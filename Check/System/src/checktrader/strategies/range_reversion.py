from __future__ import annotations
from checktrader.domain.enums import Decision, MarketRegime, ReasonCode, Side, StrategyType
from checktrader.domain.models import StrategyResult, StrategySignal
from checktrader.market_data.bars import closed_bars
from checktrader.market_data.indicators import adx, atr
from checktrader.strategies.base import StrategyContext
class RangeReversionStrategy:
    def evaluate(self, context: StrategyContext) -> StrategyResult:
        cfg=context.config.strategies.range_reversion
        if not cfg.enabled or context.regime.regime!=MarketRegime.RANGE: return StrategyResult(Decision.SKIP,ReasonCode.NO_STRATEGY_FOR_REGIME)
        bars=closed_bars(context.m15)
        if len(bars)<cfg.lookback_bars: return StrategyResult(Decision.HOLD,ReasonCode.RANGE_FILTERS_NOT_READY)
        av=atr(bars,context.config.regimes.range.atr_period); ax,_,_=adx(bars,context.config.regimes.range.adx_period); a=av[-1] if av else None; x=ax[-1] if ax else None
        if a is None or x is None or x>cfg.max_adx: return StrategyResult(Decision.HOLD,ReasonCode.RANGE_FILTERS_NOT_READY)
        w=bars[-cfg.lookback_bars:]; hi=max(b.high for b in w); lo=min(b.low for b in w); width=hi-lo
        if width<cfg.min_range_atr*a: return StrategyResult(Decision.HOLD,ReasonCode.RANGE_FILTERS_NOT_READY)
        last=bars[-1]; tol=cfg.boundary_tolerance_atr*a; loc=(last.close-last.low)/(last.high-last.low) if last.high!=last.low else cfg.rejection_close_fraction
        if last.low<=lo+tol and loc>=cfg.rejection_close_fraction:
            entry=context.market.ask; stop=lo-cfg.stop_buffer_atr*a; tp=lo+width*cfg.take_profit_fraction
            return StrategyResult(Decision.OPEN,ReasonCode.RANGE_LONG_SIGNAL,StrategySignal(StrategyType.RANGE_REVERSION,Side.LONG,context.specs.symbol,entry,stop,tp,ReasonCode.RANGE_LONG_SIGNAL))
        if last.high>=hi-tol and loc<=1.0-cfg.rejection_close_fraction:
            entry=context.market.bid; stop=hi+cfg.stop_buffer_atr*a; tp=hi-width*cfg.take_profit_fraction
            return StrategyResult(Decision.OPEN,ReasonCode.RANGE_SHORT_SIGNAL,StrategySignal(StrategyType.RANGE_REVERSION,Side.SHORT,context.specs.symbol,entry,stop,tp,ReasonCode.RANGE_SHORT_SIGNAL))
        return StrategyResult(Decision.HOLD,ReasonCode.NO_RANGE_BOUNDARY_REJECTION)
