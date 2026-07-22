"""Reference shapes and validators for MT4 protocol v2.0.0 bridge messages."""

from __future__ import annotations

from typing import Any

PROTOCOL_VERSION = "2.0.0"
MESSAGE_MARKET = "market_snapshot"
MESSAGE_STATUS = "status_snapshot"
MESSAGE_COMMAND = "command"
MESSAGE_ACK = "acknowledgement"

ENVELOPE_FIELDS = (
    "protocol_version",
    "message_type",
    "message_id",
    "generated_at_utc",
    "source",
    "sequence",
)

MARKET_REQUIRED = ENVELOPE_FIELDS + (
    "account_number",
    "server",
    "symbol",
    "digits",
    "point",
    "pip_size",
    "bid",
    "ask",
    "spread_points",
    "spread_pips",
    "tick_size",
    "tick_value",
    "minimum_lot",
    "maximum_lot",
    "lot_step",
    "stop_level_points",
    "freeze_level_points",
    "trade_allowed",
    "market_open",
    "bars_m1",
)

STATUS_REQUIRED = ENVELOPE_FIELDS + (
    "account_number",
    "balance",
    "equity",
    "margin",
    "free_margin",
    "margin_level",
    "trade_allowed",
    "expert_enabled",
)

POSITION_REQUIRED = (
    "ticket",
    "symbol",
    "magic",
    "side",
    "volume",
    "open_time",
    "open_price",
    "stop_loss",
    "take_profit",
    "current_price",
    "profit",
    "swap",
    "commission",
    "net_profit",
    "comment",
)

BAR_REQUIRED = (
    "open_time_utc",
    "close_time_utc",
    "open",
    "high",
    "low",
    "close",
    "tick_volume",
    "complete",
)

ACK_REQUIRED = ENVELOPE_FIELDS + (
    "command_id",
    "action",
    "status",
    "symbol",
    "magic",
    "processed_at_utc",
)

COMMAND_REQUIRED = (
    "protocol_version",
    "message_type",
    "message_id",
    "generated_at_utc",
    "source",
    "sequence",
    "command_id",
    "action",
    "symbol",
    "magic",
)


class ProtocolShapeError(ValueError):
    """Raised when a bridge JSON payload does not match the v2 contract."""


def _require(payload: dict[str, Any], fields: tuple[str, ...], *, label: str) -> None:
    missing = [name for name in fields if name not in payload]
    if missing:
        raise ProtocolShapeError(f"{label} missing fields: {', '.join(missing)}")


def _require_iso_utc(value: object, *, field: str) -> None:
    text = str(value)
    if "T" not in text or not text.endswith("Z"):
        raise ProtocolShapeError(f"{field} must be UTC ISO ending with Z, got {text!r}")


def validate_envelope(payload: dict[str, Any], *, expected_type: str, expected_source: str) -> None:
    _require(payload, ENVELOPE_FIELDS, label="envelope")
    if str(payload["protocol_version"]) != PROTOCOL_VERSION:
        raise ProtocolShapeError(f"protocol_version must be {PROTOCOL_VERSION}")
    if str(payload["message_type"]) != expected_type:
        raise ProtocolShapeError(f"message_type must be {expected_type}")
    if str(payload["source"]) != expected_source:
        raise ProtocolShapeError(f"source must be {expected_source}")
    _require_iso_utc(payload["generated_at_utc"], field="generated_at_utc")
    if int(payload["sequence"]) < 0:
        raise ProtocolShapeError("sequence must be >= 0")


def validate_market_snapshot(payload: dict[str, Any]) -> dict[str, Any]:
    validate_envelope(payload, expected_type=MESSAGE_MARKET, expected_source="mt4")
    _require(payload, MARKET_REQUIRED, label="market_snapshot")
    bars = payload["bars_m1"]
    if not isinstance(bars, list):
        raise ProtocolShapeError("bars_m1 must be a list")
    for index, bar in enumerate(bars):
        if not isinstance(bar, dict):
            raise ProtocolShapeError(f"bars_m1[{index}] must be an object")
        _require(bar, BAR_REQUIRED, label=f"bars_m1[{index}]")
        if not bool(bar["complete"]):
            raise ProtocolShapeError(f"bars_m1[{index}] must be complete closed bars")
    return payload


def validate_status_snapshot(payload: dict[str, Any]) -> dict[str, Any]:
    validate_envelope(payload, expected_type=MESSAGE_STATUS, expected_source="mt4")
    _require(payload, STATUS_REQUIRED, label="status_snapshot")
    positions = payload.get("positions", payload.get("open_positions"))
    if positions is None:
        raise ProtocolShapeError("status_snapshot missing positions")
    if not isinstance(positions, list):
        raise ProtocolShapeError("positions must be a list")
    for index, pos in enumerate(positions):
        if not isinstance(pos, dict):
            raise ProtocolShapeError(f"positions[{index}] must be an object")
        _require(pos, POSITION_REQUIRED, label=f"positions[{index}]")
        if str(pos["side"]) not in {"BUY", "SELL"}:
            raise ProtocolShapeError(f"positions[{index}].side invalid")
    return payload


def validate_command(payload: dict[str, Any]) -> dict[str, Any]:
    _require(payload, COMMAND_REQUIRED, label="command")
    if str(payload["protocol_version"]) != PROTOCOL_VERSION:
        raise ProtocolShapeError(f"protocol_version must be {PROTOCOL_VERSION}")
    if str(payload["message_type"]) != MESSAGE_COMMAND:
        raise ProtocolShapeError("message_type must be command")
    if str(payload["source"]) != "python":
        raise ProtocolShapeError("command source must be python")
    action = str(payload["action"])
    if action not in {"OPEN", "MODIFY", "CLOSE"}:
        raise ProtocolShapeError(f"unsupported action {action}")
    if action == "OPEN":
        for key in ("side", "volume", "stop_loss"):
            if key not in payload:
                raise ProtocolShapeError(f"OPEN missing {key}")
    if action == "MODIFY":
        for key in ("ticket", "requested_stop_loss"):
            if key not in payload:
                raise ProtocolShapeError(f"MODIFY missing {key}")
    if action == "CLOSE":
        for key in ("ticket", "volume"):
            if key not in payload:
                raise ProtocolShapeError(f"CLOSE missing {key}")
    return payload


def validate_acknowledgement(payload: dict[str, Any]) -> dict[str, Any]:
    validate_envelope(payload, expected_type=MESSAGE_ACK, expected_source="mt4")
    _require(payload, ACK_REQUIRED, label="acknowledgement")
    status = str(payload["status"])
    if status not in {"SUCCESS", "FAILED", "REJECTED", "ALREADY_PROCESSED", "ACCEPTED"}:
        raise ProtocolShapeError(f"invalid ack status {status}")
    action = str(payload["action"])
    if action == "MODIFY":
        if "requested_stop_loss" not in payload or "applied_stop_loss" not in payload:
            raise ProtocolShapeError("MODIFY ACK requires requested_stop_loss and applied_stop_loss")
    _require_iso_utc(payload["processed_at_utc"], field="processed_at_utc")
    return payload


def sl_improves_protection(
    *,
    side: str,
    previous_sl: float,
    applied_sl: float,
    tolerance: float,
) -> bool:
    if previous_sl <= 0.0 and applied_sl > 0.0:
        return True
    if side == "BUY":
        return applied_sl > previous_sl + tolerance
    if side == "SELL":
        return applied_sl < previous_sl - tolerance
    return False


def validate_modify_success(
    *,
    side: str,
    previous_sl: float,
    requested_sl: float,
    applied_sl: float,
    tolerance: float,
    order_modify_ok: bool,
) -> bool:
    if not order_modify_ok:
        return False
    if not sl_improves_protection(side=side, previous_sl=previous_sl, applied_sl=applied_sl, tolerance=tolerance):
        return False
    if abs(applied_sl - requested_sl) > tolerance:
        return False
    return True


def command_filename(sequence: int, command_id: str) -> str:
    return f"{sequence}_{command_id}.json"


def ack_filename(sequence: int, command_id: str) -> str:
    return f"{sequence}_{command_id}.ack.json"
