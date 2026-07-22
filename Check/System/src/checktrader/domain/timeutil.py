"""UTC time helpers for deadlines and retry delays."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta


def parse_utc(ts: str) -> datetime:
    """Parse an ISO-8601 UTC timestamp (accepts trailing Z)."""
    normalized = ts.strip().replace("Z", "+00:00")
    dt = datetime.fromisoformat(normalized)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def format_utc(dt: datetime) -> str:
    """Format datetime as ``YYYY-MM-DDTHH:MM:SS.sssZ``."""
    utc = dt.astimezone(UTC)
    return utc.strftime("%Y-%m-%dT%H:%M:%S.") + f"{int(utc.microsecond / 1000):03d}Z"


def add_ms(ts: str, milliseconds: int) -> str:
    """Return ``ts`` advanced by ``milliseconds``."""
    return format_utc(parse_utc(ts) + timedelta(milliseconds=milliseconds))


def elapsed_ms(start_utc: str, end_utc: str) -> int:
    """Milliseconds from ``start_utc`` to ``end_utc``."""
    delta = parse_utc(end_utc) - parse_utc(start_utc)
    return int(delta.total_seconds() * 1000)


def is_at_or_after(now_utc: str, deadline_utc: str) -> bool:
    """True when ``now_utc`` >= ``deadline_utc``."""
    return parse_utc(now_utc) >= parse_utc(deadline_utc)
