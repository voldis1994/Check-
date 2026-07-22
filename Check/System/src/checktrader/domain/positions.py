"""Position runtime model."""

from __future__ import annotations

from dataclasses import dataclass

from checktrader.domain.enums import PositionState, Side


@dataclass(slots=True)
class ManagedPosition:
    state: PositionState = PositionState.FLAT
    ticket: int | None = None
    side: Side | None = None
    volume: float | None = None
    open_price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    open_time_utc: str | None = None
    setup_id: str | None = None
    setup_fingerprint: str | None = None
    pending_command_id: str | None = None
