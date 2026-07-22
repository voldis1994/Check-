from __future__ import annotations

from datetime import datetime

from checktrader.domain.enums import ReasonCode


def heartbeat_ok(last_seen: datetime | None, now: datetime, max_age_seconds: float) -> tuple[bool, ReasonCode]:
    if last_seen is None:
        return False, ReasonCode.BRIDGE_UNAVAILABLE
    return (
        (False, ReasonCode.HEARTBEAT_STALE)
        if (now - last_seen).total_seconds() > max_age_seconds
        else (True, ReasonCode.DATA_VALID)
    )
