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
    Priority order (section 4 / routing rules):
      1. BREAKOUT — evaluated in any regime except UNKNOWN
      2. TREND_CONTINUATION — only in TREND_UP / TREND_DOWN
      3. RANGE_REVERSION — only in RANGE

    Special regime handling:
      - TRANSITION: only BREAKOUT is considered
      - UNKNOWN: no trades

    Range ARMED setups are cancelled when a confirmed BREAKOUT signal fires.
    One signal per cycle; first Decision.OPEN wins.
    """

    breakout: BreakoutStrategy = field(default_factory=BreakoutStrategy)
    trend: TrendContinuationStrategy = field(default_factory=TrendContinuationStrategy)
    range_reversion: RangeReversionStrategy = field(default_factory=RangeReversionStrategy)

    def evaluate(self, context: StrategyContext) -> StrategyResult:
        regime = context.regime.regime

        # Section 5.5: no trades in UNKNOWN
        if regime == MarketRegime.UNKNOWN:
            return StrategyResult(Decision.HOLD, ReasonCode.REGIME_UNKNOWN)

        # 1. Breakout — highest priority; runs in TREND, RANGE, and TRANSITION
        bo_result = self.breakout.evaluate(context)
        if bo_result.decision == Decision.OPEN:
            # Cancel any ARMED range setups on confirmed breakout
            self._cancel_range_setups(context)
            return bo_result

        # Section 5.4: TRANSITION → only breakout considered
        if regime == MarketRegime.TRANSITION:
            if bo_result.decision == Decision.HOLD and bo_result.reason in {
                ReasonCode.BREAKOUT_RETEST_PENDING,
                ReasonCode.BREAKOUT_BOX_PENDING,
                ReasonCode.NO_BREAKOUT_TRIGGER,
                ReasonCode.FALSE_BREAKOUT,
            }:
                return bo_result
            return StrategyResult(Decision.HOLD, ReasonCode.REGIME_TRANSITION)

        # 2. Trend continuation — TREND_UP / TREND_DOWN only
        if regime in {MarketRegime.TREND_UP, MarketRegime.TREND_DOWN}:
            tr_result = self.trend.evaluate(context)
            if tr_result.decision == Decision.OPEN:
                return tr_result

        # 3. Range reversion — RANGE only
        if regime == MarketRegime.RANGE:
            rr_result = self.range_reversion.evaluate(context)
            if rr_result.decision == Decision.OPEN:
                return rr_result

        # Return the breakout intermediate result if it has useful state
        if bo_result.setup is not None:
            return bo_result

        return StrategyResult(Decision.HOLD, ReasonCode.NO_TRADE)

    @staticmethod
    def _cancel_range_setups(context: StrategyContext) -> None:
        from checktrader.setups.state_machine import transition

        for s in context.setups.active(symbol=context.specs.symbol, strategy=StrategyType.RANGE_REVERSION):
            if s.state in {SetupState.IDLE, SetupState.ARMED}:
                transition(s, SetupState.CANCELLED)
