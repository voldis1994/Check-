"""Setup domain model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from checktrader.domain.enums import SetupState, Side


@dataclass(slots=True)
class Setup:
    setup_id: str
    setup_type: str
    symbol: str
    direction: Side
    context_timeframe: str
    setup_timeframe: str
    entry_timeframe: str
    setup_origin_timestamp: str
    context_structure_id: str
    pullback_structure_id: str
    trigger_level: float
    invalidation_level: float
    proposed_entry: float
    proposed_stop_loss: float
    created_at: str
    expires_at: str
    state: SetupState
    fingerprint: str
    evidence: dict[str, Any] = field(default_factory=dict)
