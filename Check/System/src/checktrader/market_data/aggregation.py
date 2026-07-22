from __future__ import annotations

from datetime import datetime
from math import ceil

from checktrader.domain.models import Candle
from checktrader.market_data.bars import closed_bars


def timeframe_minutes(timeframe: str) -> int:
    unit = timeframe[0].upper()
    value = int(timeframe[1:])
    if unit == "M":
        return value
    if unit == "H":
        return value * 60
    raise ValueError(f"unsupported timeframe: {timeframe}")


def bucket_start(ts: datetime, minutes: int) -> datetime:
    return ts.replace(minute=ts.minute - ts.minute % minutes, second=0, microsecond=0)


def aggregate_m1(candles: list[Candle], target_timeframe: str) -> list[Candle]:
    """
    Build higher-TF candles from M1.

    Real broker feeds (e.g. NATURALGAS) often miss minutes inside a bucket.
    Require at least half the expected M1 bars; do not demand perfect 60s spacing.
    """
    minutes = timeframe_minutes(target_timeframe)
    min_bars = max(1, ceil(minutes / 2))
    buckets: dict[datetime, list[Candle]] = {}
    for bar in sorted(closed_bars(candles), key=lambda b: b.time):
        buckets.setdefault(bucket_start(bar.time, minutes), []).append(bar)
    out: list[Candle] = []
    for start, group0 in sorted(buckets.items()):
        group = sorted(group0, key=lambda b: b.time)
        if len(group) < min_bars:
            continue
        out.append(
            Candle(
                start,
                group[0].open,
                max(b.high for b in group),
                min(b.low for b in group),
                group[-1].close,
                sum(b.volume for b in group),
                target_timeframe,
                True,
            )
        )
    return out


def aggregate_standard(candles: list[Candle]) -> tuple[list[Candle], list[Candle]]:
    return aggregate_m1(candles, "M5"), aggregate_m1(candles, "M15")
