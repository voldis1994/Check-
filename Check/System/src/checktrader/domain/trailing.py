"""Trailing domain state."""

from __future__ import annotations

from dataclasses import dataclass

from checktrader.domain.enums import ConfirmationSource


@dataclass(slots=True)
class TrailingState:
    broker_stop_loss: float | None = None
    broker_take_profit: float | None = None
    current_bid: float | None = None
    current_ask: float | None = None
    current_net_profit: float = 0.0
    peak_net_profit: float = 0.0
    position_ticket: int | None = None
    status_timestamp: str | None = None
    calculated_be_sl: float | None = None
    calculated_grid_step: int = 0
    calculated_grid_sl: float | None = None
    calculated_high_lock_sl: float | None = None
    calculated_pressure_sl: float | None = None
    final_proposed_sl: float | None = None
    pending_command_id: str | None = None
    pending_stop_loss: float | None = None
    pending_step: int | None = None
    pending_created_at: str | None = None
    retry_count: int = 0
    be_confirmed: bool = False
    confirmed_be_sl: float | None = None
    confirmed_grid_step: int = 0
    confirmed_stop_loss: float | None = None
    confirmed_locked_net_profit: float = 0.0
    confirmed_at: str | None = None
    confirmation_source: ConfirmationSource = ConfirmationSource.NONE
    last_reason: str | None = None
