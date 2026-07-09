from __future__ import annotations
import json
import re
from dataclasses import dataclass, field
from engine.protocol.constants import PROTOCOL_SCHEMA_VERSION, OrderAction
from engine.protocol.parser import parse_control
SUPPORTED_ACTIONS = {OrderAction.OPEN.value, OrderAction.MODIFY.value, OrderAction.CLOSE.value, OrderAction.NONE.value}

@dataclass
class ControlCommandData:
    schema_version: str = ''
    timestamp_utc: str = ''
    command_id: str = ''
    account_id: str = ''
    symbol: str = ''
    magic: int = 0
    action: str = ''
    reason: str = ''
    decision_id: str = ''
    side: str = ''
    volume: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    ticket: int = 0
    has_side: bool = False
    has_volume: bool = False
    has_stop_loss: bool = False
    has_take_profit: bool = False
    has_ticket: bool = False

def build_control_file_path(root_path: str, account_id: str, symbol: str, magic: int) -> str:
    return f'{root_path}\\data\\clients\\{account_id}\\control_{symbol}_{magic}.json'

def control_tmp_path(path: str) -> str:
    return f'{path}.tmp'

def is_control_tmp_present(*, tmp_exists: bool) -> bool:
    return tmp_exists

def is_control_ready(path: str, *, tmp_exists: bool, file_exists: bool) -> bool:
    return file_exists and (not tmp_exists)

def extract_json_string_field(json_text: str, field_name: str) -> str | None:
    match = re.search(f'"{re.escape(field_name)}"\\s*:\\s*"([^"]*)"', json_text)
    if match is None:
        return None
    return match.group(1)

def extract_json_token(json_text: str, field_name: str) -> str | None:
    match = re.search(f'"{re.escape(field_name)}"\\s*:\\s*([^,\\n\\r}}]+)', json_text)
    if match is None:
        return None
    return match.group(1).strip()

def extract_json_int_field(json_text: str, field_name: str) -> int | None:
    token = extract_json_token(json_text, field_name)
    if token is None:
        return None
    return int(token)

def extract_json_double_field(json_text: str, field_name: str) -> float | None:
    token = extract_json_token(json_text, field_name)
    if token is None:
        return None
    return float(token)

def is_supported_order_action(action: str) -> bool:
    return action in SUPPORTED_ACTIONS

def control_requires_order_execution(action: str) -> bool:
    return action in {OrderAction.OPEN.value, OrderAction.MODIFY.value, OrderAction.CLOSE.value}

def parse_control_command(json_text: str) -> tuple[ControlCommandData | None, str]:
    if not json_text.strip():
        return (None, 'control json is empty')
    command = ControlCommandData()
    command.schema_version = extract_json_string_field(json_text, 'schema_version') or ''
    if not command.schema_version:
        return (None, 'missing schema_version')
    if command.schema_version != PROTOCOL_SCHEMA_VERSION:
        return (None, 'unsupported schema_version')
    command.timestamp_utc = extract_json_string_field(json_text, 'timestamp_utc') or ''
    if not command.timestamp_utc:
        return (None, 'missing timestamp_utc')
    command.command_id = extract_json_string_field(json_text, 'command_id') or ''
    if not command.command_id:
        return (None, 'missing command_id')
    command.account_id = extract_json_string_field(json_text, 'account_id') or ''
    if not command.account_id:
        return (None, 'missing account_id')
    command.symbol = extract_json_string_field(json_text, 'symbol') or ''
    if not command.symbol:
        return (None, 'missing symbol')
    magic = extract_json_int_field(json_text, 'magic')
    if magic is None:
        return (None, 'missing magic')
    command.magic = magic
    command.action = extract_json_string_field(json_text, 'action') or ''
    if not command.action:
        return (None, 'missing action')
    if not is_supported_order_action(command.action):
        return (None, 'invalid action')
    command.reason = extract_json_string_field(json_text, 'reason') or ''
    if not command.reason:
        return (None, 'missing reason')
    command.decision_id = extract_json_string_field(json_text, 'decision_id') or ''
    if not command.decision_id:
        return (None, 'missing decision_id')
    side = extract_json_string_field(json_text, 'side')
    if side is not None:
        command.side = side
        command.has_side = True
    volume = extract_json_double_field(json_text, 'volume')
    if volume is not None:
        command.volume = volume
        command.has_volume = True
    stop_loss = extract_json_double_field(json_text, 'stop_loss')
    if stop_loss is not None:
        command.stop_loss = stop_loss
        command.has_stop_loss = True
    take_profit = extract_json_double_field(json_text, 'take_profit')
    if take_profit is not None:
        command.take_profit = take_profit
        command.has_take_profit = True
    ticket = extract_json_int_field(json_text, 'ticket')
    if ticket is not None:
        command.ticket = ticket
        command.has_ticket = True
    return (command, '')

def validate_control_instance(command: ControlCommandData, *, expected_account_id: str, expected_symbol: str, expected_magic: int) -> str:
    if command.account_id != expected_account_id:
        return 'control account_id does not match instance'
    if command.symbol != expected_symbol:
        return 'control symbol does not match instance'
    if command.magic != expected_magic:
        return 'control magic does not match instance'
    return ''

def read_control_command(json_text: str, *, account_id: str, symbol: str, magic: int, tmp_exists: bool=False, file_exists: bool=True) -> tuple[ControlCommandData | None, str]:
    if not is_control_ready('path', tmp_exists=tmp_exists, file_exists=file_exists):
        return (None, 'control file is not ready')
    command, error = parse_control_command(json_text)
    if command is None:
        return (None, error)
    validation_error = validate_control_instance(command, expected_account_id=account_id, expected_symbol=symbol, expected_magic=magic)
    if validation_error:
        return (None, validation_error)
    return (command, '')

def parse_control_with_protocol(json_text: str):
    return parse_control(json_text)
