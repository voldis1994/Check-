from __future__ import annotations
from datetime import timedelta
from checktrader.domain.enums import Decision, ReasonCode, SetupState, Side, StrategyType
from checktrader.domain.models import Setup, StrategyResult, StrategySignal
from checktrader.market_data.aggregation import timeframe_minutes
from checktrader.market_data.bars import closed_bars
from checktrader.market_data.indicators import adx, atr
from checktrader.setups.state_machine import transition
from checktrader.strategies.base import StrategyContext
class BreakoutStrategy:
    def evaluate(self, context: StrategyContext) -> StrategyResult:
        cfg=context.config.strategies.breakout; bars=closed_bars(context.m15); required=cfg.box_lookback_bars+1
        if not cfg.enabled: return StrategyResult(Decision.SKIP,ReasonCode.NO_STRATEGY_FOR_REGIME)
        if len(bars)<required: return StrategyResult(Decision.HOLD,ReasonCode.BREAKOUT_FILTERS_NOT_READY)
        av=atr(bars,context.config.regimes.trend.atr_period); ax,_,_=adx(bars,context.config.regimes.trend.adx_period); a=av[-1] if av else None; x=ax[-1] if ax else None
        if a is None or x is None or x<cfg.min_adx: return StrategyResult(Decision.HOLD,ReasonCode.BREAKOUT_FILTERS_NOT_READY)
        last=bars[-1]
        for setup in context.setups.active(symbol=context.specs.symbol, strategy=StrategyType.BREAKOUT):
            tol=cfg.retest_tolerance_atr*a
            if setup.side==Side.LONG and last.low<=setup.trigger_price+tol and last.close>=setup.trigger_price:
                transition(setup,SetupState.READY); transition(setup,SetupState.TRIGGERED); return StrategyResult(Decision.OPEN,ReasonCode.BREAKOUT_LONG_SIGNAL,StrategySignal(StrategyType.BREAKOUT,Side.LONG,context.specs.symbol,context.market.ask,setup.stop_loss,setup.take_profit,ReasonCode.BREAKOUT_LONG_SIGNAL,setup.setup_id),setup)
            if setup.side==Side.SHORT and last.high>=setup.trigger_price-tol and last.close<=setup.trigger_price:
                transition(setup,SetupState.READY); transition(setup,SetupState.TRIGGERED); return StrategyResult(Decision.OPEN,ReasonCode.BREAKOUT_SHORT_SIGNAL,StrategySignal(StrategyType.BREAKOUT,Side.SHORT,context.specs.symbol,context.market.bid,setup.stop_loss,setup.take_profit,ReasonCode.BREAKOUT_SHORT_SIGNAL,setup.setup_id),setup)
        box=bars[-required:-1]; hi=max(b.high for b in box); lo=min(b.low for b in box); width=hi-lo; width_atr=width/a if a else 0.0
        if width_atr<cfg.min_box_atr or width_atr>cfg.max_box_atr: return StrategyResult(Decision.HOLD,ReasonCode.BREAKOUT_BOX_PENDING,diagnostics={'box_width_atr':width_atr})
        expiry=last.time+timedelta(minutes=timeframe_minutes(context.config.instrument.timeframe_decision)*cfg.setup_expiry_bars); buffer=cfg.breakout_buffer_atr*a
        if last.close>hi+buffer:
            entry=context.market.ask; stop=lo-cfg.stop_buffer_atr*a; tp=entry+(entry-stop)*cfg.take_profit_rr
            if cfg.retest_required:
                setup=Setup.create(context.specs.symbol,StrategyType.BREAKOUT,Side.LONG,SetupState.WAITING_CONFIRMATION,last.time,expiry,hi,stop,tp,ReasonCode.SETUP_WAITING_CONFIRMATION,{'box_high':hi,'box_low':lo}); context.setups.upsert(setup); return StrategyResult(Decision.HOLD,ReasonCode.SETUP_WAITING_CONFIRMATION,setup=setup)
            return StrategyResult(Decision.OPEN,ReasonCode.BREAKOUT_LONG_SIGNAL,StrategySignal(StrategyType.BREAKOUT,Side.LONG,context.specs.symbol,entry,stop,tp,ReasonCode.BREAKOUT_LONG_SIGNAL))
        if last.close<lo-buffer:
            entry=context.market.bid; stop=hi+cfg.stop_buffer_atr*a; tp=entry-(stop-entry)*cfg.take_profit_rr
            if cfg.retest_required:
                setup=Setup.create(context.specs.symbol,StrategyType.BREAKOUT,Side.SHORT,SetupState.WAITING_CONFIRMATION,last.time,expiry,lo,stop,tp,ReasonCode.SETUP_WAITING_CONFIRMATION,{'box_high':hi,'box_low':lo}); context.setups.upsert(setup); return StrategyResult(Decision.HOLD,ReasonCode.SETUP_WAITING_CONFIRMATION,setup=setup)
            return StrategyResult(Decision.OPEN,ReasonCode.BREAKOUT_SHORT_SIGNAL,StrategySignal(StrategyType.BREAKOUT,Side.SHORT,context.specs.symbol,entry,stop,tp,ReasonCode.BREAKOUT_SHORT_SIGNAL))
        return StrategyResult(Decision.HOLD,ReasonCode.NO_BREAKOUT_TRIGGER)
