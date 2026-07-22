"""Execution acknowledgement and pending command models."""

from __future__ import annotations

from dataclasses import dataclass

from checktrader.domain.enums import ExecutionStatus, OrderAction


@dataclass(frozen=True, slots=True)
class Acknowledgement:
    """Broker acknowledgement for one command."""

    protocol_version: str
    message_id: str
    command_id: str
    action: OrderAction
    status: ExecutionStatus
    ticket: int | None
    symbol: str
    magic: int
    processed_at_utc: str
    account_number: str | None = None
    server: str | None = None
    instance_id: str | None = None
    requested_price: float | None = None
    applied_price: float | None = None
    requested_stop_loss: float | None = None
    applied_stop_loss: float | None = None
    previous_stop_loss: float | None = None
    requested_take_profit: float | None = None
    applied_take_profit: float | None = None
    requested_volume: float | None = None
    applied_volume: float | None = None
    broker_error_code: int | None = None
    broker_error_text: str | None = None
    sequence: int = 0


@dataclass(slots=True)
class PendingCommandState:
    """Single in-flight broker command for one instance."""

    command_id: str
    action: OrderAction
    account_number: str
    server: str
    instance_id: str
    symbol: str
    magic: int
    ticket: int | None = None
    setup_fingerprint: str | None = None
    requested_price: float | None = None
    requested_volume: float | None = None
    requested_stop_loss: float | None = None
    requested_take_profit: float | None = None
    created_at: str = ""
    last_attempt_at: str = ""
    retry_count: int = 0
    maximum_retries: int = 3
    acknowledgement_deadline: str = ""
    last_error: str | None = None
