"""Freshness helpers."""

from __future__ import annotations

from datetime import UTC, datetime


def parse_utc(ts: str) -> datetime:
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    return datetime.fromisoformat(ts).astimezone(UTC)


def age_ms(generated_at_utc: str, now_utc: str) -> int:
    delta = parse_utc(now_utc) - parse_utc(generated_at_utc)
    return int(delta.total_seconds() * 1000)


def is_stale(*, generated_at_utc: str, now_utc: str, maximum_age_ms: int) -> bool:
    return age_ms(generated_at_utc, now_utc) > maximum_age_ms
