from __future__ import annotations
from checktrader.domain.enums import Decision, MarketRegime, ReasonCode, Side, StrategyType
from checktrader.domain.models import StrategyResult, StrategySignal
from checktrader.market_data.bars import closed_bars
from checktrader.market_data.indicators import adx, atr, ema
from checktrader.market_data.swings import last_swing_high, last_swing_low
from checktrader.strategies.base import StrategyContext
class TrendContinuationStrategy:
    def evaluate(self, context: StrategyContext) -> StrategyResult:
        cfg=context.config.strategies.trend_continuation; regime=context.regime.regime
        if not cfg.enabled or (cfg.require_regime_alignment and regime not in {MarketRegime.TREND_UP,MarketRegime.TREND_DOWN}): return StrategyResult(Decision.SKIP,ReasonCode.NO_STRATEGY_FOR_REGIME)
        bars=closed_bars(context.m15)
        if len(bars)<max(cfg.pullback_ema_period, context.config.regimes.trend.adx_period, context.config.regimes.trend.atr_period): return StrategyResult(Decision.HOLD,ReasonCode.TREND_FILTERS_NOT_READY)
        ev=ema(bars,cfg.pullback_ema_period); av=atr(bars,context.config.regimes.trend.atr_period); ax,_,_=adx(bars,context.config.regimes.trend.adx_period); e=ev[-1]; a=av[-1]; x=ax[-1]
        if e is None or a is None or x is None or x<cfg.min_adx: return StrategyResult(Decision.HOLD,ReasonCode.TREND_FILTERS_NOT_READY)
        last=bars[-1]; close_buffer=cfg.min_close_beyond_ema_points*context.specs.point; allowance=cfg.max_pullback_atr*a
        if regime==MarketRegime.TREND_UP and last.low<=e+allowance and last.close>=e+close_buffer:
            swing=last_swing_low(bars,cfg.swing_lookback); stop=min(swing.price if swing else last.low, last.close-cfg.stop_atr_multiplier*a); entry=context.market.ask+cfg.entry_buffer_points*context.specs.point; tp=entry+(entry-stop)*cfg.take_profit_rr
            return StrategyResult(Decision.OPEN,ReasonCode.TREND_LONG_SIGNAL,StrategySignal(StrategyType.TREND_CONTINUATION,Side.LONG,context.specs.symbol,entry,stop,tp,ReasonCode.TREND_LONG_SIGNAL))
        if regime==MarketRegime.TREND_DOWN and last.high>=e-allowance and last.close<=e-close_buffer:
            swing=last_swing_high(bars,cfg.swing_lookback); stop=max(swing.price if swing else last.high, last.close+cfg.stop_atr_multiplier*a); entry=context.market.bid-cfg.entry_buffer_points*context.specs.point; tp=entry-(stop-entry)*cfg.take_profit_rr
            return StrategyResult(Decision.OPEN,ReasonCode.TREND_SHORT_SIGNAL,StrategySignal(StrategyType.TREND_CONTINUATION,Side.SHORT,context.specs.symbol,entry,stop,tp,ReasonCode.TREND_SHORT_SIGNAL))
        return StrategyResult(Decision.HOLD,ReasonCode.NO_TREND_PULLBACK_CONFIRMATION)
