"""Execution acknowledgement model."""

from __future__ import annotations

from dataclasses import dataclass

from checktrader.domain.enums import ExecutionStatus, OrderAction


@dataclass(frozen=True, slots=True)
class Acknowledgement:
    protocol_version: str
    message_id: str
    command_id: str
    action: OrderAction
    status: ExecutionStatus
    ticket: int | None
    symbol: str
    magic: int
    processed_at_utc: str
    requested_price: float | None = None
    applied_price: float | None = None
    requested_stop_loss: float | None = None
    applied_stop_loss: float | None = None
    requested_take_profit: float | None = None
    applied_take_profit: float | None = None
    requested_volume: float | None = None
    applied_volume: float | None = None
    broker_error_code: int | None = None
    broker_error_text: str | None = None
    sequence: int = 0
