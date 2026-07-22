"""Command factory and outbox writer."""

from __future__ import annotations

from pathlib import Path

from checktrader.domain.enums import MessageType, OrderAction, Side
from checktrader.domain.identifiers import new_command_id, new_message_id
from checktrader.domain.orders import OrderCommand
from checktrader.execution.protocol import atomic_write_json


def build_open_command(
    *,
    symbol: str,
    magic: int,
    side: Side,
    volume: float,
    requested_price: float,
    stop_loss: float,
    take_profit: float | None,
    setup_id: str,
    setup_fingerprint: str,
    created_at_utc: str,
) -> OrderCommand:
    return OrderCommand(
        command_id=new_command_id(),
        action=OrderAction.OPEN,
        symbol=symbol,
        magic=magic,
        created_at_utc=created_at_utc,
        side=side,
        volume=volume,
        requested_price=requested_price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        setup_id=setup_id,
        setup_fingerprint=setup_fingerprint,
    )


def build_modify_command(
    *,
    ticket: int,
    symbol: str,
    magic: int,
    requested_stop_loss: float,
    requested_take_profit: float,
    previous_broker_stop_loss: float,
    trailing_reason: str,
    trailing_step: float,
    created_at_utc: str,
) -> OrderCommand:
    return OrderCommand(
        command_id=new_command_id(),
        action=OrderAction.MODIFY,
        symbol=symbol,
        magic=magic,
        created_at_utc=created_at_utc,
        ticket=ticket,
        requested_stop_loss=requested_stop_loss,
        requested_take_profit=requested_take_profit,
        previous_broker_stop_loss=previous_broker_stop_loss,
        trailing_reason=trailing_reason,
        trailing_step=trailing_step,
    )


def build_close_command(
    *,
    ticket: int,
    symbol: str,
    magic: int,
    volume: float,
    requested_price: float,
    close_reason: str,
    created_at_utc: str,
) -> OrderCommand:
    return OrderCommand(
        command_id=new_command_id(),
        action=OrderAction.CLOSE,
        symbol=symbol,
        magic=magic,
        created_at_utc=created_at_utc,
        ticket=ticket,
        volume=volume,
        requested_price=requested_price,
        close_reason=close_reason,
    )


def command_to_payload(command: OrderCommand, *, sequence: int) -> dict[str, object]:
    payload: dict[str, object] = {
        "protocol_version": "2.0.0",
        "message_type": MessageType.COMMAND.value,
        "message_id": new_message_id(),
        "generated_at_utc": command.created_at_utc,
        "source": "python",
        "sequence": sequence,
        "command_id": command.command_id,
        "action": command.action.value,
        "symbol": command.symbol,
        "magic": command.magic,
        "created_at_utc": command.created_at_utc,
    }
    if command.side is not None:
        payload["side"] = command.side.value
    if command.volume is not None:
        payload["volume"] = command.volume
    if command.ticket is not None:
        payload["ticket"] = command.ticket
    if command.requested_price is not None:
        payload["requested_price"] = command.requested_price
    if command.stop_loss is not None:
        payload["stop_loss"] = command.stop_loss
    if command.take_profit is not None:
        payload["take_profit"] = command.take_profit
    if command.requested_stop_loss is not None:
        payload["requested_stop_loss"] = command.requested_stop_loss
    if command.requested_take_profit is not None:
        payload["requested_take_profit"] = command.requested_take_profit
    if command.previous_broker_stop_loss is not None:
        payload["previous_broker_stop_loss"] = command.previous_broker_stop_loss
    if command.setup_id is not None:
        payload["setup_id"] = command.setup_id
    if command.setup_fingerprint is not None:
        payload["setup_fingerprint"] = command.setup_fingerprint
    if command.trailing_reason is not None:
        payload["trailing_reason"] = command.trailing_reason
    if command.trailing_step is not None:
        payload["trailing_step"] = command.trailing_step
    if command.close_reason is not None:
        payload["close_reason"] = command.close_reason
    payload["slippage_points"] = command.slippage_points
    return payload


def write_command(commands_dir: Path, command: OrderCommand, *, sequence: int) -> Path:
    path = commands_dir / f"{sequence}_{command.command_id}.json"
    atomic_write_json(path, command_to_payload(command, sequence=sequence))
    return path
