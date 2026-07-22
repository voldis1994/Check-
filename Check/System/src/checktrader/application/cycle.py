"""Single trading cycle with strict ACK / reconciliation / retry rules."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from checktrader.config.models import SystemConfig
from checktrader.domain.enums import ConfirmationSource, OrderAction, PositionState, RiskDecision, Side, StrategyResult
from checktrader.domain.execution import PendingCommandState
from checktrader.domain.money import price_tolerance
from checktrader.domain.orders import BrokerPosition, OrderCommand
from checktrader.domain.positions import ManagedPosition
from checktrader.domain.timeutil import add_ms, elapsed_ms, is_at_or_after
from checktrader.domain.trailing import TrailingState
from checktrader.execution.ack_parser import (
    parse_acknowledgement,
    validate_close_ack,
    validate_modify_ack,
    validate_open_ack,
)
from checktrader.execution.command_factory import (
    build_close_command,
    build_modify_command,
    build_open_command,
    write_command,
)
from checktrader.execution.protocol import read_json
from checktrader.execution.reconciliation import reconcile_position_from_broker
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
        return None
    return matches[0] if len(matches) == 1 else None


def _identity_kwargs(config: SystemConfig, status: StatusSnapshot, market: MarketSnapshot) -> dict[str, str]:
    server = market.server or getattr(status, "server", "") or config.account.required_server
    return {
        "account_number": status.account_number,
        "server": server,
        "instance_id": config.runtime.instance_id,
    }


def _new_pending(
    cmd: OrderCommand,
    *,
    now_utc: str,
    ack_timeout_ms: int,
    maximum_retries: int,
    retry_count: int = 0,
    created_at: str | None = None,
) -> PendingCommandState:
    return PendingCommandState(
        command_id=cmd.command_id,
        action=cmd.action,
        account_number=cmd.account_number,
        server=cmd.server,
        instance_id=cmd.instance_id,
        symbol=cmd.symbol,
        magic=cmd.magic,
        ticket=cmd.ticket,
        setup_fingerprint=cmd.setup_fingerprint,
        requested_price=cmd.requested_price,
        requested_volume=cmd.volume,
        requested_stop_loss=cmd.stop_loss if cmd.action is OrderAction.OPEN else cmd.requested_stop_loss,
        requested_take_profit=cmd.take_profit if cmd.action is OrderAction.OPEN else cmd.requested_take_profit,
        created_at=created_at or now_utc,
        last_attempt_at=now_utc,
        retry_count=retry_count,
        maximum_retries=maximum_retries,
        acknowledgement_deadline=add_ms(now_utc, ack_timeout_ms),
        last_error=None,
    )


def _find_ack(ack_dir: Path, command_id: str) -> Path | None:
    matches = sorted(ack_dir.glob(f"*_{command_id}.ack.json"))
    return matches[-1] if matches else None


def _confirm_modify_trailing(
    state: InstanceRuntimeState,
    *,
    applied_sl: float,
    side: Side,
    market: MarketSnapshot,
    config: SystemConfig,
    tol: float,
) -> None:
    prev = state.trailing.confirmed_stop_loss or state.trailing.confirmed_be_sl
    if state.trailing.be_confirmed and prev is not None:
        jump = count_jump_steps(
            side=side,
            previous_sl=prev,
            applied_sl=applied_sl,
            trailing_step_pips=config.trade_management.trailing_step_pips,
            pip_size=market.specs.pip_size,
            digits=market.specs.digits,
            tolerance=tol,
        )
        state.trailing.confirmed_grid_step += max(jump, 1) if jump else 1
        state.last_reason = ReasonCode.TRAILING_GRID_CONFIRMED.value
    else:
        state.trailing.be_confirmed = True
        state.trailing.confirmed_be_sl = applied_sl
        state.last_reason = ReasonCode.BE_CONFIRMED.value
    state.trailing.confirmed_stop_loss = applied_sl
    state.trailing.pending_stop_loss = None
    state.trailing.pending_command_id = None
    state.trailing.confirmation_source = ConfirmationSource.ACK
    state.position.stop_loss = applied_sl
    state.position.state = PositionState.OPEN
    state.pending = None


def _try_retry(
    *,
    config: SystemConfig,
    state: InstanceRuntimeState,
    market: MarketSnapshot,
    status: StatusSnapshot,
    bridge_root: Path,
    now_utc: str,
    broker_pos: BrokerPosition | None,
) -> CycleResult:
    pending = state.pending
    assert pending is not None
    state_path = Path(config.paths.root) / config.paths.state / "instance.json"
    symbol = config.instrument.symbol
    magic = config.position.magic_number
    identity = _identity_kwargs(config, status, market)
    commands_dir = bridge_root / "commands"

    if not is_at_or_after(now_utc, pending.acknowledgement_deadline):
        save_instance_state(state_path, state, now_utc=now_utc)
        return CycleResult(ReasonCode.COMMAND_ALREADY_PENDING)

    if pending.retry_count >= pending.maximum_retries:
        if pending.action is OrderAction.OPEN:
            state.position.state = PositionState.ERROR
            state.last_reason = ReasonCode.RECONCILIATION_REQUIRED.value
        else:
            state.position.state = PositionState.RECONCILING
            state.last_reason = (
                ReasonCode.MODIFY_TIMEOUT.value
                if pending.action is OrderAction.MODIFY
                else ReasonCode.RECONCILIATION_REQUIRED.value
            )
        pending.last_error = state.last_reason
        save_instance_state(state_path, state, now_utc=now_utc)
        return CycleResult(ReasonCode(state.last_reason))

    if elapsed_ms(pending.last_attempt_at, now_utc) < config.execution.retry_delay_ms:
        save_instance_state(state_path, state, now_utc=now_utc)
        return CycleResult(ReasonCode.COMMAND_ALREADY_PENDING)

    retry_count = pending.retry_count + 1
    created_at = pending.created_at
    if pending.action is OrderAction.OPEN:
        cmd = build_open_command(
            symbol=symbol,
            magic=magic,
            side=state.position.side or Side.BUY,
            volume=pending.requested_volume or 0.0,
            requested_price=pending.requested_price or 0.0,
            stop_loss=pending.requested_stop_loss or 0.0,
            take_profit=pending.requested_take_profit,
            setup_id=state.position.setup_id or "",
            setup_fingerprint=pending.setup_fingerprint or "",
            created_at_utc=now_utc,
            **identity,
        )
        state.position.state = PositionState.OPEN_PENDING
        reason = ReasonCode.OPEN_SENT
    elif pending.action is OrderAction.MODIFY:
        cmd = build_modify_command(
            ticket=pending.ticket or 0,
            symbol=symbol,
            magic=magic,
            requested_stop_loss=pending.requested_stop_loss or 0.0,
            requested_take_profit=pending.requested_take_profit or 0.0,
            previous_broker_stop_loss=(broker_pos.stop_loss if broker_pos else state.trailing.broker_stop_loss or 0.0),
            trailing_reason=state.trailing.last_reason or ReasonCode.MODIFY_SENT.value,
            trailing_step=config.trade_management.trailing_step_pips,
            created_at_utc=now_utc,
            **identity,
        )
        state.position.state = PositionState.MODIFY_PENDING
        state.trailing.pending_command_id = cmd.command_id
        state.trailing.pending_stop_loss = pending.requested_stop_loss
        state.trailing.retry_count = retry_count
        reason = ReasonCode.MODIFY_SENT
    else:
        side = state.position.side or Side.BUY
        cmd = build_close_command(
            ticket=pending.ticket or 0,
            symbol=symbol,
            magic=magic,
            volume=pending.requested_volume or (broker_pos.volume if broker_pos else 0.0),
            requested_price=pending.requested_price or (market.bid if side is Side.BUY else market.ask),
            close_reason=pending.last_error or ReasonCode.CLOSE_SENT.value,
            created_at_utc=now_utc,
            **identity,
        )
        state.position.state = PositionState.CLOSE_PENDING
        reason = ReasonCode.CLOSE_SENT

    seq = state.next_sequence()
    path = write_command(commands_dir, cmd, sequence=seq)
    state.pending = _new_pending(
        cmd,
        now_utc=now_utc,
        ack_timeout_ms=config.execution.ack_timeout_ms,
        maximum_retries=config.execution.maximum_retries,
        retry_count=retry_count,
        created_at=created_at,
    )
    state.last_reason = reason.value
    save_instance_state(state_path, state, now_utc=now_utc)
    return CycleResult(reason, str(path), cmd.action)


def _handle_pending(
    *,
    config: SystemConfig,
    state: InstanceRuntimeState,
    market: MarketSnapshot,
    status: StatusSnapshot,
    bridge_root: Path,
    now_utc: str,
    broker_pos: BrokerPosition | None,
) -> CycleResult | None:
    pending = state.pending
    if pending is None:
        return None

    symbol = config.instrument.symbol
    magic = config.position.magic_number
    state_path = Path(config.paths.root) / config.paths.state / "instance.json"
    ack_dir = bridge_root / "acknowledgements"
    tol = price_tolerance(
        point=market.specs.point, digits=market.specs.digits, points=config.execution.price_tolerance_points
    )

    ack_path = _find_ack(ack_dir, pending.command_id) if ack_dir.exists() else None
    if ack_path is not None:
        ack = parse_acknowledgement(read_json(ack_path))

        if pending.action is OrderAction.OPEN and state.position.state in {
            PositionState.OPEN_PENDING,
            PositionState.RECONCILING,
        }:
            status_pos = _find_position(status, symbol=symbol, magic=magic, ticket=ack.ticket)
            reason = validate_open_ack(ack, pending, broker_pos=status_pos)
            if reason is None:
                state.position.state = PositionState.OPEN
                state.position.ticket = ack.ticket
                state.position.open_price = ack.applied_price
                state.position.volume = ack.applied_volume
                state.position.stop_loss = ack.applied_stop_loss
                if pending.setup_fingerprint and pending.setup_fingerprint not in state.known_setup_fingerprints:
                    state.known_setup_fingerprints.append(pending.setup_fingerprint)
                state.pending = None
                state.last_reason = ReasonCode.OPEN_CONFIRMED.value
                save_instance_state(state_path, state, now_utc=now_utc)
                return CycleResult(ReasonCode.OPEN_CONFIRMED)
            if reason is ReasonCode.RECONCILIATION_REQUIRED:
                state.position.state = PositionState.RECONCILING
                pending.last_error = reason.value
                state.last_reason = reason.value
                save_instance_state(state_path, state, now_utc=now_utc)
                return CycleResult(reason)
            state.position = ManagedPosition()
            state.pending = None
            state.last_reason = reason.value
            save_instance_state(state_path, state, now_utc=now_utc)
            return CycleResult(reason)

        if pending.action is OrderAction.MODIFY and state.position.state is PositionState.MODIFY_PENDING:
            side = state.position.side or (broker_pos.side if broker_pos else None)
            if side is None:
                state.last_reason = ReasonCode.RECONCILIATION_REQUIRED.value
                state.position.state = PositionState.RECONCILING
                save_instance_state(state_path, state, now_utc=now_utc)
                return CycleResult(ReasonCode.RECONCILIATION_REQUIRED)
            status_pos = _find_position(status, symbol=symbol, magic=magic, ticket=pending.ticket)
            reason = validate_modify_ack(ack, pending, side=side, broker_pos=status_pos, tolerance=tol)
            if reason is None and ack.applied_stop_loss is not None:
                _confirm_modify_trailing(
                    state,
                    applied_sl=float(ack.applied_stop_loss),
                    side=side,
                    market=market,
                    config=config,
                    tol=tol,
                )
                save_instance_state(state_path, state, now_utc=now_utc)
                return CycleResult(ReasonCode(state.last_reason or ReasonCode.MODIFY_CONFIRMED.value))
            pending.last_error = (reason or ReasonCode.MODIFY_REJECTED).value
            state.last_reason = pending.last_error
            # Expire deadline so retry path can fire after retry_delay_ms
            pending.acknowledgement_deadline = now_utc
            return _try_retry(
                config=config,
                state=state,
                market=market,
                status=status,
                bridge_root=bridge_root,
                now_utc=now_utc,
                broker_pos=broker_pos,
            )

        if pending.action is OrderAction.CLOSE and state.position.state is PositionState.CLOSE_PENDING:
            status_pos = _find_position(status, symbol=symbol, magic=magic, ticket=pending.ticket)
            reason = validate_close_ack(ack, pending, broker_pos=status_pos)
            if reason is None:
                state.position = ManagedPosition()
                state.trailing = TrailingState()
                state.pending = None
                state.last_reason = ReasonCode.CLOSE_CONFIRMED.value
                save_instance_state(state_path, state, now_utc=now_utc)
                return CycleResult(ReasonCode.CLOSE_CONFIRMED)
            pending.last_error = reason.value
            state.last_reason = reason.value
            if reason is ReasonCode.CLOSE_REJECTED:
                state.position.state = PositionState.OPEN if broker_pos is not None else PositionState.RECONCILING
                state.pending = None
                save_instance_state(state_path, state, now_utc=now_utc)
                return CycleResult(reason)
            state.position.state = PositionState.RECONCILING
            save_instance_state(state_path, state, now_utc=now_utc)
            return CycleResult(reason)

    # Broker already reflects the pending action
    if (
        pending.action is OrderAction.OPEN
        and broker_pos is not None
        and state.position.state
        in {
            PositionState.OPEN_PENDING,
            PositionState.RECONCILING,
        }
    ):
        state.position.state = PositionState.OPEN
        state.position.ticket = broker_pos.ticket
        state.position.open_price = broker_pos.open_price
        state.position.volume = broker_pos.volume
        state.position.stop_loss = broker_pos.stop_loss
        if pending.setup_fingerprint and pending.setup_fingerprint not in state.known_setup_fingerprints:
            state.known_setup_fingerprints.append(pending.setup_fingerprint)
        state.pending = None
        state.last_reason = ReasonCode.RECONCILIATION_CONFIRMED.value
        save_instance_state(state_path, state, now_utc=now_utc)
        return CycleResult(ReasonCode.RECONCILIATION_CONFIRMED)

    if pending.action is OrderAction.MODIFY and broker_pos is not None and pending.requested_stop_loss is not None:
        if abs(broker_pos.stop_loss - pending.requested_stop_loss) <= tol:
            side = state.position.side or broker_pos.side
            _confirm_modify_trailing(
                state,
                applied_sl=broker_pos.stop_loss,
                side=side,
                market=market,
                config=config,
                tol=tol,
            )
            state.trailing.confirmation_source = ConfirmationSource.STATUS
            state.last_reason = ReasonCode.RECONCILIATION_CONFIRMED.value
            save_instance_state(state_path, state, now_utc=now_utc)
            return CycleResult(ReasonCode.RECONCILIATION_CONFIRMED)

    if (
        pending.action is OrderAction.CLOSE
        and broker_pos is None
        and state.position.state is PositionState.CLOSE_PENDING
    ):
        state.position = ManagedPosition()
        state.trailing = TrailingState()
        state.pending = None
        state.last_reason = ReasonCode.RECONCILIATION_CONFIRMED.value
        save_instance_state(state_path, state, now_utc=now_utc)
        return CycleResult(ReasonCode.RECONCILIATION_CONFIRMED)

    return _try_retry(
        config=config,
        state=state,
        market=market,
        status=status,
        bridge_root=bridge_root,
        now_utc=now_utc,
        broker_pos=broker_pos,
    )


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
    identity = _identity_kwargs(config, status, market)

    if status.account_number not in config.account.allowed_account_numbers:
        state.last_reason = ReasonCode.ACCOUNT_NOT_ALLOWED.value
        save_instance_state(state_path, state, now_utc=now_utc)
        return CycleResult(ReasonCode.ACCOUNT_NOT_ALLOWED)

    if config.account.required_server and identity["server"] and identity["server"] != config.account.required_server:
        state.last_reason = ReasonCode.SERVER_MISMATCH.value
        save_instance_state(state_path, state, now_utc=now_utc)
        return CycleResult(ReasonCode.SERVER_MISMATCH)

    if is_stale(
        generated_at_utc=status.generated_at_utc, now_utc=now_utc, maximum_age_ms=config.execution.maximum_status_age_ms
    ):
        return CycleResult(ReasonCode.DATA_STALE)
    if is_stale(
        generated_at_utc=market.generated_at_utc, now_utc=now_utc, maximum_age_ms=config.execution.maximum_market_age_ms
    ):
        return CycleResult(ReasonCode.DATA_STALE)

    ticket_hint = state.position.ticket or (state.pending.ticket if state.pending else None)
    broker_pos = _find_position(status, symbol=symbol, magic=magic, ticket=ticket_hint)

    pending_result = _handle_pending(
        config=config,
        state=state,
        market=market,
        status=status,
        bridge_root=bridge_root,
        now_utc=now_utc,
        broker_pos=broker_pos,
    )
    if pending_result is not None:
        return pending_result

    broker_pos = _find_position(status, symbol=symbol, magic=magic, ticket=state.position.ticket)
    state.position, _ = reconcile_position_from_broker(state.position, broker_pos)
    if broker_pos is not None and state.position.state is PositionState.FLAT:
        state.position.state = PositionState.OPEN

    if state.pending is not None:
        save_instance_state(state_path, state, now_utc=now_utc)
        return CycleResult(ReasonCode.COMMAND_ALREADY_PENDING)

    commands_dir = bridge_root / "commands"

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
                **identity,
            )
            path = write_command(commands_dir, cmd, sequence=state.next_sequence())
            state.pending = _new_pending(
                cmd,
                now_utc=now_utc,
                ack_timeout_ms=config.execution.ack_timeout_ms,
                maximum_retries=config.execution.maximum_retries,
            )
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
                **identity,
            )
            path = write_command(commands_dir, cmd, sequence=state.next_sequence())
            state.pending = _new_pending(
                cmd,
                now_utc=now_utc,
                ack_timeout_ms=config.execution.ack_timeout_ms,
                maximum_retries=config.execution.maximum_retries,
            )
            state.trailing.pending_command_id = cmd.command_id
            state.trailing.pending_stop_loss = decision.stop_loss
            state.position.state = PositionState.MODIFY_PENDING
            state.last_reason = ReasonCode.MODIFY_SENT.value
            save_instance_state(state_path, state, now_utc=now_utc)
            return CycleResult(ReasonCode.MODIFY_SENT, str(path), OrderAction.MODIFY)
        save_instance_state(state_path, state, now_utc=now_utc)
        return CycleResult(decision.reason)

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
    if fp in state.known_setup_fingerprints or (state.pending is not None and state.pending.setup_fingerprint == fp):
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
        fixed_take_profit_enabled=config.trade_management.fixed_take_profit_enabled,
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

    take_profit = 0.0 if risk.take_profit is None else risk.take_profit
    cmd = build_open_command(
        symbol=symbol,
        magic=magic,
        side=side,
        volume=risk.volume,
        requested_price=entry,
        stop_loss=risk.stop_loss,
        take_profit=take_profit,
        setup_id=strategy_decision.setup.setup_id,
        setup_fingerprint=fp,
        created_at_utc=now_utc,
        **identity,
    )
    path = write_command(commands_dir, cmd, sequence=state.next_sequence())
    state.pending = _new_pending(
        cmd,
        now_utc=now_utc,
        ack_timeout_ms=config.execution.ack_timeout_ms,
        maximum_retries=config.execution.maximum_retries,
    )
    state.position.state = PositionState.OPEN_PENDING
    state.position.side = side
    state.position.volume = risk.volume
    state.position.stop_loss = risk.stop_loss
    state.position.take_profit = take_profit
    state.position.setup_id = strategy_decision.setup.setup_id
    state.position.setup_fingerprint = fp
    state.last_reason = ReasonCode.OPEN_SENT.value
    save_instance_state(state_path, state, now_utc=now_utc)
    return CycleResult(ReasonCode.OPEN_SENT, str(path), OrderAction.OPEN)
