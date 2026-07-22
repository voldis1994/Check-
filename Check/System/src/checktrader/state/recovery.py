"""State recovery helpers."""

from __future__ import annotations

from pathlib import Path

from checktrader.domain.enums import PositionState
from checktrader.state.store import InstanceRuntimeState, load_instance_state


def load_or_recover(path: Path) -> InstanceRuntimeState:
    """Load instance state; checksum mismatch already yields RECONCILING from store."""
    state = load_instance_state(path)
    return state


def needs_broker_reconciliation(state: InstanceRuntimeState) -> bool:
    return state.position.state in {
        PositionState.RECONCILING,
        PositionState.OPEN_PENDING,
        PositionState.MODIFY_PENDING,
        PositionState.CLOSE_PENDING,
        PositionState.ERROR,
    }


__all__ = ["load_or_recover", "needs_broker_reconciliation"]
