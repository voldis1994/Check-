from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from checktrader import protocol_version
from checktrader.domain.models import Acknowledgement, Command


def envelope(message_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "protocol_version": protocol_version,
        "message_type": message_type,
        "timestamp": datetime.now(UTC).isoformat(),
        "payload": payload,
    }


def command_message(command: Command) -> dict[str, Any]:
    return envelope("COMMAND", command.to_dict())


def ack_message(ack: Acknowledgement) -> dict[str, Any]:
    return envelope("ACK", ack.to_dict())


def market_status_shape(payload: dict[str, Any]) -> dict[str, Any]:
    return envelope("MARKET_STATUS", payload)
