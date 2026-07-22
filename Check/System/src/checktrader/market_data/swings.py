from __future__ import annotations
from checktrader.domain.enums import Side
from checktrader.domain.models import Candle, SwingPoint
from checktrader.market_data.bars import closed_bars

def confirmed_swings(candles: list[Candle], lookback: int) -> list[SwingPoint]:
    bars=closed_bars(candles); out=[]
    if lookback<=0 or len(bars)<lookback*2+1: return out
    for current in range(lookback*2, len(bars)):
        ci=current-lookback; window=bars[ci-lookback:current+1]; c=bars[ci]
        if c.high == max(b.high for b in window): out.append(SwingPoint(c.time,c.high,Side.SHORT,ci,bars[current].time))
        if c.low == min(b.low for b in window): out.append(SwingPoint(c.time,c.low,Side.LONG,ci,bars[current].time))
    return out
def last_swing_low(candles: list[Candle], lookback: int) -> SwingPoint|None: return next((s for s in reversed(confirmed_swings(candles,lookback)) if s.side==Side.LONG), None)
def last_swing_high(candles: list[Candle], lookback: int) -> SwingPoint|None: return next((s for s in reversed(confirmed_swings(candles,lookback)) if s.side==Side.SHORT), None)
