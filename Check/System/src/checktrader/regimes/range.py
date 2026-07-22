from __future__ import annotations
from checktrader.config.models import RegimeRangeConfig
from checktrader.domain.enums import MarketRegime, ReasonCode
from checktrader.domain.models import Candle, IndicatorSnapshot, RegimeSnapshot
from checktrader.market_data.bars import closed_bars
from checktrader.market_data.indicators import adx, atr, ema

def detect_range(candles: list[Candle], config: RegimeRangeConfig) -> RegimeSnapshot|None:
    bars=closed_bars(candles)
    if len(bars)<config.lookback_bars: return None
    fast=ema(bars,config.ema_fast_period); slow=ema(bars,config.ema_slow_period); av=atr(bars,config.atr_period); ax,p,m=adx(bars,config.adx_period)
    lf=fast[-1] if fast else None; ls=slow[-1] if slow else None; la=av[-1] if av else None; ladx=ax[-1] if ax else None
    if lf is None or ls is None or la is None or ladx is None or ladx>config.max_adx: return None
    sep=abs(lf-ls)/la if la else 0.0
    if sep>config.max_ema_separation_atr: return None
    w=bars[-config.lookback_bars:]; hi=max(b.high for b in w); lo=min(b.low for b in w); tol=config.boundary_tolerance_atr*la
    if sum(1 for b in w if hi-b.high<=tol)<config.min_touches or sum(1 for b in w if b.low-lo<=tol)<config.min_touches: return None
    ind=IndicatorSnapshot(bars[-1].time,lf,ls,None,la,ladx,p[-1],m[-1],{'range_high':hi,'range_low':lo,'ema_separation_atr':sep})
    return RegimeSnapshot(MarketRegime.RANGE,bars[-1].time,ReasonCode.REGIME_RANGE_CONFIRMED,max(0.0,config.max_ema_separation_atr-sep),ind)
