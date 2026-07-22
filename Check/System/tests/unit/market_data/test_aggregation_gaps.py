from __future__ import annotations

from datetime import UTC, datetime, timedelta

from checktrader.domain.models import Candle
from checktrader.market_data.aggregation import aggregate_m1


def _m1(ts: datetime, price: float = 1.0) -> Candle:
    return Candle(ts, price, price + 0.1, price - 0.1, price, 1.0, "M1", True)


def test_aggregate_m1_allows_incomplete_naturalgas_bucket() -> None:
    t0 = datetime(2026, 7, 22, 10, 0, tzinfo=UTC)
    # Only 8 of 15 M1 bars present in the first M15 bucket (common on NATURALGAS).
    bars = [_m1(t0 + timedelta(minutes=i), 100 + i * 0.01) for i in (0, 1, 2, 3, 5, 7, 9, 12)]
    m15 = aggregate_m1(bars, "M15")
    assert len(m15) == 1
    assert m15[0].time == t0
    assert m15[0].open == bars[0].open
    assert m15[0].close == bars[-1].close


def test_aggregate_m1_skips_almost_empty_bucket() -> None:
    t0 = datetime(2026, 7, 22, 10, 0, tzinfo=UTC)
    bars = [_m1(t0), _m1(t0 + timedelta(minutes=1))]
    assert aggregate_m1(bars, "M15") == []
