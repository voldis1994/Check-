from __future__ import annotations

from dataclasses import dataclass, field

from checktrader.domain.enums import ReasonCode
from checktrader.domain.models import Position


@dataclass(slots=True)
class ReconciliationResult:
    positions: list[Position]
    reason: ReasonCode = ReasonCode.RECONCILED_WITH_BROKER
    closed_position_ids: list[str] = field(default_factory=list)


def reconcile(local_positions: list[Position], broker_positions: list[Position]) -> ReconciliationResult:
    ids = {p.position_id for p in broker_positions}
    return ReconciliationResult(
        list(broker_positions), closed_position_ids=[p.position_id for p in local_positions if p.position_id not in ids]
    )
