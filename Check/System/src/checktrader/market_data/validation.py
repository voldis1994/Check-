from __future__ import annotations

from datetime import datetime

from checktrader.domain.enums import ReasonCode
from checktrader.domain.models import Candle
from checktrader.market_data.aggregation import timeframe_minutes
from checktrader.market_data.bars import closed_bars


def sequential_bars(candles: list[Candle], timeframe: str) -> tuple[bool, ReasonCode]:
    """
    Require closed bars to be ordered without overlap/duplication.

    Session gaps (weekends, NATURALGAS closes, missing buckets) are allowed when
    the gap is an exact multiple of the timeframe. Reject only broken spacing:
    zero/negative deltas or gaps that are not timeframe-aligned.
    """
    bars = sorted(closed_bars(candles), key=lambda b: b.time)
    if not bars:
        return False, ReasonCode.NO_CLOSED_BARS
    step = timeframe_minutes(timeframe) * 60
    for i in range(1, len(bars)):
        delta = (bars[i].time - bars[i - 1].time).total_seconds()
        if delta <= 0:
            return False, ReasonCode.BARS_NOT_SEQUENTIAL
        # Allow 1x, 2x, 3x... period gaps (sessions / dropped incomplete buckets).
        if abs(delta / step - round(delta / step)) > 1e-6:
            return False, ReasonCode.BARS_NOT_SEQUENTIAL
    return True, ReasonCode.DATA_VALID



def fresh_enough(last_bar: Candle | None, now: datetime, max_age_seconds: float) -> tuple[bool, ReasonCode]:
    if last_bar is None:
        return False, ReasonCode.MARKET_DATA_MISSING
    return (
        (False, ReasonCode.MARKET_DATA_STALE)
        if (now - last_bar.time).total_seconds() > max_age_seconds
        else (True, ReasonCode.DATA_VALID)
    )
