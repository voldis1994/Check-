from __future__ import annotations
import csv
import json
from io import StringIO
from typing import Any, Iterable, Sequence
from engine.protocol.constants import MARKET_CSV_COLUMNS, SENSOR_CSV_COLUMNS
from engine.protocol.errors import ProtocolError
from engine.protocol.models import AckRecord, ControlCommand, DecisionJournalEntry, ErrorJournalEntry, InstanceStateRecord, MarketBar, SensorReading, SpreadStateRecord, StatusRecord, SystemConfig, TradeJournalEntry, UniverseRecord
WRITER_MODULE = 'protocol.writer'

def _writer_error(message: str, **context: Any) -> ProtocolError:
    return ProtocolError(message, module=WRITER_MODULE, context=context)

def _ensure_dict(data: dict[str, Any], label: str) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise _writer_error(f'{label} data must be a dict', label=label, value_type=type(data).__name__)
    return data

def write_json(data: dict[str, Any]) -> str:
    payload = _ensure_dict(data, 'json')
    try:
        return json.dumps(payload, ensure_ascii=False, separators=(',', ':'), sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise _writer_error('failed to serialize JSON', error=str(exc)) from exc

def write_json_pretty(data: dict[str, Any]) -> str:
    payload = _ensure_dict(data, 'json')
    try:
        return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + '\n'
    except (TypeError, ValueError) as exc:
        raise _writer_error('failed to serialize JSON', error=str(exc)) from exc

def _assert_jsonl_safe_values(data: dict[str, Any], label: str) -> None:
    for key, value in data.items():
        if isinstance(value, str) and ('\n' in value or '\r' in value):
            raise _writer_error('JSONL value must not contain newline characters', label=label, field=key)
        if isinstance(value, dict):
            _assert_jsonl_safe_values(value, label)
        if isinstance(value, list):
            for index, item in enumerate(value):
                if isinstance(item, str) and ('\n' in item or '\r' in item):
                    raise _writer_error('JSONL value must not contain newline characters', label=label, field=f'{key}[{index}]')
                if isinstance(item, dict):
                    _assert_jsonl_safe_values(item, label)

def write_jsonl_line(data: dict[str, Any]) -> str:
    payload = _ensure_dict(data, 'jsonl')
    _assert_jsonl_safe_values(payload, 'jsonl')
    line = write_json(payload)
    if '\n' in line or '\r' in line:
        raise _writer_error('JSONL line must not contain newline characters')
    return line

def write_system_config(config: SystemConfig) -> str:
    return write_json_pretty(config.to_dict())

def write_status(record: StatusRecord) -> str:
    return write_json_pretty(record.to_dict())

def write_universe(record: UniverseRecord) -> str:
    return write_json_pretty(record.to_dict())

def write_control(command: ControlCommand) -> str:
    return write_json_pretty(command.to_dict())

def write_ack(record: AckRecord) -> str:
    return write_json_pretty(record.to_dict())

def write_instance_state(record: InstanceStateRecord) -> str:
    return write_json_pretty(record.to_dict())

def write_spread_state(record: SpreadStateRecord) -> str:
    return write_json_pretty(record.to_dict())

def write_decision_journal_entry(entry: DecisionJournalEntry) -> str:
    return write_jsonl_line(entry.to_dict())

def write_trade_journal_entry(entry: TradeJournalEntry) -> str:
    return write_jsonl_line(entry.to_dict())

def write_error_journal_entry(entry: ErrorJournalEntry) -> str:
    return write_jsonl_line(entry.to_dict())

def _write_csv_rows(rows: Iterable[dict[str, Any]], columns: tuple[str, ...], label: str) -> str:
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=list(columns), lineterminator='\n', extrasaction='raise')
    writer.writeheader()
    for index, row in enumerate(rows, start=1):
        if set(row.keys()) != set(columns):
            raise _writer_error('CSV row columns do not match expected schema', label=label, row=index, expected=list(columns), actual=list(row.keys()))
        writer.writerow({column: row[column] for column in columns})
    return output.getvalue()

def write_market_csv(bars: Sequence[MarketBar]) -> str:
    rows = [bar.to_dict() for bar in bars]
    return _write_csv_rows(rows, MARKET_CSV_COLUMNS, 'market')

def write_sensor_csv(readings: Sequence[SensorReading]) -> str:
    rows = [reading.to_dict() for reading in readings]
    return _write_csv_rows(rows, SENSOR_CSV_COLUMNS, 'sensor')

def required_fields_present(data: dict[str, Any], required: Sequence[str]) -> bool:
    return all((field in data for field in required))
STATUS_REQUIRED_FIELDS: tuple[str, ...] = ('schema_version', 'timestamp_utc', 'account_id', 'connected', 'trade_allowed', 'balance', 'equity', 'margin_free', 'ea_version')
UNIVERSE_REQUIRED_FIELDS: tuple[str, ...] = ('schema_version', 'timestamp_utc', 'session', 'market_regime', 'news_window_active')
CONTROL_REQUIRED_FIELDS: tuple[str, ...] = ('schema_version', 'timestamp_utc', 'command_id', 'account_id', 'symbol', 'magic', 'action', 'reason', 'decision_id')
ACK_REQUIRED_FIELDS: tuple[str, ...] = ('schema_version', 'timestamp_utc', 'command_id', 'account_id', 'symbol', 'magic', 'status')
DECISION_JOURNAL_REQUIRED_FIELDS: tuple[str, ...] = ('decision_id', 'timestamp_utc', 'account_id', 'symbol', 'magic', 'decision', 'reason', 'risk_result')
TRADE_JOURNAL_REQUIRED_FIELDS: tuple[str, ...] = ('trade_id', 'timestamp_utc', 'account_id', 'symbol', 'magic', 'event', 'command_id', 'ack_status', 'reason')
ERROR_JOURNAL_REQUIRED_FIELDS: tuple[str, ...] = ('error_id', 'timestamp_utc', 'account_id', 'module', 'error_type', 'message')
SYSTEM_CONFIG_REQUIRED_FIELDS: tuple[str, ...] = ('schema_version', 'system', 'paths', 'runtime', 'instances', 'risk', 'analysis', 'journal', 'trade_management', 'dashboard', 'logging')
INSTANCE_STATE_REQUIRED_FIELDS: tuple[str, ...] = ('schema_version', 'account_id', 'symbol', 'magic', 'last_decision', 'last_reason', 'last_command_id', 'last_ack_status', 'instrument_digits', 'instrument_point', 'instrument_pip', 'cycle_count', 'last_cycle_utc')
SPREAD_STATE_REQUIRED_FIELDS: tuple[str, ...] = ('schema_version', 'account_id', 'symbol', 'magic', 'sample_count', 'mean_spread', 'std_spread', 'median_spread', 'current_spread', 'relative_spread', 'updated_utc')
