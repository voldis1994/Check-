from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from checktrader.app.bootstrap import AppContext
from checktrader.domain.enums import Decision, ReasonCode, Side
from checktrader.domain.models import AccountStatus, CycleAudit, MarketSnapshot
from checktrader.execution.commands import build_close, build_modify, build_open
from checktrader.execution.reconciliation import reconcile
from checktrader.management.manager import manage_position
from checktrader.market_data.aggregation import aggregate_standard
from checktrader.market_data.bars import last_closed
from checktrader.market_data.history import save_history
from checktrader.market_data.validation import sequential_bars
from checktrader.risk.limits import record_trade_open
from checktrader.risk.validator import validate_order
from checktrader.setups.expiry import expire_setups
from checktrader.strategies.base import StrategyContext


def _paper_market(context: AppContext) -> MarketSnapshot:
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
        AccountStatus(context.config.account.account_id, 100000.0, 100000.0, 100000.0, context.config.account.currency),
        context.state.positions,
        datetime.now(UTC),
    )


def run_cycle(context: AppContext, market: MarketSnapshot | None = None) -> CycleAudit:
    now = datetime.now(UTC)
    market = market or _paper_market(context)
    audit = CycleAudit(uuid4().hex, now, symbol=context.specs.symbol, reasons=[ReasonCode.CYCLE_STARTED])
    if market.m1:
        context.history.merge("M1", market.m1)
        m5, m15 = aggregate_standard(context.history.get("M1"))
        context.history.merge("M5", m5)
        context.history.merge("M15", m15)
    if market.m5:
        context.history.merge("M5", market.m5)
    if market.m15:
        context.history.merge("M15", market.m15)
    market.m1 = context.history.get("M1")
    market.m5 = context.history.get("M5")
    market.m15 = context.history.get("M15")
    ok, reason = sequential_bars(market.m15, context.config.instrument.timeframe_decision)
    audit.reasons.append(reason)
    if not ok:
        audit.completed_at = datetime.now(UTC)
        context.audit.write(audit)
        return audit
    regime = context.detector.update(market.m15)
    audit.regime = regime.regime
    audit.reasons.append(regime.reason)
    last = last_closed(market.m15)
    if last:
        for setup in expire_setups(context.state.setups.active(symbol=context.specs.symbol), last.time):
            context.state.setups.upsert(setup)
            audit.reasons.append(setup.reason)
    reconciled = reconcile(context.state.positions, market.positions or context.state.positions)
    context.state.positions = reconciled.positions
    audit.reasons.append(reconciled.reason)
    if context.state.positions:
        pos = context.state.positions[0]
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
            ack, positions = context.execution.execute(cmd, context.state.positions)
            context.state.positions = positions
            audit.command = cmd
            audit.reasons.append(ack.reason)
        elif action.decision == Decision.MODIFY:
            cmd = build_modify(pos, action)
            ack, positions = context.execution.execute(cmd, context.state.positions)
            context.state.positions = positions
            audit.command = cmd
            audit.reasons.append(ack.reason)
        pos.current_price = market.bid if pos.side == Side.BUY else market.ask
    else:
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
        if result.signal:
            audit.strategy = result.signal.strategy
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
            audit.risk = risk
            audit.reasons.extend(risk.messages)
            if risk.allowed:
                cmd = build_open(result.signal, risk.lot, context.config.execution)
                ack, positions = context.execution.execute(cmd, context.state.positions)
                context.state.positions = positions
                audit.command = cmd
                audit.reasons.append(ack.reason)
                record_trade_open(context.state.limits, now)
    save_history(context.config.paths.history_file, context.history)
    context.state_store.save(context.state)
    context.metrics.inc("cycles")
    context.metrics.save(context.config.paths.metrics_file)
    audit.reasons.append(ReasonCode.CYCLE_COMPLETED)
    audit.completed_at = datetime.now(UTC)
    context.audit.write(audit)
    return audit
