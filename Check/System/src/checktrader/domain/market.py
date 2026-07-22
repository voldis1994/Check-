"""Market domain models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Candle:
    open_time_utc: str
    close_time_utc: str
    open: float
    high: float
    low: float
    close: float
    tick_volume: float
    spread: float
    complete: bool
    timeframe: str


@dataclass(frozen=True, slots=True)
class TickQuote:
    bid: float
    ask: float
    time_utc: str
    spread_points: float
    spread_pips: float
