"""Position state transition helpers."""

from __future__ import annotations

from checktrader.domain.enums import PositionState
from checktrader.domain.positions import ManagedPosition


def transition_to(managed: ManagedPosition, new_state: PositionState) -> ManagedPosition:
    managed.state = new_state
    return managed


def mark_flat(managed: ManagedPosition) -> ManagedPosition:
    managed.state = PositionState.FLAT
    managed.ticket = None
    managed.side = None
    managed.volume = None
    managed.open_price = None
    managed.stop_loss = None
    managed.take_profit = None
    managed.open_time_utc = None
    managed.pending_command_id = None
    return managed


def mark_open_pending(managed: ManagedPosition, *, command_id: str) -> ManagedPosition:
    managed.state = PositionState.OPEN_PENDING
    managed.pending_command_id = command_id
    return managed


__all__ = ["transition_to", "mark_flat", "mark_open_pending"]
