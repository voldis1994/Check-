from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from checktrader.app.bootstrap import AppContext
from checktrader.domain.enums import Decision, ReasonCode, SetupState, Side
from checktrader.domain.models import AccountStatus, Acknowledgement, CycleAudit, MarketSnapshot
from checktrader.execution.commands import build_close, build_modify, build_open
from checktrader.execution.reconciliation import reconcile
from checktrader.management.manager import manage_position
from checktrader.market_data.aggregation import aggregate_standard
from checktrader.market_data.bars import last_closed
from checktrader.market_data.history import save_history
from checktrader.market_data.validation import fresh_enough, sequential_bars
from checktrader.risk.limits import record_trade_open
from checktrader.risk.validator import validate_order
from checktrader.setups.expiry import expire_setups
from checktrader.setups.state_machine import transition
from checktrader.strategies.base import StrategyContext

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def _paper_market(context: AppContext) -> MarketSnapshot:
    """Synthetic market snapshot used in paper mode when no bridge is present."""
    last = last_closed(context.history.get("M15"))
    price = last.close if last else 0.0
    return MarketSnapshot(
        context.specs.symbol,
        price,
        price + context.config.execution.paper_fill_spread_points * context.specs.point,
        datetime.now(UTC),
        context.history.get("M1"),
        context.history.get("M5"),
        context.history.get("M15"),
        AccountStatus(
            context.config.account.account_id,
            100_000.0,
            100_000.0,
            100_000.0,
            context.config.account.currency,
        ),
        context.state.positions,
        datetime.now(UTC),
    )


def _ack_to_exec_result(ack: Acknowledgement) -> dict[str, object]:
    return {
        "command_id": ack.command_id,
        "accepted": ack.accepted,
        "reason": ack.reason.value,
        "broker_order_id": ack.broker_order_id,
        "message": ack.message,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Main cycle entry point
# ──────────────────────────────────────────────────────────────────────────────


def run_cycle(context: AppContext, market: MarketSnapshot | None = None) -> CycleAudit:
    now = datetime.now(UTC)
    is_live = context.config.runtime.mode == "live"
    audit = CycleAudit(
        uuid4().hex,
        now,
        symbol=context.specs.symbol,
    )
    audit.reasons.append(ReasonCode.CYCLE_STARTED)

    # ── Step 1: resolve snapshot ────────────────────────────────────────────
    if market is None:
        if is_live:
            # In live mode never silently fall back to a fake snapshot
            audit.set_reason(ReasonCode.BRIDGE_UNAVAILABLE, ["no market snapshot provided"])
            audit.reasons.append(ReasonCode.BRIDGE_UNAVAILABLE)
            audit.completed_at = datetime.now(UTC)
            context.audit.write(audit)
            return audit
        market = _paper_market(context)

    # ── Step 2: data validation ─────────────────────────────────────────────
    if is_live:
        last_m1 = last_closed(market.m1)
        ok_fresh, reason_fresh = fresh_enough(
            last_m1,
            now,
            context.config.limits.heartbeat_max_age_seconds,
        )
        if not ok_fresh:
            audit.set_reason(ReasonCode.DATA_STALE, [reason_fresh.value])
            audit.reasons.append(reason_fresh)
            audit.completed_at = datetime.now(UTC)
            context.audit.write(audit)
            return audit

    # ── Step 3: merge closed M1 history ────────────────────────────────────
    if market.m1:
        context.history.merge("M1", market.m1)

    # ── Step 4: aggregate M5 / M15 from M1 ────────────────────────────────
    m1_all = context.history.get("M1")
    if m1_all:
        m5_agg, m15_agg = aggregate_standard(m1_all)
        context.history.merge("M5", m5_agg)
        context.history.merge("M15", m15_agg)

    # Also merge any directly-provided higher-TF bars (legacy or pre-built)
    if market.m5:
        context.history.merge("M5", market.m5)
    if market.m15:
        context.history.merge("M15", market.m15)

    market.m1 = context.history.get("M1")
    market.m5 = context.history.get("M5")
    market.m15 = context.history.get("M15")

    if market.symbol and market.symbol.upper() not in {"", "AUTO"}:
        audit.symbol = market.symbol
        if context.specs.symbol.upper() in {"AUTO", ""}:
            context.specs.symbol = market.symbol

    # ── Step 5/6: indicators + regime update ───────────────────────────────
    ok_seq, reason_seq = sequential_bars(market.m15, context.config.instrument.timeframe_decision)
    audit.reasons.append(reason_seq)
    if not ok_seq:
        audit.set_reason(reason_seq, [reason_seq.value])
        audit.completed_at = datetime.now(UTC)
        context.audit.write(audit)
        return audit

    regime = context.detector.update(market.m15)
    audit.market_regime = regime.regime
    audit.reasons.append(regime.reason)
    # Capture indicator snapshot for the audit
    ind = regime.indicators
    audit.indicator_snapshot = {
        "time": ind.time.isoformat(),
        "ema_fast": ind.ema_fast,
        "ema_slow": ind.ema_slow,
        "ema200": ind.ema200,
        "atr": ind.atr,
        "adx": ind.adx,
        "plus_di": ind.plus_di,
        "minus_di": ind.minus_di,
    }

    # Populate account_number from market status if available
    if market.account:
        audit.account_number = market.account.account_id

    # ── Step 7: expire/update setups ────────────────────────────────────────
    last_bar = last_closed(market.m15)
    if last_bar:
        for setup in expire_setups(context.state.setups.active(symbol=context.specs.symbol), last_bar.time):
            context.state.setups.upsert(setup)
            audit.reasons.append(setup.reason)

    # ── Reconcile live broker positions ─────────────────────────────────────
    reconciled = reconcile(context.state.positions, market.positions or context.state.positions)
    context.state.positions = reconciled.positions
    audit.reasons.append(reconciled.reason)

    # ── Step 8: position management — ALL positions ─────────────────────────
    if context.state.positions:
        for pos in list(context.state.positions):
            action = manage_position(
                pos,
                bid=market.bid,
                ask=market.ask,
                atr_value=regime.indicators.atr,
                regime=regime,
                specs=context.specs,
                config=context.config,
            )
            audit.management = action
            audit.reasons.append(action.reason)

            if action.decision == Decision.CLOSE:
                cmd = build_close(pos, action)
                ack, context.state.positions = context.execution.execute(cmd, context.state.positions)
                audit.command = cmd
                audit.execution_result = _ack_to_exec_result(ack)
                audit.reasons.append(ack.reason)
                audit.decision = Decision.CLOSE
                audit.set_reason(ack.reason)
            elif action.decision == Decision.MODIFY:
                cmd = build_modify(pos, action)
                ack, context.state.positions = context.execution.execute(cmd, context.state.positions)
                audit.command = cmd
                audit.execution_result = _ack_to_exec_result(ack)
                audit.reasons.append(ack.reason)
                audit.decision = Decision.MODIFY
                audit.set_reason(ack.reason)

            # Update mark-to-market price on surviving positions
            if any(p.position_id == pos.position_id for p in context.state.positions):
                pos.current_price = market.bid if pos.side == Side.BUY else market.ask

    else:
        # ── Step 9: strategy router ──────────────────────────────────────────
        result = context.router.evaluate(
            StrategyContext(
                context.config,
                context.specs,
                market,
                regime,
                market.account,
                context.state.positions,
                context.state.setups,
            )
        )
        audit.reasons.append(result.reason)
        audit.signal = result.signal
        audit.decision = result.decision

        if result.setup:
            audit.setup_state = result.setup.state

        if result.signal:
            audit.selected_strategy = result.signal.strategy

            # ── Step 10: risk validate ───────────────────────────────────────
            risk = validate_order(
                result.signal,
                config=context.config,
                specs=context.specs,
                account=market.account,
                positions=context.state.positions,
                limit_state=context.state.limits,
                bid=market.bid,
                ask=market.ask,
                atr_value=regime.indicators.atr,
                now=now,
            )
            audit.risk_result = risk
            audit.reasons.extend(risk.messages)

            if risk.allowed:
                # ── Step 11: order command ───────────────────────────────────
                cmd = build_open(result.signal, risk.lot, context.config.execution)
                ack, context.state.positions = context.execution.execute(cmd, context.state.positions)
                audit.command = cmd
                audit.execution_result = _ack_to_exec_result(ack)
                audit.reasons.append(ack.reason)
                audit.decision = Decision.OPEN
                audit.set_reason(ack.reason)

                # ── Step 12: update limits on accepted trade ─────────────────
                if ack.accepted:
                    record_trade_open(context.state.limits, now)
                    # Advance setup state to ORDER_PENDING if a setup is linked
                    if result.setup is not None:
                        transition(result.setup, SetupState.ORDER_PENDING)
                        result.setup.command_id = cmd.command_id
                        context.state.setups.upsert(result.setup)
            else:
                audit.failed_conditions = [r.value for r in risk.messages if r != risk.reason]
                audit.set_reason(risk.reason, audit.failed_conditions or None)
                audit.decision = Decision.BLOCK
        else:
            audit.set_reason(result.reason)

    # ── Step 13: save history + state ───────────────────────────────────────
    save_history(context.config.paths.history_file, context.history)
    context.state_store.save(context.state)
    context.metrics.inc("cycles")
    context.metrics.save(context.config.paths.metrics_file)

    # ── Step 14: finalise audit ──────────────────────────────────────────────
    audit.reasons.append(ReasonCode.CYCLE_COMPLETED)
    audit.completed_at = datetime.now(UTC)

    if not audit.human_readable_reason:
        last_reason = audit.reasons[-2] if len(audit.reasons) >= 2 else audit.reasons[-1]
        audit.set_reason(last_reason)

    context.audit.write(audit)
    return audit
