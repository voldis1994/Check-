"""Strategy router — priority: breakout > trend > range; one signal per cycle."""

from __future__ import annotations

from dataclasses import dataclass, field

from checktrader.domain.enums import Decision, MarketRegime, ReasonCode, SetupState, StrategyType
from checktrader.domain.models import StrategyResult
from checktrader.strategies.base import StrategyContext
from checktrader.strategies.breakout import BreakoutStrategy
from checktrader.strategies.range_reversion import RangeReversionStrategy
from checktrader.strategies.trend_continuation import TrendContinuationStrategy


@dataclass(slots=True)
class StrategyRouter:
    """
    Priority order:
      1. BREAKOUT — evaluated in any regime except UNKNOWN
      2. TREND_CONTINUATION — only in TREND_UP / TREND_DOWN
      3. RANGE_REVERSION — only in RANGE

    Special regime handling:
      - TRANSITION: only BREAKOUT is considered (no trend / range)
      - UNKNOWN: no trades at all

    Range ARMED setups are cancelled when a confirmed BREAKOUT OPEN fires.
    One signal per cycle; first Decision.OPEN wins.
    """

    breakout: BreakoutStrategy = field(default_factory=BreakoutStrategy)
    trend: TrendContinuationStrategy = field(default_factory=TrendContinuationStrategy)
    range_reversion: RangeReversionStrategy = field(default_factory=RangeReversionStrategy)

    def evaluate(self, context: StrategyContext) -> StrategyResult:
        regime = context.regime.regime

        # UNKNOWN → no trades
        if regime == MarketRegime.UNKNOWN:
            return StrategyResult(Decision.HOLD, ReasonCode.REGIME_UNKNOWN)

        # 1. Breakout — highest priority; runs in TREND, RANGE, and TRANSITION
        bo_result = self.breakout.evaluate(context)
        if bo_result.decision == Decision.OPEN:
            # Cancel any ARMED range setups on confirmed breakout
            _cancel_range_setups(context)
            return bo_result

        # TRANSITION → only breakout; do not fall through to trend/range
        if regime == MarketRegime.TRANSITION:
            if bo_result.decision == Decision.HOLD and bo_result.reason in {
                ReasonCode.BREAKOUT_RETEST_PENDING,
                ReasonCode.BREAKOUT_BOX_PENDING,
                ReasonCode.NO_BREAKOUT_TRIGGER,
                ReasonCode.FALSE_BREAKOUT,
                ReasonCode.SETUP_ARMED,
            }:
                return bo_result
            # Breakout skipped or not applicable → generic TRANSITION hold
            return StrategyResult(Decision.HOLD, ReasonCode.REGIME_TRANSITION)

        # 2. Trend continuation — TREND_UP / TREND_DOWN only
        tr_result: StrategyResult | None = None
        if regime in {MarketRegime.TREND_UP, MarketRegime.TREND_DOWN}:
            tr_result = self.trend.evaluate(context)
            if tr_result.decision == Decision.OPEN:
                return tr_result

        # 3. Range reversion — RANGE only
        rr_result: StrategyResult | None = None
        if regime == MarketRegime.RANGE:
            rr_result = self.range_reversion.evaluate(context)
            if rr_result.decision == Decision.OPEN:
                return rr_result

        # Propagate the most-informative HOLD result:
        # breakout ARMED setup > trend ARMED setup > range result > generic NO_TRADE
        if bo_result.setup is not None:
            return bo_result
        if tr_result is not None and tr_result.setup is not None:
            return tr_result
        if rr_result is not None and rr_result.setup is not None:
            return rr_result
        if tr_result is not None:
            return tr_result
        if rr_result is not None:
            return rr_result

        return StrategyResult(Decision.HOLD, ReasonCode.NO_TRADE)


def _cancel_range_setups(context: StrategyContext) -> None:
    from checktrader.setups.state_machine import transition

    for s in context.setups.active(symbol=context.specs.symbol, strategy=StrategyType.RANGE_REVERSION):
        if s.state in {SetupState.IDLE, SetupState.ARMED}:
            transition(s, SetupState.CANCELLED)
            context.setups.upsert(s)
