"""Market data aggregation and indicators."""

from __future__ import annotations

from collections.abc import Sequence

from checktrader.domain.errors import DataError
from checktrader.domain.market import Candle
from checktrader.observability.reason_codes import ReasonCode


def _parse_minute(ts: str) -> tuple[str, int]:
    # Expect ...HH:MM:SS...
    date_part, time_part = ts.split("T", 1)
    hh, mm, rest = time_part.split(":", 2)
    minute = int(hh) * 60 + int(mm)
    return date_part, minute


def aggregate_timeframe(candles: Sequence[Candle], *, minutes: int, timeframe: str) -> list[Candle]:
    if minutes <= 1:
        return [c for c in candles if c.complete]
    buckets: dict[tuple[str, int], list[Candle]] = {}
    order: list[tuple[str, int]] = []
    for candle in candles:
        if not candle.complete:
            continue
        date_part, minute = _parse_minute(candle.open_time_utc)
        bucket_index = minute // minutes
        key = (date_part, bucket_index)
        if key not in buckets:
            buckets[key] = []
            order.append(key)
        buckets[key].append(candle)
    out: list[Candle] = []
    for key in order:
        group = buckets[key]
        if len(group) < minutes:
            # Incomplete bucket — do not mark complete
            continue
        first, last = group[0], group[-1]
        out.append(
            Candle(
                open_time_utc=first.open_time_utc,
                close_time_utc=last.close_time_utc,
                open=first.open,
                high=max(c.high for c in group),
                low=min(c.low for c in group),
                close=last.close,
                tick_volume=sum(c.tick_volume for c in group),
                spread=last.spread,
                complete=True,
                timeframe=timeframe,
            )
        )
    return out


def validate_candle_sequence(candles: Sequence[Candle]) -> None:
    if not candles:
        raise DataError("no candles", reason=ReasonCode.DATA_MISSING)
    seen: set[str] = set()
    prev: str | None = None
    for candle in candles:
        if candle.open_time_utc in seen:
            raise DataError("duplicate candle", reason=ReasonCode.DATA_INVALID, context={"t": candle.open_time_utc})
        seen.add(candle.open_time_utc)
        if prev is not None and candle.open_time_utc <= prev:
            raise DataError("out-of-order candles", reason=ReasonCode.DATA_INVALID)
        prev = candle.open_time_utc


def atr(candles: Sequence[Candle], period: int) -> float | None:
    if len(candles) < period + 1:
        return None
    trs: list[float] = []
    for i in range(1, len(candles)):
        cur, prev = candles[i], candles[i - 1]
        tr = max(cur.high - cur.low, abs(cur.high - prev.close), abs(cur.low - prev.close))
        trs.append(tr)
    window = trs[-period:]
    return sum(window) / period


def wma(values: Sequence[float], period: int) -> float | None:
    if len(values) < period:
        return None
    weights = list(range(1, period + 1))
    window = values[-period:]
    return sum(v * w for v, w in zip(window, weights, strict=True)) / sum(weights)


def hma(values: Sequence[float], period: int) -> float | None:
    if period < 2 or len(values) < period:
        return None
    half = max(period // 2, 1)
    sqrt_p = max(int(period**0.5), 1)
    raw: list[float] = []
    for i in range(period - 1, len(values)):
        slice_vals = values[: i + 1]
        wma_half = wma(slice_vals, half)
        wma_full = wma(slice_vals, period)
        if wma_half is None or wma_full is None:
            continue
        raw.append(2 * wma_half - wma_full)
    return wma(raw, sqrt_p)


def swing_points(
    candles: Sequence[Candle], *, lookback: int = 2
) -> tuple[list[tuple[int, float]], list[tuple[int, float]]]:
    highs: list[tuple[int, float]] = []
    lows: list[tuple[int, float]] = []
    for i in range(lookback, len(candles) - lookback):
        window = candles[i - lookback : i + lookback + 1]
        if candles[i].high == max(c.high for c in window):
            highs.append((i, candles[i].high))
        if candles[i].low == min(c.low for c in window):
            lows.append((i, candles[i].low))
    return highs, lows
