"""Execution engine facade for command build + write."""

from __future__ import annotations

from pathlib import Path

from checktrader.domain.enums import Side
from checktrader.domain.orders import OrderCommand
from checktrader.execution.command_factory import (
    build_close_command,
    build_modify_command,
    build_open_command,
    write_command,
)


def submit_open(
    commands_dir: Path,
    *,
    sequence: int,
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
) -> tuple[OrderCommand, Path]:
    command = build_open_command(
        symbol=symbol,
        magic=magic,
        side=side,
        volume=volume,
        requested_price=requested_price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        setup_id=setup_id,
        setup_fingerprint=setup_fingerprint,
        created_at_utc=created_at_utc,
    )
    path = write_command(commands_dir, command, sequence=sequence)
    return command, path


def submit_modify(
    commands_dir: Path,
    *,
    sequence: int,
    ticket: int,
    symbol: str,
    magic: int,
    requested_stop_loss: float,
    requested_take_profit: float,
    previous_broker_stop_loss: float,
    trailing_reason: str,
    trailing_step: float,
    created_at_utc: str,
) -> tuple[OrderCommand, Path]:
    command = build_modify_command(
        ticket=ticket,
        symbol=symbol,
        magic=magic,
        requested_stop_loss=requested_stop_loss,
        requested_take_profit=requested_take_profit,
        previous_broker_stop_loss=previous_broker_stop_loss,
        trailing_reason=trailing_reason,
        trailing_step=trailing_step,
        created_at_utc=created_at_utc,
    )
    path = write_command(commands_dir, command, sequence=sequence)
    return command, path


def submit_close(
    commands_dir: Path,
    *,
    sequence: int,
    ticket: int,
    symbol: str,
    magic: int,
    volume: float,
    requested_price: float,
    close_reason: str,
    created_at_utc: str,
) -> tuple[OrderCommand, Path]:
    command = build_close_command(
        ticket=ticket,
        symbol=symbol,
        magic=magic,
        volume=volume,
        requested_price=requested_price,
        close_reason=close_reason,
        created_at_utc=created_at_utc,
    )
    path = write_command(commands_dir, command, sequence=sequence)
    return command, path


__all__ = ["submit_open", "submit_modify", "submit_close"]
