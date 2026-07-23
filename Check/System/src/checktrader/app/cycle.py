from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from checktrader.app.bootstrap import AppContext
from checktrader.domain.enums import Decision, MarketRegime, ReasonCode, SetupState, Side
from checktrader.domain.models import (
    AccountStatus,
    Acknowledgement,
    CycleAudit,
    IndicatorSnapshot,
    MarketSnapshot,
    Position,
    RegimeSnapshot,
)
from checktrader.execution.commands import build_close, build_modify, build_open
from checktrader.execution.reconciliation import reconcile
from checktrader.management.manager import manage_position
from checktrader.market_data.aggregation import aggregate_standard
from checktrader.market_data.bars import last_closed
from checktrader.market_data.history import save_history
from checktrader.market_data.validation import heartbeat_fresh, sequential_bars
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


def _norm_symbol(symbol: str | None) -> str:
    return (symbol or "").strip().upper()


def _positions_for_symbol(positions: list[Position], symbol: str) -> list[Position]:
    target = _norm_symbol(symbol)
    return [p for p in positions if _norm_symbol(p.symbol) == target]


def _apply_broker_specs(context: AppContext, market: MarketSnapshot) -> None:
    meta = market.meta or {}
    specs = context.specs
    if "digits" in meta:
        specs.digits = int(meta["digits"])
    if "point" in meta:
        specs.point = float(meta["point"])
    if "tick_size" in meta:
        specs.tick_size = float(meta["tick_size"])
    if "stop_level" in meta:
        specs.stop_level_points = float(meta["stop_level"])
    if "freeze_level" in meta:
        specs.freeze_level_points = float(meta["freeze_level"])
    if "min_lot" in meta:
        specs.min_lot = float(meta["min_lot"])
    if "max_lot" in meta:
        specs.max_lot = float(meta["max_lot"])
    if "lot_step" in meta:
        specs.lot_step = float(meta["lot_step"])
    if specs.point > 0 and specs.pip_size <= 0:
        specs.pip_size = specs.point * 10


# ──────────────────────────────────────────────────────────────────────────────
# Main cycle entry point
# ──────────────────────────────────────────────────────────────────────────────


def merge_market_history(context: AppContext, market: MarketSnapshot) -> None:
    """Merge bridge bars into rolling history and refresh market TF lists in-place."""
    if market.m1:
        context.history.merge("M1", market.m1)

    m1_all = context.history.get("M1")
    if m1_all:
        m5_agg, m15_agg = aggregate_standard(m1_all)
        context.history.merge("M5", m5_agg)
        context.history.merge("M15", m15_agg)

    if market.m5:
        context.history.merge("M5", market.m5)
    if market.m15:
        context.history.merge("M15", market.m15)

    market.m1 = context.history.get("M1")
    market.m5 = context.history.get("M5")
    market.m15 = context.history.get("M15")

    if market.symbol and market.symbol.upper() not in {"", "AUTO"}:
        if context.specs.symbol.upper() in {"AUTO", ""}:
            context.specs.symbol = market.symbol
        _apply_broker_specs(context, market)

    save_history(context.config.paths.history_file, context.history)


def run_cycle(
    context: AppContext,
    market: MarketSnapshot | None = None,
    *,
    shared_regime: RegimeSnapshot | None = None,
) -> CycleAudit:
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
        ok_fresh, reason_fresh = heartbeat_fresh(
            market.heartbeat_at or market.timestamp,
            now,
            max(context.config.limits.heartbeat_max_age_seconds, 90.0),
        )
        if not ok_fresh:
            # Still sync/manage open broker positions on a stale heartbeat.
            reconciled = reconcile(context.state.positions, market.positions or context.state.positions)
            context.state.positions = reconciled.positions
            audit.reasons.append(reconciled.reason)
            if market.account:
                audit.account_number = market.account.account_id
            if context.state.positions:
                stale_regime = RegimeSnapshot(
                    MarketRegime.UNKNOWN,
                    now,
                    reason_fresh,
                    0.0,
                    IndicatorSnapshot(now),
                )
                for pos in list(context.state.positions):
                    action = manage_position(
                        pos,
                        bid=market.bid,
                        ask=market.ask,
                        atr_value=None,
                        regime=stale_regime,
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
                        audit.decision = Decision.CLOSE
                        audit.set_reason(ack.reason)
                    elif action.decision == Decision.MODIFY:
                        cmd = build_modify(pos, action)
                        ack, context.state.positions = context.execution.execute(cmd, context.state.positions)
                        audit.command = cmd
                        audit.execution_result = _ack_to_exec_result(ack)
                        audit.decision = Decision.MODIFY
                        audit.set_reason(ack.reason)
                context.state_store.save(context.state)
            if not audit.decision:
                audit.set_reason(ReasonCode.DATA_STALE, [reason_fresh.value])
                audit.decision = Decision.HOLD
            audit.reasons.append(reason_fresh)
            audit.completed_at = datetime.now(UTC)
            context.audit.write(audit)
            return audit

    # ── Step 3/4: merge history + aggregate higher TF ───────────────────────
    merge_market_history(context, market)
    audit.metrics["m1_count"] = len(market.m1)
    audit.metrics["m15_count"] = len(market.m15)
    if market.symbol and market.symbol.upper() not in {"", "AUTO"}:
        audit.symbol = market.symbol

    # Always sync broker positions first — open trades must be managed even when
    # history/regime is not ready for new entries.
    reconciled = reconcile(context.state.positions, market.positions or context.state.positions)
    context.state.positions = reconciled.positions
    audit.reasons.append(reconciled.reason)
    if market.account:
        audit.account_number = market.account.account_id

    # ── Step 5/6: indicators + regime update ───────────────────────────────
    ok_seq, reason_seq = sequential_bars(market.m15, context.config.instrument.timeframe_decision)
    audit.reasons.append(reason_seq)

    if ok_seq:
        local_regime = context.detector.update(market.m15)
    else:
        # Keep going for management; block only *new* entries via UNKNOWN regime.
        local_regime = RegimeSnapshot(
            MarketRegime.UNKNOWN,
            datetime.now(UTC),
            reason_seq,
            0.0,
            IndicatorSnapshot(datetime.now(UTC)),
        )

    # Same symbol across accounts must share one market regime (richest M15 wins).
    if shared_regime is not None:
        regime = shared_regime
        audit.metrics["regime_source"] = "shared"
        audit.metrics["shared_m15"] = int((shared_regime.metadata or {}).get("shared_m15") or 0)
    else:
        regime = local_regime
        audit.metrics["regime_source"] = "local"

    audit.market_regime = regime.regime
    audit.reasons.append(regime.reason)
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
    if regime.reason == ReasonCode.HISTORY_INSUFFICIENT:
        need = int((regime.metadata or {}).get("need") or context.config.regimes.trend.ema50_period)
        have = int((regime.metadata or {}).get("m15") or (regime.metadata or {}).get("shared_m15") or len(market.m15))
        audit.metrics["warmup_m15"] = have
        audit.metrics["warmup_need"] = need
        # Keep warm-up visible as the primary reason (not overwritten later to REGIME_UNKNOWN alone).
        audit.set_reason(ReasonCode.HISTORY_INSUFFICIENT, [f"m15={have}/{need}"])

    # ── Step 7: expire/update setups ────────────────────────────────────────
    last_bar = last_closed(market.m15)
    if last_bar:
        for setup in expire_setups(context.state.setups.active(symbol=context.specs.symbol), last_bar.time):
            context.state.setups.upsert(setup)
            audit.reasons.append(setup.reason)

    # ── Step 8: position management — ONLY same-symbol (quotes match chart) ──
    active_symbol = audit.symbol or context.specs.symbol
    same_symbol_positions = _positions_for_symbol(context.state.positions, active_symbol)
    other_symbol_count = len(context.state.positions) - len(same_symbol_positions)
    audit.metrics["positions_symbol"] = len(same_symbol_positions)
    audit.metrics["positions_other"] = other_symbol_count

    managed_decision: Decision | None = None
    for pos in list(same_symbol_positions):
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
            managed_decision = Decision.CLOSE
            audit.decision = Decision.CLOSE
            audit.set_reason(ack.reason)
        elif action.decision == Decision.MODIFY:
            cmd = build_modify(pos, action)
            ack, context.state.positions = context.execution.execute(cmd, context.state.positions)
            audit.command = cmd
            audit.execution_result = _ack_to_exec_result(ack)
            audit.reasons.append(ack.reason)
            managed_decision = Decision.MODIFY
            audit.decision = Decision.MODIFY
            audit.set_reason(ack.reason)

        # Update mark-to-market price on surviving positions
        if any(p.position_id == pos.position_id for p in context.state.positions):
            pos.current_price = market.bid if pos.side == Side.BUY else market.ask

    # Refresh after management (closes may free a slot).
    same_symbol_positions = _positions_for_symbol(context.state.positions, active_symbol)
    room_for_entry = len(same_symbol_positions) < context.config.position.max_open_positions

    # ── Step 9: strategy router when flat on THIS symbol (symbol change must not freeze) ─
    if room_for_entry and (
        ok_seq
        or (
            shared_regime is not None
            and shared_regime.regime != MarketRegime.UNKNOWN
            and reason_seq != ReasonCode.BARS_NOT_SEQUENTIAL
        )
    ):
        # Warm-up: do not rewrite HISTORY_INSUFFICIENT into generic REGIME_UNKNOWN.
        if regime.reason == ReasonCode.HISTORY_INSUFFICIENT:
            if managed_decision is None:
                audit.decision = Decision.HOLD
                need = int((regime.metadata or {}).get("need") or context.config.regimes.trend.ema50_period)
                have = int(
                    (regime.metadata or {}).get("m15") or (regime.metadata or {}).get("shared_m15") or len(market.m15)
                )
                audit.set_reason(ReasonCode.HISTORY_INSUFFICIENT, [f"m15={have}/{need}"])
        else:
            result = context.router.evaluate(
                StrategyContext(
                    context.config,
                    context.specs,
                    market,
                    regime,
                    market.account,
                    same_symbol_positions,
                    context.state.setups,
                )
            )
            audit.reasons.append(result.reason)
            audit.signal = result.signal
            if managed_decision is None:
                audit.decision = result.decision

            if result.setup:
                audit.setup_state = result.setup.state

            if result.signal:
                audit.selected_strategy = result.signal.strategy

                # ── Step 10: risk validate ───────────────────────────────────
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
                    # ── Step 11: order command ───────────────────────────────
                    cmd = build_open(result.signal, risk.lot, context.config.execution)
                    ack, context.state.positions = context.execution.execute(cmd, context.state.positions)
                    audit.command = cmd
                    audit.execution_result = _ack_to_exec_result(ack)
                    audit.reasons.append(ack.reason)
                    audit.decision = Decision.OPEN
                    audit.set_reason(ack.reason)

                    # ── Step 12: update limits on accepted trade ─────────────
                    if ack.accepted:
                        record_trade_open(context.state.limits, now)
                        if result.setup is not None:
                            transition(result.setup, SetupState.ORDER_PENDING)
                            result.setup.command_id = cmd.command_id
                            context.state.setups.upsert(result.setup)
                else:
                    audit.failed_conditions = [r.value for r in risk.messages if r != risk.reason]
                    if managed_decision is None:
                        audit.set_reason(risk.reason, audit.failed_conditions or None)
                        audit.decision = Decision.BLOCK
            elif managed_decision is None:
                audit.set_reason(result.reason)
    elif managed_decision is None and same_symbol_positions:
        # Full on this symbol; management had nothing to change this cycle.
        audit.decision = Decision.HOLD
        audit.set_reason(
            ReasonCode.MANAGEMENT_NO_ACTION,
            [f"open={len(same_symbol_positions)} symbol={active_symbol}"],
        )

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
