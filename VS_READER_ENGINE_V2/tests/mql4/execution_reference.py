from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Callable

from engine.protocol.constants import AckStatus, OrderAction, PROTOCOL_SCHEMA_VERSION, Side
from engine.protocol.parser import parse_ack
from tests.mql4 import control_reference

ACK_FILENAME_TEMPLATE = "ack_{symbol}_{magic}.json"
SUPPORTED_ACK_STATUSES = {
    AckStatus.SUCCESS.value,
    AckStatus.FAILED.value,
    AckStatus.REJECTED.value,
}
DEFAULT_SLIPPAGE = 3


@dataclass
class AckResult:
    status: str = ""
    ticket: int = 0
    error_code: int = 0
    error_message: str = ""
    has_ticket: bool = False


@dataclass
class OrderExecutionContext:
    symbol: str
    magic: int
    trade_allowed: bool = True
    known_tickets: set[int] | None = None
    order_send_result: int | None = None
    order_modify_result: bool | None = None
    order_close_result: bool | None = None
    order_send_error: int = 130
    order_modify_error: int = 130
    order_close_error: int = 130

    def __post_init__(self) -> None:
        if self.known_tickets is None:
            self.known_tickets = set()


def build_ack_file_path(root_path: str, account_id: str, symbol: str, magic: int) -> str:
    return f"{root_path}\\data\\clients\\{account_id}\\ack_{symbol}_{magic}.json"


def is_supported_ack_status(status: str) -> bool:
    return status in SUPPORTED_ACK_STATUSES


def build_ack_json(
    *,
    command_id: str,
    account_id: str,
    symbol: str,
    magic: int,
    status: str,
    timestamp_utc: str,
    ticket: int | None = None,
    error_code: int | None = None,
    error_message: str | None = None,
) -> str:
    payload: dict[str, object] = {
        "account_id": account_id,
        "command_id": command_id,
        "magic": magic,
        "schema_version": PROTOCOL_SCHEMA_VERSION,
        "status": status,
        "symbol": symbol,
        "timestamp_utc": timestamp_utc,
    }
    if ticket is not None and ticket > 0:
        payload["ticket"] = ticket
    if error_code is not None and error_code != 0:
        payload["error_code"] = error_code
    if error_message:
        payload["error_message"] = error_message
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def is_supported_trade_side(side: str) -> bool:
    return side in {Side.BUY.value, Side.SELL.value}


def trade_command_for_side(side: str) -> int:
    if side == Side.BUY.value:
        return 0
    if side == Side.SELL.value:
        return 1
    return -1


def select_order_by_ticket(ticket: int, *, symbol: str, magic: int, known_tickets: set[int]) -> bool:
    return ticket > 0 and ticket in known_tickets


def set_rejected_ack(result: AckResult, message: str, *, error_code: int = 0) -> AckResult:
    return AckResult(
        status=AckStatus.REJECTED.value,
        error_message=message,
        error_code=error_code,
    )


def set_failed_ack(result: AckResult, message: str, *, error_code: int) -> AckResult:
    return AckResult(
        status=AckStatus.FAILED.value,
        error_message=message,
        error_code=error_code,
    )


def set_success_ack(ticket: int) -> AckResult:
    return AckResult(
        status=AckStatus.SUCCESS.value,
        ticket=ticket,
        has_ticket=ticket > 0,
    )


def execute_open(command: control_reference.ControlCommandData, context: OrderExecutionContext) -> AckResult:
    if not command.has_side or not is_supported_trade_side(command.side):
        return set_rejected_ack(AckResult(), "open command requires BUY or SELL side")
    if not command.has_volume or command.volume <= 0:
        return set_rejected_ack(AckResult(), "open command requires positive volume")
    if not context.trade_allowed:
        return set_rejected_ack(AckResult(), "trade is not allowed")

    if context.order_send_result is None:
        ticket = 555 if command.side == Side.BUY.value else 556
    else:
        ticket = context.order_send_result

    if ticket < 0:
        return set_failed_ack(AckResult(), "OrderSend failed", error_code=context.order_send_error)

    if context.known_tickets is not None:
        context.known_tickets.add(ticket)
    return set_success_ack(ticket)


def execute_modify(command: control_reference.ControlCommandData, context: OrderExecutionContext) -> AckResult:
    if not command.has_ticket or command.ticket <= 0:
        return set_rejected_ack(AckResult(), "modify command requires ticket")
    if not select_order_by_ticket(
        command.ticket,
        symbol=command.symbol,
        magic=command.magic,
        known_tickets=context.known_tickets or set(),
    ):
        return set_rejected_ack(AckResult(), "modify ticket not found for instance")

    modified = True if context.order_modify_result is None else context.order_modify_result
    if not modified:
        return set_failed_ack(AckResult(), "OrderModify failed", error_code=context.order_modify_error)
    return set_success_ack(command.ticket)


def execute_close(command: control_reference.ControlCommandData, context: OrderExecutionContext) -> AckResult:
    if not command.has_ticket or command.ticket <= 0:
        return set_rejected_ack(AckResult(), "close command requires ticket")
    if not select_order_by_ticket(
        command.ticket,
        symbol=command.symbol,
        magic=command.magic,
        known_tickets=context.known_tickets or set(),
    ):
        return set_rejected_ack(AckResult(), "close ticket not found for instance")

    closed = True if context.order_close_result is None else context.order_close_result
    if not closed:
        return set_failed_ack(AckResult(), "OrderClose failed", error_code=context.order_close_error)
    return set_success_ack(command.ticket)


def execute_control_command(
    command: control_reference.ControlCommandData,
    context: OrderExecutionContext,
) -> AckResult:
    if command.action == OrderAction.NONE.value:
        return set_success_ack(0)
    if command.action == OrderAction.OPEN.value:
        return execute_open(command, context)
    if command.action == OrderAction.MODIFY.value:
        return execute_modify(command, context)
    if command.action == OrderAction.CLOSE.value:
        return execute_close(command, context)
    return set_rejected_ack(AckResult(), "unsupported control action")


def try_execute_pending_control(
    json_text: str,
    *,
    account_id: str,
    symbol: str,
    magic: int,
    last_processed_command_id: str,
    context: OrderExecutionContext,
    tmp_exists: bool = False,
    file_exists: bool = True,
    write_ack: Callable[[str, AckResult], bool] | None = None,
) -> tuple[str | None, AckResult | None, str]:
    command, error = control_reference.read_control_command(
        json_text,
        account_id=account_id,
        symbol=symbol,
        magic=magic,
        tmp_exists=tmp_exists,
        file_exists=file_exists,
    )
    if command is None:
        return None, None, error

    if command.command_id == last_processed_command_id:
        return None, None, ""

    result = execute_control_command(command, context)
    if write_ack is not None and not write_ack(command.command_id, result):
        return None, None, "failed to write ack file"

    return command.command_id, result, ""


def parse_ack_from_reference_json(json_text: str):
    return parse_ack(json_text)
