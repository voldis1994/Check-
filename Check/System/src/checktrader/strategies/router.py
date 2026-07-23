"""Strategy router — priority: breakout > trend > range; idle HOLD becomes force entry."""

from __future__ import annotations

from dataclasses import dataclass, field

from checktrader.domain.enums import Decision, MarketRegime, ReasonCode, SetupState, Side, StrategyType
from checktrader.domain.models import StrategyResult, StrategySignal
from checktrader.management.atr_stops import atr_for_stops, stop_target_distance
from checktrader.market_data.bars import closed_bars
from checktrader.strategies.base import StrategyContext
from checktrader.strategies.breakout import BreakoutStrategy
from checktrader.strategies.exits import hard_take_profit_price
from checktrader.strategies.range_reversion import RangeReversionStrategy
from checktrader.strategies.trend_continuation import TrendContinuationStrategy


@dataclass(slots=True)
class StrategyRouter:
    """
    Priority: BREAKOUT → TREND → RANGE.

    If nothing OPENs and force_entry_when_idle is on, open M1 momentum
    instead of returning idle HOLD (NO_BREAKOUT_TRIGGER / NO_TRADE / TRANSITION).
    """

    breakout: BreakoutStrategy = field(default_factory=BreakoutStrategy)
    trend: TrendContinuationStrategy = field(default_factory=TrendContinuationStrategy)
    range_reversion: RangeReversionStrategy = field(default_factory=RangeReversionStrategy)

    def evaluate(self, context: StrategyContext) -> StrategyResult:
        regime = context.regime.regime
        scfg = context.config.strategies

        # 1. Breakout
        bo_result = self.breakout.evaluate(context)
        if bo_result.decision == Decision.OPEN:
            _cancel_range_setups(context)
            return bo_result

        # 2. Trend (including TRANSITION / soft TREND)
        tr_result: StrategyResult | None = None
        if regime in {MarketRegime.TREND_UP, MarketRegime.TREND_DOWN, MarketRegime.TRANSITION, MarketRegime.UNKNOWN}:
            tr_result = self.trend.evaluate(context)
            if tr_result.decision == Decision.OPEN:
                return tr_result

        # 3. Range
        rr_result: StrategyResult | None = None
        if regime == MarketRegime.RANGE:
            rr_result = self.range_reversion.evaluate(context)
            if rr_result.decision == Decision.OPEN:
                return rr_result

        # Armed setups waiting forever → force path below instead of HOLD
        if scfg.force_entry_when_idle:
            forced = _force_m1_entry(context)
            if forced is not None:
                _cancel_range_setups(context)
                return forced

        if bo_result.setup is not None:
            return bo_result
        if tr_result is not None and tr_result.setup is not None:
            return tr_result
        if rr_result is not None and rr_result.setup is not None:
            return rr_result
        if bo_result.decision != Decision.SKIP:
            return bo_result
        if tr_result is not None and tr_result.decision != Decision.SKIP:
            return tr_result
        if rr_result is not None:
            return rr_result
        return StrategyResult(Decision.HOLD, ReasonCode.MARKET_DATA_MISSING)


def _force_m1_entry(context: StrategyContext) -> StrategyResult | None:
    scfg = context.config.strategies
    m1 = closed_bars(context.m1)
    if len(m1) < 2:
        return None

    a = atr_for_stops(m15=context.m15, m5=context.m5, m1=context.m1, period=14)
    if a is None or a <= 0:
        ra = context.regime.indicators.atr
        if ra is not None and ra > 0:
            a = float(ra)
    if a is None or a <= 0:
        # Last resort: short M1 TR mean, capped to 1% of price (blocks insane SL).
        window = m1[-min(15, len(m1)) :]
        if not window:
            return None
        raw = sum(b.high - b.low for b in window) / len(window)
        mid = context.market.mid or window[-1].close
        a = min(raw, mid * 0.01) if mid > 0 else raw
    if a is None or a <= 0:
        return None

    last = m1[-1]
    prev = m1[-2]
    bullish = last.close >= last.open and last.close >= prev.close
    bearish = last.close <= last.open and last.close <= prev.close
    if not bullish and not bearish:
        # Flat doji — lean with last close vs open, else vs prev close
        bullish = last.close >= prev.close
        bearish = not bullish

    stop_dist = stop_target_distance(context.specs, scfg, a)
    if bullish:
        entry = context.market.ask
        stop = entry - stop_dist
        tp = hard_take_profit_price(
            entry=entry,
            stop=stop,
            side=Side.BUY,
            rr=scfg.force_tp_rr,
            enabled=context.config.management.hard_take_profit,
        )
        return StrategyResult(
            Decision.OPEN,
            ReasonCode.FORCE_MOMENTUM_BUY,
            StrategySignal(
                StrategyType.BREAKOUT,
                Side.BUY,
                context.specs.symbol,
                entry,
                stop,
                tp,
                ReasonCode.FORCE_MOMENTUM_BUY,
            ),
            diagnostics={"mode": "force_idle", "atr": a, "m1_close": last.close},
        )

    entry = context.market.bid
    stop = entry + stop_dist
    tp = hard_take_profit_price(
        entry=entry,
        stop=stop,
        side=Side.SELL,
        rr=scfg.force_tp_rr,
        enabled=context.config.management.hard_take_profit,
    )
    return StrategyResult(
        Decision.OPEN,
        ReasonCode.FORCE_MOMENTUM_SELL,
        StrategySignal(
            StrategyType.BREAKOUT,
            Side.SELL,
            context.specs.symbol,
            entry,
            stop,
            tp,
            ReasonCode.FORCE_MOMENTUM_SELL,
        ),
        diagnostics={"mode": "force_idle", "atr": a, "m1_close": last.close},
    )


def _cancel_range_setups(context: StrategyContext) -> None:
    from checktrader.setups.state_machine import transition

    for s in context.setups.active(symbol=context.specs.symbol, strategy=StrategyType.RANGE_REVERSION):
        if s.state in {SetupState.IDLE, SetupState.ARMED}:
            transition(s, SetupState.CANCELLED)
            context.setups.upsert(s)
