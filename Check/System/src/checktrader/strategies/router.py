from __future__ import annotations
from dataclasses import dataclass, field
from checktrader.domain.enums import Decision, ReasonCode
from checktrader.domain.models import StrategyResult
from checktrader.strategies.base import StrategyContext
from checktrader.strategies.breakout import BreakoutStrategy
from checktrader.strategies.range_reversion import RangeReversionStrategy
from checktrader.strategies.trend_continuation import TrendContinuationStrategy
@dataclass(slots=True)
class StrategyRouter:
    breakout: BreakoutStrategy=field(default_factory=BreakoutStrategy); trend: TrendContinuationStrategy=field(default_factory=TrendContinuationStrategy); range_reversion: RangeReversionStrategy=field(default_factory=RangeReversionStrategy)
    def evaluate(self, context: StrategyContext) -> StrategyResult:
        diag={}
        for name,strat in (('breakout',self.breakout),('trend',self.trend),('range',self.range_reversion)):
            r=strat.evaluate(context); diag[name]=r.reason.value
            if r.signal is not None and r.decision==Decision.OPEN: r.diagnostics.update(diag); return r
            if r.setup is not None: r.diagnostics.update(diag); return r
        return StrategyResult(Decision.HOLD,ReasonCode.NO_STRATEGY_FOR_REGIME,diagnostics=diag)
