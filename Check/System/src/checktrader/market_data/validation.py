from __future__ import annotations
from datetime import datetime, timedelta
from checktrader.domain.enums import ReasonCode
from checktrader.domain.models import Candle
from checktrader.market_data.aggregation import timeframe_minutes
from checktrader.market_data.bars import closed_bars

def sequential_bars(candles: list[Candle], timeframe: str) -> tuple[bool, ReasonCode]:
    bars=sorted(closed_bars(candles), key=lambda b:b.time)
    if not bars: return False, ReasonCode.NO_CLOSED_BARS
    exp=timedelta(minutes=timeframe_minutes(timeframe))
    return (False, ReasonCode.BARS_NOT_SEQUENTIAL) if any(bars[i].time-bars[i-1].time != exp for i in range(1,len(bars))) else (True, ReasonCode.DATA_VALID)
def fresh_enough(last_bar: Candle|None, now: datetime, max_age_seconds: float) -> tuple[bool, ReasonCode]:
    if last_bar is None: return False, ReasonCode.MARKET_DATA_MISSING
    return (False, ReasonCode.MARKET_DATA_STALE) if (now-last_bar.time).total_seconds()>max_age_seconds else (True, ReasonCode.DATA_VALID)
