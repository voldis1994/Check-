"""Single trading cycle."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from checktrader.config.models import SystemConfig
from checktrader.domain.enums import OrderAction, PositionState, RiskDecision, StrategyResult
from checktrader.domain.money import price_tolerance
from checktrader.domain.orders import BrokerPosition
from checktrader.execution.ack_parser import parse_acknowledgement, validate_modify_ack
from checktrader.execution.command_factory import (
    build_close_command,
    build_modify_command,
    build_open_command,
    write_command,
)
from checktrader.execution.protocol import read_json
from checktrader.execution.reconciliation import confirm_pending_from_status, reconcile_position_from_broker
from checktrader.market_data.freshness import is_stale
from checktrader.market_data.loader import MarketSnapshot
from checktrader.market_data.status import StatusSnapshot
from checktrader.observability.reason_codes import ReasonCode
from checktrader.position_management.engine import choose_protective_action
from checktrader.position_management.pip_grid_trailing import count_jump_steps
from checktrader.risk.engine import approve_order
from checktrader.state.store import InstanceRuntimeState, save_instance_state
from checktrader.strategy.engine import run_strategy


@dataclass(frozen=True, slots=True)
class CycleResult:
    reason: ReasonCode
    command_path: str | None = None
    action: OrderAction = OrderAction.NONE


def _find_position(status: StatusSnapshot, *, symbol: str, magic: int, ticket: int | None) -> BrokerPosition | None:
    matches = [p for p in status.positions if p.symbol == symbol and p.magic == magic]
    if ticket is not None:
        for p in matches:
            if p.ticket == ticket:
                return p
    return matches[0] if len(matches) == 1 else None


def run_cycle(
    *,
    config: SystemConfig,
    state: InstanceRuntimeState,
    market: MarketSnapshot,
    status: StatusSnapshot,
    bridge_root: Path,
    now_utc: str,
    kill_switch: bool = False,
) -> CycleResult:
    symbol = config.instrument.symbol
    magic = config.position.magic_number
    state_path = Path(config.paths.root) / config.paths.state / "instance.json"

    if status.account_number not in config.account.allowed_account_numbers:
        state.last_reason = ReasonCode.ACCOUNT_NOT_ALLOWED.value
        save_instance_state(state_path, state, now_utc=now_utc)
        return CycleResult(ReasonCode.ACCOUNT_NOT_ALLOWED)

    if is_stale(
        generated_at_utc=status.generated_at_utc, now_utc=now_utc, maximum_age_ms=config.execution.maximum_status_age_ms
    ):
        return CycleResult(ReasonCode.DATA_STALE)
    if is_stale(
        generated_at_utc=market.generated_at_utc, now_utc=now_utc, maximum_age_ms=config.execution.maximum_market_age_ms
    ):
        return CycleResult(ReasonCode.DATA_STALE)

    # Process ACK files before broker reconcile so pending states survive.
    ack_dir = bridge_root / "acknowledgements"
    if state.pending_command_id and ack_dir.exists():
        for ack_path in sorted(ack_dir.glob(f"*_{state.pending_command_id}.ack.json")):
            ack = parse_acknowledgement(read_json(ack_path))
            if state.position.state is PositionState.OPEN_PENDING and ack.action is OrderAction.OPEN and ack.ticket:
                state.position.state = PositionState.OPEN
                state.position.ticket = ack.ticket
                state.position.open_price = ack.applied_price
                state.position.volume = ack.applied_volume
                state.position.stop_loss = ack.applied_stop_loss
                state.pending_command_id = None
                state.last_reason = ReasonCode.OPEN_CONFIRMED.value
            elif state.position.state is PositionState.MODIFY_PENDING and ack.action is OrderAction.MODIFY:
                tol = price_tolerance(
                    point=market.specs.point, digits=market.specs.digits, points=config.execution.price_tolerance_points
                )
                pending_sl = state.trailing.pending_stop_loss or 0.0
                from dataclasses import replace

                cmd = replace(
                    build_modify_command(
                        ticket=state.position.ticket or 0,
                        symbol=symbol,
                        magic=magic,
                        requested_stop_loss=pending_sl,
                        requested_take_profit=state.position.take_profit or 0.0,
                        previous_broker_stop_loss=state.trailing.broker_stop_loss or 0.0,
                        trailing_reason=state.trailing.last_reason or "",
                        trailing_step=config.trade_management.trailing_step_pips,
                        created_at_utc=now_utc,
                    ),
                    command_id=ack.command_id,
                )
                mismatch = validate_modify_ack(
                    ack,
                    cmd,
                    open_ticket=state.position.ticket or -1,
                    symbol=symbol,
                    magic=magic,
                    pending_sl=pending_sl,
                    tolerance=tol,
                )
                if mismatch is None and ack.applied_stop_loss is not None:
                    prev = state.trailing.confirmed_stop_loss or state.trailing.confirmed_be_sl
                    if state.trailing.be_confirmed and prev is not None and state.position.side is not None:
                        jump = count_jump_steps(
                            side=state.position.side,
                            previous_sl=prev,
                            applied_sl=float(ack.applied_stop_loss),
                            trailing_step_pips=config.trade_management.trailing_step_pips,
                            pip_size=market.specs.pip_size,
                            digits=market.specs.digits,
                            tolerance=tol,
                        )
                        state.trailing.confirmed_grid_step += max(jump, 1) if jump else 1
                    if not state.trailing.be_confirmed:
                        state.trailing.be_confirmed = True
                        state.trailing.confirmed_be_sl = float(ack.applied_stop_loss)
                        state.last_reason = ReasonCode.BE_CONFIRMED.value
                    else:
                        state.last_reason = ReasonCode.TRAILING_GRID_CONFIRMED.value
                    state.trailing.confirmed_stop_loss = float(ack.applied_stop_loss)
                    state.trailing.pending_stop_loss = None
                    state.position.stop_loss = float(ack.applied_stop_loss)
                    state.position.state = PositionState.OPEN
                    state.pending_command_id = None
                else:
                    # Rejected / mismatched ACK: clear command id but keep pending SL for retry.
                    state.last_reason = (mismatch or ReasonCode.TRAILING_ACK_SL_MISMATCH).value
                    state.position.state = PositionState.OPEN
                    state.pending_command_id = None
                    state.trailing.retry_count += 1
            elif state.position.state is PositionState.CLOSE_PENDING and ack.action is OrderAction.CLOSE:
                from checktrader.domain.positions import ManagedPosition
                from checktrader.domain.trailing import TrailingState

                state.position = ManagedPosition()
                state.trailing = TrailingState()
                state.pending_command_id = None
                state.last_reason = ReasonCode.CLOSE_CONFIRMED.value
                save_instance_state(state_path, state, now_utc=now_utc)
                return CycleResult(ReasonCode.CLOSE_CONFIRMED)

    broker_pos = _find_position(status, symbol=symbol, magic=magic, ticket=state.position.ticket)
    state.position, _ = reconcile_position_from_broker(state.position, broker_pos)
    if broker_pos is not None:
        tol = price_tolerance(
            point=market.specs.point, digits=market.specs.digits, points=config.execution.price_tolerance_points
        )
        state.trailing, confirmed = confirm_pending_from_status(state.trailing, broker_pos, tolerance=tol)
        if confirmed:
            state.position.stop_loss = broker_pos.stop_loss
            state.pending_command_id = None
            state.position.state = PositionState.OPEN

    if state.pending_command_id is not None:
        save_instance_state(state_path, state, now_utc=now_utc)
        return CycleResult(ReasonCode.COMMAND_ALREADY_PENDING)

    commands_dir = bridge_root / "commands"

    # Manage open position
    if broker_pos is not None and state.position.state in {PositionState.OPEN, PositionState.RECONCILING}:
        state.position.state = PositionState.OPEN
        decision = choose_protective_action(
            side=broker_pos.side,
            open_price=broker_pos.open_price,
            volume=broker_pos.volume,
            broker_sl=broker_pos.stop_loss,
            current_price=market.bid if broker_pos.side.value == "BUY" else market.ask,
            current_net_profit=broker_pos.net_profit,
            swap=broker_pos.swap,
            commission=broker_pos.commission,
            specs=market.specs,
            config=config.trade_management,
            trailing=state.trailing,
            recent_m1=list(market.bars_m1[-30:]),
            current_spread_pips=market.spread_pips,
            median_spread_pips=max(market.spread_pips, 0.1),
            bid=market.bid,
            ask=market.ask,
        )
        if decision.state is not None:
            state.trailing = decision.state
        if decision.close:
            cmd = build_close_command(
                ticket=broker_pos.ticket,
                symbol=symbol,
                magic=magic,
                volume=broker_pos.volume,
                requested_price=market.bid if broker_pos.side.value == "BUY" else market.ask,
                close_reason=decision.reason.value,
                created_at_utc=now_utc,
            )
            seq = state.next_sequence()
            path = write_command(commands_dir, cmd, sequence=seq)
            state.pending_command_id = cmd.command_id
            state.position.state = PositionState.CLOSE_PENDING
            state.last_reason = ReasonCode.CLOSE_SENT.value
            save_instance_state(state_path, state, now_utc=now_utc)
            return CycleResult(ReasonCode.CLOSE_SENT, str(path), OrderAction.CLOSE)
        if decision.action is OrderAction.MODIFY and decision.stop_loss is not None:
            cmd = build_modify_command(
                ticket=broker_pos.ticket,
                symbol=symbol,
                magic=magic,
                requested_stop_loss=decision.stop_loss,
                requested_take_profit=broker_pos.take_profit,
                previous_broker_stop_loss=broker_pos.stop_loss,
                trailing_reason=decision.reason.value,
                trailing_step=config.trade_management.trailing_step_pips,
                created_at_utc=now_utc,
            )
            seq = state.next_sequence()
            path = write_command(commands_dir, cmd, sequence=seq)
            state.pending_command_id = cmd.command_id
            state.trailing.pending_command_id = cmd.command_id
            state.trailing.pending_stop_loss = decision.stop_loss
            state.position.state = PositionState.MODIFY_PENDING
            state.last_reason = ReasonCode.MODIFY_SENT.value
            save_instance_state(state_path, state, now_utc=now_utc)
            return CycleResult(ReasonCode.MODIFY_SENT, str(path), OrderAction.MODIFY)
        save_instance_state(state_path, state, now_utc=now_utc)
        return CycleResult(decision.reason)

    # Flat → strategy
    if kill_switch or not config.runtime.trading_enabled:
        state.last_reason = ReasonCode.KILL_SWITCH_ACTIVE.value
        save_instance_state(state_path, state, now_utc=now_utc)
        return CycleResult(ReasonCode.KILL_SWITCH_ACTIVE)

    if not status.trade_allowed:
        return CycleResult(ReasonCode.TRADE_NOT_ALLOWED)
    if config.account.require_expert_enabled and not status.expert_enabled:
        return CycleResult(ReasonCode.EXPERT_NOT_ENABLED)
    if not market.market_open:
        return CycleResult(ReasonCode.MARKET_CLOSED)

    strategy_decision = run_strategy(
        symbol=symbol,
        specs=market.specs,
        bars_m1=list(market.bars_m1),
        config=config.strategy,
        now_utc=now_utc,
    )
    if (
        strategy_decision.result in {StrategyResult.NO_SIGNAL, StrategyResult.DATA_INVALID}
        or strategy_decision.setup is None
    ):
        state.last_reason = strategy_decision.reason.value
        save_instance_state(state_path, state, now_utc=now_utc)
        return CycleResult(strategy_decision.reason)

    fp = strategy_decision.setup.fingerprint
    if fp in state.known_setup_fingerprints:
        state.last_reason = ReasonCode.DUPLICATE_SETUP.value
        save_instance_state(state_path, state, now_utc=now_utc)
        return CycleResult(ReasonCode.DUPLICATE_SETUP)

    side = strategy_decision.setup.direction
    entry = market.ask if side.value == "BUY" else market.bid
    risk = approve_order(
        side=side,
        entry=entry,
        stop_loss=strategy_decision.setup.proposed_stop_loss,
        specs=market.specs,
        risk=config.risk,
        equity=status.equity,
        free_margin=status.free_margin,
    )
    if risk.decision is not RiskDecision.APPROVED:
        mapping = {
            RiskDecision.INVALID_STOP: ReasonCode.INVALID_STOP_LOSS,
            RiskDecision.INVALID_VOLUME: ReasonCode.INVALID_VOLUME,
            RiskDecision.MARGIN_INSUFFICIENT: ReasonCode.MARGIN_INSUFFICIENT,
            RiskDecision.SYMBOL_SPEC_MISSING: ReasonCode.SYMBOL_SPEC_MISSING,
            RiskDecision.PRICE_INVALID: ReasonCode.INVALID_ENTRY_PRICE,
        }
        reason = mapping.get(risk.decision, ReasonCode.INTERNAL_ERROR)
        state.last_reason = reason.value
        save_instance_state(state_path, state, now_utc=now_utc)
        return CycleResult(reason)

    cmd = build_open_command(
        symbol=symbol,
        magic=magic,
        side=side,
        volume=risk.volume,
        requested_price=entry,
        stop_loss=risk.stop_loss,
        take_profit=risk.take_profit,
        setup_id=strategy_decision.setup.setup_id,
        setup_fingerprint=fp,
        created_at_utc=now_utc,
    )
    seq = state.next_sequence()
    path = write_command(commands_dir, cmd, sequence=seq)
    state.known_setup_fingerprints.append(fp)
    state.pending_command_id = cmd.command_id
    state.position.state = PositionState.OPEN_PENDING
    state.position.side = side
    state.position.volume = risk.volume
    state.position.stop_loss = risk.stop_loss
    state.position.take_profit = risk.take_profit
    state.position.setup_id = strategy_decision.setup.setup_id
    state.position.setup_fingerprint = fp
    state.last_reason = ReasonCode.OPEN_SENT.value
    save_instance_state(state_path, state, now_utc=now_utc)
    return CycleResult(ReasonCode.OPEN_SENT, str(path), OrderAction.OPEN)
