from __future__ import annotations
import re
from datetime import datetime, timedelta, timezone
import pytest
from engine.core.clock import format_utc_timestamp, now_utc, utc_now
from engine.protocol.errors import ValidationError

def test_utc_now_returns_timezone_aware_utc_datetime() -> None:
    current = utc_now()
    assert isinstance(current, datetime)
    assert current.tzinfo is not None
    assert current.utcoffset() == timedelta(0)

def test_format_utc_timestamp_returns_iso8601_with_milliseconds() -> None:
    timestamp = datetime(2026, 7, 7, 6, 0, 1, 987654, tzinfo=timezone.utc)
    assert format_utc_timestamp(timestamp) == '2026-07-07T06:00:01.987Z'

def test_format_utc_timestamp_converts_non_utc_to_utc() -> None:
    plus_two = timezone(timedelta(hours=2))
    timestamp = datetime(2026, 7, 7, 8, 0, 1, 123000, tzinfo=plus_two)
    assert format_utc_timestamp(timestamp) == '2026-07-07T06:00:01.123Z'

def test_format_utc_timestamp_rejects_naive_datetime() -> None:
    naive = datetime(2026, 7, 7, 6, 0, 1, 123000)
    with pytest.raises(ValidationError, match='timezone-aware'):
        format_utc_timestamp(naive)

def test_format_utc_timestamp_rejects_non_datetime() -> None:
    with pytest.raises(ValidationError, match='datetime'):
        format_utc_timestamp('2026-07-07T06:00:01.123Z')

def test_now_utc_uses_default_utc_clock() -> None:
    value = now_utc()
    assert re.fullmatch('\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}\\.\\d{3}Z', value)

def test_now_utc_accepts_deterministic_provider() -> None:
    fixed = datetime(2026, 7, 7, 6, 0, 1, 123000, tzinfo=timezone.utc)
    assert now_utc(lambda: fixed) == '2026-07-07T06:00:01.123Z'
