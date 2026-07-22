"""M1 entry trigger helpers for trend pullback break."""

from __future__ import annotations

from checktrader.domain.enums import Side
from checktrader.domain.market import Candle


def m1_break_triggered(
    *,
    side: Side,
    candle: Candle,
    trigger: float,
    buffer: float,
) -> bool:
    """True when M1 close breaks trigger with buffer and candle direction agrees."""
    if side is Side.BUY:
        return candle.close >= trigger + buffer and candle.close > candle.open
    return candle.close <= trigger - buffer and candle.close < candle.open


__all__ = ["m1_break_triggered"]
