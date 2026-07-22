from __future__ import annotations
from checktrader.config.models import InstrumentConfig, RegimeTrendConfig
from checktrader.domain.enums import MarketRegime, ReasonCode
from checktrader.domain.models import Candle, IndicatorSnapshot, RegimeSnapshot
from checktrader.market_data.bars import closed_bars
from checktrader.market_data.indicators import adx, atr, ema

def detect_trend(candles: list[Candle], config: RegimeTrendConfig, instrument: InstrumentConfig) -> RegimeSnapshot|None:
    bars=closed_bars(candles)
    if not bars: return None
    fast=ema(bars,config.ema_fast_period); slow=ema(bars,config.ema_slow_period); av=atr(bars,config.atr_period); ax,p,m=adx(bars,config.adx_period)
    lf=fast[-1] if fast else None; ls=slow[-1] if slow else None; la=av[-1] if av else None; ladx=ax[-1] if ax else None
    if lf is None or ls is None or la is None or ladx is None or ladx<config.min_adx: return None
    sep=abs(lf-ls)/la if la else 0.0; slope_idx=len(fast)-config.confirmation_bars-1
    if sep<config.min_ema_separation_atr or slope_idx<0 or fast[slope_idx] is None: return None
    slope=(lf-float(fast[slope_idx]))/instrument.point
    ind=IndicatorSnapshot(bars[-1].time, lf, ls, None, la, ladx, p[-1], m[-1], {'ema_separation_atr':sep,'ema_slope_points':slope})
    if lf>ls and slope>=config.min_slope_points: return RegimeSnapshot(MarketRegime.TREND_UP,bars[-1].time,ReasonCode.REGIME_TREND_UP_CONFIRMED,sep,ind)
    if lf<ls and slope<=-config.min_slope_points: return RegimeSnapshot(MarketRegime.TREND_DOWN,bars[-1].time,ReasonCode.REGIME_TREND_DOWN_CONFIRMED,sep,ind)
    return None
