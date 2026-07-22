"""Shared exit-level helpers for strategy OPEN signals."""

from __future__ import annotations

from checktrader.domain.enums import Side


def hard_take_profit_price(
    *,
    entry: float,
    stop: float,
    side: Side,
    rr: float,
    enabled: bool,
) -> float | None:
    """Fixed TP only when management.hard_take_profit is on; else trail manages exit."""
    if not enabled:
        return None
    risk = abs(entry - stop)
    if risk <= 0.0 or rr <= 0.0:
        return None
    if side == Side.BUY:
        return entry + risk * rr
    return entry - risk * rr
