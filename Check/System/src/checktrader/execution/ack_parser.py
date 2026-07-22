"""ACK parser and identity/fill validators."""

from __future__ import annotations

from typing import Any

from checktrader.domain.enums import ExecutionStatus, OrderAction, Side
from checktrader.domain.execution import Acknowledgement, PendingCommandState
from checktrader.domain.money import sl_improves
from checktrader.domain.orders import BrokerPosition
from checktrader.observability.reason_codes import ReasonCode


def parse_acknowledgement(payload: dict[str, Any]) -> Acknowledgement:
    status_raw = str(payload["status"]).upper()
    if status_raw == "SUCCESS":
        status_raw = ExecutionStatus.ACCEPTED.value
    if status_raw == "UNKNOWN":
        status_raw = ExecutionStatus.UNKNOWN.value
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
        account_number=str(payload["account_number"]) if payload.get("account_number") is not None else None,
        server=str(payload["server"]) if payload.get("server") is not None else None,
        instance_id=str(payload["instance_id"]) if payload.get("instance_id") is not None else None,
        requested_price=_opt_float(payload.get("requested_price")),
        applied_price=_opt_float(payload.get("applied_price")),
        requested_stop_loss=_opt_float(payload.get("requested_stop_loss")),
        applied_stop_loss=_opt_float(payload.get("applied_stop_loss")),
        previous_stop_loss=_opt_float(payload.get("previous_stop_loss") or payload.get("previous_broker_stop_loss")),
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


def _identity_mismatch(ack: Acknowledgement, pending: PendingCommandState) -> ReasonCode | None:
    if ack.command_id != pending.command_id:
        return ReasonCode.TRAILING_ACK_SL_MISMATCH
    if ack.action is not pending.action:
        return ReasonCode.TRAILING_ACK_SL_MISMATCH
    if ack.symbol != pending.symbol or ack.magic != pending.magic:
        return ReasonCode.TRAILING_ACK_SL_MISMATCH
    if ack.account_number is not None and ack.account_number != pending.account_number:
        return ReasonCode.ACCOUNT_NOT_ALLOWED
    if ack.server is not None and ack.server != pending.server:
        return ReasonCode.SERVER_MISMATCH
    if ack.instance_id is not None and ack.instance_id != pending.instance_id:
        return ReasonCode.TRAILING_ACK_SL_MISMATCH
    return None


def validate_open_ack(
    ack: Acknowledgement,
    pending: PendingCommandState,
    *,
    broker_pos: BrokerPosition | None,
) -> ReasonCode | None:
    """OPEN is confirmed only with SUCCESS fill fields and matching broker status."""
    mismatch = _identity_mismatch(ack, pending)
    if mismatch is not None:
        return mismatch
    if ack.status is ExecutionStatus.UNKNOWN:
        return ReasonCode.RECONCILIATION_REQUIRED
    if ack.status is not ExecutionStatus.ACCEPTED:
        return ReasonCode.OPEN_REJECTED
    if ack.ticket is None or ack.ticket <= 0:
        return ReasonCode.OPEN_REJECTED
    if ack.applied_price is None or ack.applied_price <= 0:
        return ReasonCode.OPEN_REJECTED
    if ack.applied_volume is None or ack.applied_volume <= 0:
        return ReasonCode.OPEN_REJECTED
    if ack.applied_stop_loss is None or ack.applied_stop_loss <= 0:
        return ReasonCode.OPEN_REJECTED
    if broker_pos is None:
        return ReasonCode.RECONCILIATION_REQUIRED
    if broker_pos.ticket != ack.ticket:
        return ReasonCode.RECONCILIATION_REQUIRED
    if broker_pos.symbol != pending.symbol or broker_pos.magic != pending.magic:
        return ReasonCode.RECONCILIATION_REQUIRED
    return None


def validate_modify_ack(
    ack: Acknowledgement,
    pending: PendingCommandState,
    *,
    side: Side,
    broker_pos: BrokerPosition | None,
    tolerance: float,
) -> ReasonCode | None:
    """MODIFY confirmed only with applied SL matching pending and improving protection."""
    mismatch = _identity_mismatch(ack, pending)
    if mismatch is not None:
        return mismatch
    if ack.status is not ExecutionStatus.ACCEPTED:
        return ReasonCode.MODIFY_REJECTED
    if ack.ticket is None or pending.ticket is None or ack.ticket != pending.ticket:
        return ReasonCode.TRAILING_ACK_SL_MISMATCH
    if ack.applied_stop_loss is None:
        return ReasonCode.TRAILING_ACK_SL_MISMATCH
    pending_sl = pending.requested_stop_loss
    if pending_sl is None:
        return ReasonCode.TRAILING_ACK_SL_MISMATCH
    if abs(float(ack.applied_stop_loss) - float(pending_sl)) > tolerance:
        return ReasonCode.TRAILING_ACK_SL_MISMATCH
    previous = ack.previous_stop_loss
    if previous is not None and not sl_improves(
        side=side, current_sl=float(previous), proposed_sl=float(ack.applied_stop_loss), tolerance=tolerance
    ):
        return ReasonCode.TRAILING_ACK_SL_MISMATCH
    if broker_pos is None:
        return ReasonCode.RECONCILIATION_REQUIRED
    if abs(broker_pos.stop_loss - float(ack.applied_stop_loss)) > tolerance:
        return ReasonCode.TRAILING_STATE_BROKER_MISMATCH
    return None


def validate_close_ack(
    ack: Acknowledgement,
    pending: PendingCommandState,
    *,
    broker_pos: BrokerPosition | None,
) -> ReasonCode | None:
    """CLOSE may go FLAT only when SUCCESS and position is gone from status."""
    mismatch = _identity_mismatch(ack, pending)
    if mismatch is not None:
        return mismatch
    if ack.status is not ExecutionStatus.ACCEPTED:
        return ReasonCode.CLOSE_REJECTED
    if ack.ticket is None or pending.ticket is None or ack.ticket != pending.ticket:
        return ReasonCode.CLOSE_REJECTED
    if broker_pos is not None:
        return ReasonCode.RECONCILIATION_REQUIRED
    return None


# Back-compat shim used by older call sites / thin wrappers.
def validate_modify_ack_legacy(
    ack: Acknowledgement,
    command_id: str,
    *,
    open_ticket: int,
    symbol: str,
    magic: int,
    pending_sl: float,
    tolerance: float,
) -> ReasonCode | None:
    if ack.command_id != command_id:
        return ReasonCode.TRAILING_ACK_SL_MISMATCH
    if ack.action is not OrderAction.MODIFY:
        return ReasonCode.TRAILING_ACK_SL_MISMATCH
    if ack.ticket is None or ack.ticket != open_ticket:
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
