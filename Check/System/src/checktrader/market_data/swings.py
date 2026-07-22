from __future__ import annotations

from checktrader.domain.enums import Side
from checktrader.domain.models import Candle, SwingPoint
from checktrader.market_data.bars import closed_bars


def confirmed_swings(candles: list[Candle], lookback: int) -> list[SwingPoint]:
    """
    Return confirmed swing highs and lows.

    A swing high at bar `ci` is confirmed when `lookback` bars both before and
    after `ci` all have lower highs (2 bars each side → needs lookback=2).
    No look-ahead: confirmation is only declared once bar `ci + lookback` closes.

    side=SELL → swing high (price reversed downward from here)
    side=BUY  → swing low  (price reversed upward from here)
    """
    bars = closed_bars(candles)
    out: list[SwingPoint] = []
    if lookback <= 0 or len(bars) < lookback * 2 + 1:
        return out
    for current in range(lookback * 2, len(bars)):
        ci = current - lookback
        window = bars[ci - lookback : current + 1]
        c = bars[ci]
        if c.high == max(b.high for b in window):
            out.append(SwingPoint(c.time, c.high, Side.SELL, ci, bars[current].time))
        if c.low == min(b.low for b in window):
            out.append(SwingPoint(c.time, c.low, Side.BUY, ci, bars[current].time))
    return out


def last_swing_low(candles: list[Candle], lookback: int) -> SwingPoint | None:
    return next((s for s in reversed(confirmed_swings(candles, lookback)) if s.side == Side.BUY), None)


def last_swing_high(candles: list[Candle], lookback: int) -> SwingPoint | None:
    return next((s for s in reversed(confirmed_swings(candles, lookback)) if s.side == Side.SELL), None)
