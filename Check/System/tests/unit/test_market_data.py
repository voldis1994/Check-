"""Market data loader / aggregation / freshness tests."""

from __future__ import annotations

import pytest

from checktrader.domain.errors import DataError
from checktrader.market_data.aggregator import aggregate_timeframe, validate_candle_sequence
from checktrader.market_data.freshness import age_ms, is_stale
from checktrader.market_data.loader import parse_market_snapshot
from checktrader.observability.reason_codes import ReasonCode
from tests.fixtures.candles import candle_dicts, sequential_m1, with_incomplete_last
from tests.fixtures.helpers import eurusd_market_payload


def test_m1_order_and_parse() -> None:
    bars = sequential_m1(n=10)
    snap = parse_market_snapshot(eurusd_market_payload(bars_m1=candle_dicts(bars)))
    assert len(snap.bars_m1) == 10
    assert snap.bars_m1[0].open_time_utc < snap.bars_m1[-1].open_time_utc
    validate_candle_sequence(snap.bars_m1)


def test_duplicate_candles_rejected() -> None:
    bars = sequential_m1(n=5)
    bad = list(bars) + [bars[-1]]
    with pytest.raises(DataError) as exc:
        validate_candle_sequence(bad)
    assert exc.value.reason is ReasonCode.DATA_INVALID


def test_missing_bars_field_rejected() -> None:
    payload = eurusd_market_payload(bars_m1=candle_dicts(sequential_m1(n=3)))
    del payload["bars_m1"]
    with pytest.raises(DataError) as exc:
        parse_market_snapshot(payload)
    assert exc.value.reason is ReasonCode.DATA_MISSING


def test_m5_m15_aggregation() -> None:
    bars = sequential_m1(n=30)
    m5 = aggregate_timeframe(bars, minutes=5, timeframe="M5")
    m15 = aggregate_timeframe(bars, minutes=15, timeframe="M15")
    assert len(m5) == 6
    assert len(m15) == 2
    assert m5[0].timeframe == "M5"
    assert m15[0].timeframe == "M15"
    assert m5[0].open == bars[0].open
    assert m5[0].close == bars[4].close
    assert m5[0].high == max(c.high for c in bars[:5])


def test_incomplete_bucket_skipped() -> None:
    bars = sequential_m1(n=7)  # one full M5 + 2 leftover
    m5 = aggregate_timeframe(bars, minutes=5, timeframe="M5")
    assert len(m5) == 1


def test_incomplete_bar_excluded_from_aggregation() -> None:
    bars = with_incomplete_last(sequential_m1(n=5))
    m5 = aggregate_timeframe(bars, minutes=5, timeframe="M5")
    assert m5 == []


def test_stale_data_detection() -> None:
    assert age_ms("2026-03-01T12:00:00Z", "2026-03-01T12:00:02Z") == 2000
    assert is_stale(
        generated_at_utc="2026-03-01T12:00:00Z",
        now_utc="2026-03-01T12:00:03Z",
        maximum_age_ms=1500,
    )
    assert not is_stale(
        generated_at_utc="2026-03-01T12:00:00Z",
        now_utc="2026-03-01T12:00:01Z",
        maximum_age_ms=1500,
    )


def test_invalid_tick_metadata() -> None:
    payload = eurusd_market_payload(bars_m1=candle_dicts(sequential_m1(n=3)), tick_value=0.0)
    with pytest.raises(DataError) as exc:
        parse_market_snapshot(payload)
    assert exc.value.reason is ReasonCode.SYMBOL_SPEC_MISSING
