from __future__ import annotations
from datetime import datetime
from checktrader.domain.models import Candle

def closed_bars(candles: list[Candle]) -> list[Candle]: return [b for b in candles if b.closed]
def last_closed(candles: list[Candle]) -> Candle|None: return next((b for b in reversed(candles) if b.closed), None)
def body(c: Candle) -> float: return abs(c.close-c.open)
def upper_wick(c: Candle) -> float: return c.high-max(c.open,c.close)
def lower_wick(c: Candle) -> float: return min(c.open,c.close)-c.low
def is_bullish(c: Candle) -> bool: return c.close > c.open
def is_bearish(c: Candle) -> bool: return c.close < c.open
def typical_price(c: Candle) -> float: return (c.high+c.low+c.close)/3.0
def true_range(c: Candle, prev_close: float|None) -> float: return c.high-c.low if prev_close is None else max(c.high-c.low, abs(c.high-prev_close), abs(c.low-prev_close))
def points_between(a: float, b: float, point: float) -> float: return abs(a-b)/point
def sort_unique(candles: list[Candle]) -> list[Candle]:
    by_time: dict[datetime,Candle] = {c.time:c for c in candles}
    return [by_time[t] for t in sorted(by_time)]
