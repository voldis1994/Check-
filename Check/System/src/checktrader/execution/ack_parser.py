"""ACK parser and validator."""

from __future__ import annotations

from typing import Any

from checktrader.domain.enums import ExecutionStatus, OrderAction
from checktrader.domain.errors import ValidationError
from checktrader.domain.execution import Acknowledgement
from checktrader.domain.orders import OrderCommand
from checktrader.observability.reason_codes import ReasonCode


def parse_acknowledgement(payload: dict[str, Any]) -> Acknowledgement:
    status_raw = str(payload["status"]).upper()
    if status_raw == "SUCCESS":
        status_raw = ExecutionStatus.ACCEPTED.value
    return Acknowledgement(
        protocol_version=str(payload.get("protocol_version", "2.0.0")),
        message_id=str(payload.get("message_id", "")),
        command_id=str(payload["command_id"]),
        action=OrderAction(str(payload["action"])),
        status=ExecutionStatus(status_raw),
        ticket=int(payload["ticket"]) if payload.get("ticket") is not None else None,
        symbol=str(payload["symbol"]),
        magic=int(payload["magic"]),
        processed_at_utc=str(payload.get("processed_at_utc", payload.get("generated_at_utc", ""))),
        requested_price=_opt_float(payload.get("requested_price")),
        applied_price=_opt_float(payload.get("applied_price")),
        requested_stop_loss=_opt_float(payload.get("requested_stop_loss")),
        applied_stop_loss=_opt_float(payload.get("applied_stop_loss")),
        requested_take_profit=_opt_float(payload.get("requested_take_profit")),
        applied_take_profit=_opt_float(payload.get("applied_take_profit")),
        requested_volume=_opt_float(payload.get("requested_volume")),
        applied_volume=_opt_float(payload.get("applied_volume")),
        broker_error_code=int(payload["broker_error_code"]) if payload.get("broker_error_code") is not None else None,
        broker_error_text=str(payload["broker_error_text"]) if payload.get("broker_error_text") else None,
        sequence=int(payload.get("sequence", 0)),
    )


def _opt_float(value: object) -> float | None:
    if value is None:
        return None
    return float(value)  # type: ignore[arg-type]


def validate_modify_ack(
    ack: Acknowledgement,
    command: OrderCommand,
    *,
    open_ticket: int,
    symbol: str,
    magic: int,
    pending_sl: float,
    tolerance: float,
) -> ReasonCode | None:
    if ack.command_id != command.command_id:
        return ReasonCode.TRAILING_ACK_SL_MISMATCH
    if ack.action is not OrderAction.MODIFY:
        return ReasonCode.TRAILING_ACK_SL_MISMATCH
    if ack.ticket is None or ack.ticket != command.ticket or ack.ticket != open_ticket:
        return ReasonCode.TRAILING_ACK_SL_MISMATCH
    if ack.symbol != symbol or ack.magic != magic:
        return ReasonCode.TRAILING_ACK_SL_MISMATCH
    if ack.status is not ExecutionStatus.ACCEPTED:
        return ReasonCode.MODIFY_REJECTED
    if ack.applied_stop_loss is None:
        return ReasonCode.TRAILING_ACK_SL_MISMATCH
    if abs(float(ack.applied_stop_loss) - float(pending_sl)) > tolerance:
        return ReasonCode.TRAILING_ACK_SL_MISMATCH
    return None


def require_open_fill(ack: Acknowledgement) -> None:
    if ack.status is not ExecutionStatus.ACCEPTED:
        raise ValidationError("OPEN not accepted", reason=ReasonCode.OPEN_REJECTED)
    if ack.ticket is None or ack.applied_price is None or ack.applied_volume is None:
        raise ValidationError("OPEN ACK missing fill fields", reason=ReasonCode.OPEN_REJECTED)
