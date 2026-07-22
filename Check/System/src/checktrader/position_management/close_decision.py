"""Close decision helpers for exit pressure / protective path."""

from __future__ import annotations

from checktrader.domain.enums import OrderAction
from checktrader.position_management.engine import ProtectiveDecision


def should_market_close(decision: ProtectiveDecision) -> bool:
    return bool(decision.close) or decision.action is OrderAction.CLOSE


def close_reason(decision: ProtectiveDecision) -> str:
    return decision.reason.value


__all__ = ["should_market_close", "close_reason"]
