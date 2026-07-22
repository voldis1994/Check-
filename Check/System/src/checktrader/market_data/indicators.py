from __future__ import annotations
from checktrader.domain.models import Candle, IndicatorSnapshot
from checktrader.market_data.bars import closed_bars, true_range

def ema_values(values: list[float], period: int) -> list[float|None]:
    out=[None]*len(values)
    if period<=0 or len(values)<period: return out
    prev=sum(values[:period])/period; out[period-1]=prev; k=2.0/(period+1.0)
    for i in range(period,len(values)):
        prev=(values[i]-prev)*k+prev; out[i]=prev
    return out
def ema(candles: list[Candle], period: int) -> list[float|None]: return ema_values([b.close for b in closed_bars(candles)], period)
def atr(candles: list[Candle], period: int) -> list[float|None]:
    bars=closed_bars(candles); out=[None]*len(bars)
    if period<=0 or len(bars)<period: return out
    trs=[]; prev=None
    for b in bars: trs.append(true_range(b, prev)); prev=b.close
    val=sum(trs[:period])/period; out[period-1]=val
    for i in range(period,len(trs)):
        val=((val*(period-1))+trs[i])/period; out[i]=val
    return out
def adx(candles: list[Candle], period: int) -> tuple[list[float|None], list[float|None], list[float|None]]:
    bars=closed_bars(candles); adx_out=[None]*len(bars); plus_out=[None]*len(bars); minus_out=[None]*len(bars)
    if period<=0 or len(bars)<period*2: return adx_out, plus_out, minus_out
    tr=[0.0]; plus=[0.0]; minus=[0.0]
    for i in range(1,len(bars)):
        up=bars[i].high-bars[i-1].high; down=bars[i-1].low-bars[i].low
        plus.append(up if up>down and up>0.0 else 0.0); minus.append(down if down>up and down>0.0 else 0.0); tr.append(true_range(bars[i], bars[i-1].close))
    sm_tr=sum(tr[1:period+1]); sm_p=sum(plus[1:period+1]); sm_m=sum(minus[1:period+1]); dx=[None]*len(bars)
    for i in range(period,len(bars)):
        if i>period: sm_tr=sm_tr-sm_tr/period+tr[i]; sm_p=sm_p-sm_p/period+plus[i]; sm_m=sm_m-sm_m/period+minus[i]
        p=100.0*sm_p/sm_tr if sm_tr else 0.0; m=100.0*sm_m/sm_tr if sm_tr else 0.0; plus_out[i]=p; minus_out[i]=m; den=p+m; dx[i]=100.0*abs(p-m)/den if den else 0.0
    vals=[v for v in dx[period:period*2] if v is not None]
    if len(vals)==period:
        idx=period*2-1; val=sum(vals)/period; adx_out[idx]=val
        for i in range(idx+1,len(bars)):
            if dx[i] is not None: val=((val*(period-1))+float(dx[i]))/period; adx_out[i]=val
    return adx_out, plus_out, minus_out
def latest_snapshot(candles: list[Candle], *, ema_fast_period: int, ema_slow_period: int, atr_period: int, adx_period: int, ema_signal_period: int|None=None) -> IndicatorSnapshot:
    bars=closed_bars(candles)
    if not bars: raise ValueError('no closed candles')
    fast=ema(bars, ema_fast_period); slow=ema(bars, ema_slow_period); av=atr(bars, atr_period); ax,p,m=adx(bars, adx_period); sig=ema(bars, ema_signal_period) if ema_signal_period else [None]*len(bars)
    return IndicatorSnapshot(bars[-1].time, fast[-1] if fast else None, slow[-1] if slow else None, sig[-1] if sig else None, av[-1] if av else None, ax[-1] if ax else None, p[-1] if p else None, m[-1] if m else None)
