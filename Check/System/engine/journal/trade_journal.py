from __future__ import annotations
import os
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4
from engine.core.atomic_io import atomic_read_text, atomic_write_text
from engine.core.clock import now_utc
from engine.core.instance import Instance
from engine.core.paths import SystemPaths
from engine.protocol.constants import AckStatus, REASON_ACK_TIMEOUT, REASON_EXTERNAL_PARTIAL_CLOSE, REASON_EXTERNAL_POSITION_CLOSE, TradeEvent
from engine.protocol.errors import DataIOError
from engine.protocol.models import AckRecord, TradeJournalEntry
from engine.protocol.parser import parse_trade_journal_line
from engine.protocol.writer import write_trade_journal_entry
from engine.reason import build_reason
MODULE_NAME = 'journal.trade_journal'
INTENT_REASON_PREFIX = 'INTENT:'

@dataclass(frozen=True)
class TradeIntentParams:
    command_id: str
    event: str
    reason: str
    trade_id: str | None = None
    side: str | None = None
    volume: float | None = None
    price: float | None = None
    ticket: int | None = None
    stop_loss: float | None = None

def _data_io_error(message: str, **context: object) -> DataIOError:
    return DataIOError(message, module=MODULE_NAME, context=dict(context))

def _intent_reason(reason: str) -> str:
    stripped = reason.strip()
    if stripped.startswith(INTENT_REASON_PREFIX):
        return stripped
    return f'{INTENT_REASON_PREFIX} {stripped}'

def build_trade_journal_path(paths: SystemPaths, instance: Instance) -> Path:
    return paths.account_journal_dir(instance.account_id) / instance.trade_journal_filename()

def build_trade_intent_entry(instance: Instance, params: TradeIntentParams, *, timestamp_utc: str) -> TradeJournalEntry:
    if params.event not in {TradeEvent.OPEN.value, TradeEvent.MODIFY.value, TradeEvent.CLOSE.value}:
        raise _data_io_error('trade intent event must be OPEN, MODIFY, or CLOSE', event=params.event)
    return TradeJournalEntry(trade_id=params.trade_id or str(uuid4()), timestamp_utc=timestamp_utc, account_id=instance.account_id, symbol=instance.symbol, magic=instance.magic, event=params.event, command_id=params.command_id, ack_status=AckStatus.REJECTED.value, reason=_intent_reason(params.reason), side=params.side, volume=params.volume, price=params.price, ticket=params.ticket, stop_loss=params.stop_loss)

def build_trade_ack_entry(intent_entry: TradeJournalEntry, ack_record: AckRecord, *, timestamp_utc: str, price: float | None=None) -> TradeJournalEntry:
    if intent_entry.command_id != ack_record.command_id:
        raise _data_io_error('ack command_id does not match trade intent', command_id=intent_entry.command_id, ack_command_id=ack_record.command_id)
    if intent_entry.instance_key != ack_record.instance_key:
        raise _data_io_error('ack instance does not match trade intent', intent_instance=intent_entry.instance_key, ack_instance=ack_record.instance_key)
    resolved_ticket = ack_record.ticket if ack_record.ticket is not None else intent_entry.ticket
    resolved_price = price if price is not None else intent_entry.price
    return TradeJournalEntry(trade_id=intent_entry.trade_id, timestamp_utc=timestamp_utc, account_id=intent_entry.account_id, symbol=intent_entry.symbol, magic=intent_entry.magic, event=intent_entry.event, command_id=intent_entry.command_id, ack_status=ack_record.status, reason=intent_entry.reason.removeprefix(f'{INTENT_REASON_PREFIX} ').strip() if intent_entry.reason.startswith(INTENT_REASON_PREFIX) else intent_entry.reason, side=intent_entry.side, volume=intent_entry.volume, price=resolved_price, ticket=resolved_ticket, stop_loss=intent_entry.stop_loss)

def append_trade_journal_entry(paths: SystemPaths, instance: Instance, entry: TradeJournalEntry) -> None:
    journal_path = build_trade_journal_path(paths, instance)
    paths.ensure_account_directories(instance.account_id)
    line = write_trade_journal_entry(entry)
    suffix = '' if line.endswith('\n') else '\n'
    try:
        with journal_path.open('a', encoding='utf-8') as handle:
            handle.write(f'{line}{suffix}')
            handle.flush()
            os.fsync(handle.fileno())
    except OSError as exc:
        raise _data_io_error('failed to append trade journal entry', path=str(journal_path), error=str(exc)) from exc

def _read_journal_lines(journal_path: Path) -> list[str]:
    if not journal_path.exists():
        return []
    content = atomic_read_text(journal_path)
    return [line for line in content.splitlines() if line.strip()]

def update_trade_journal_ack(paths: SystemPaths, instance: Instance, ack_record: AckRecord, *, timestamp_utc: str | None=None, price: float | None=None) -> TradeJournalEntry:
    journal_path = build_trade_journal_path(paths, instance)
    lines = _read_journal_lines(journal_path)
    if not lines:
        raise _data_io_error('trade journal entry not found for ack update', command_id=ack_record.command_id, path=str(journal_path))
    updated_entry: TradeJournalEntry | None = None
    rewritten_lines: list[str] = []
    for line in lines:
        entry = parse_trade_journal_line(line)
        if entry.command_id == ack_record.command_id:
            updated_entry = build_trade_ack_entry(entry, ack_record, timestamp_utc=timestamp_utc or now_utc(), price=price)
            rewritten_lines.append(write_trade_journal_entry(updated_entry))
        else:
            rewritten_lines.append(line)
    if updated_entry is None:
        raise _data_io_error('trade journal entry not found for ack update', command_id=ack_record.command_id, path=str(journal_path))
    output = '\n'.join(rewritten_lines)
    if output:
        output = f'{output}\n'
    atomic_write_text(journal_path, output)
    return updated_entry

def log_trade_ack_timeout(paths: SystemPaths, instance: Instance, *, command_id: str, timestamp_utc: str | None=None) -> TradeJournalEntry:
    journal_path = build_trade_journal_path(paths, instance)
    lines = _read_journal_lines(journal_path)
    if not lines:
        raise _data_io_error('trade journal entry not found for ack timeout update', command_id=command_id, path=str(journal_path))
    updated_entry: TradeJournalEntry | None = None
    rewritten_lines: list[str] = []
    for line in lines:
        entry = parse_trade_journal_line(line)
        if entry.command_id == command_id:
            updated_entry = TradeJournalEntry(trade_id=entry.trade_id, timestamp_utc=timestamp_utc or now_utc(), account_id=entry.account_id, symbol=entry.symbol, magic=entry.magic, event=entry.event, command_id=entry.command_id, ack_status=AckStatus.FAILED.value, reason=build_reason(REASON_ACK_TIMEOUT, 'ack wait timed out', command_id=command_id), side=entry.side, volume=entry.volume, price=entry.price, ticket=entry.ticket, stop_loss=entry.stop_loss)
            rewritten_lines.append(write_trade_journal_entry(updated_entry))
        else:
            rewritten_lines.append(line)
    if updated_entry is None:
        raise _data_io_error('trade journal entry not found for ack timeout update', command_id=command_id, path=str(journal_path))
    output = '\n'.join(rewritten_lines)
    if output:
        output = f'{output}\n'
    atomic_write_text(journal_path, output)
    return updated_entry

def log_trade_intent(paths: SystemPaths, instance: Instance, params: TradeIntentParams, *, timestamp_utc: str | None=None) -> TradeJournalEntry:
    entry = build_trade_intent_entry(instance, params, timestamp_utc=timestamp_utc or now_utc())
    append_trade_journal_entry(paths, instance, entry)
    return entry

def log_trade_ack(paths: SystemPaths, instance: Instance, ack_record: AckRecord, *, timestamp_utc: str | None=None, price: float | None=None) -> TradeJournalEntry:
    return update_trade_journal_ack(paths, instance, ack_record, timestamp_utc=timestamp_utc, price=price)

def log_external_position_close(paths: SystemPaths, instance: Instance, *, ticket: int | None, side: str | None, volume: float | None, timestamp_utc: str | None=None, price: float | None=None, stop_loss: float | None=None, reason: str | None=None) -> TradeJournalEntry:
    resolved_reason = reason or build_reason(REASON_EXTERNAL_POSITION_CLOSE, 'position closed on MT4 without Python CLOSE command', ticket=ticket)
    entry = TradeJournalEntry(trade_id=str(uuid4()), timestamp_utc=timestamp_utc or now_utc(), account_id=instance.account_id, symbol=instance.symbol, magic=instance.magic, event=TradeEvent.CLOSE.value, command_id=f'external-close-{uuid4()}', ack_status=AckStatus.SUCCESS.value, reason=resolved_reason, side=side, volume=volume, ticket=ticket, price=price, stop_loss=stop_loss)
    append_trade_journal_entry(paths, instance, entry)
    return entry

def log_external_partial_position_close(paths: SystemPaths, instance: Instance, *, ticket: int | None, side: str | None, closed_volume: float, remaining_volume: float, timestamp_utc: str | None=None) -> TradeJournalEntry:
    reason = build_reason(REASON_EXTERNAL_PARTIAL_CLOSE, 'position partially closed on MT4 without Python CLOSE command', ticket=ticket, closed_volume=closed_volume, remaining_volume=remaining_volume)
    entry = TradeJournalEntry(trade_id=str(uuid4()), timestamp_utc=timestamp_utc or now_utc(), account_id=instance.account_id, symbol=instance.symbol, magic=instance.magic, event=TradeEvent.CLOSE.value, command_id=f'external-partial-{uuid4()}', ack_status=AckStatus.SUCCESS.value, reason=reason, side=side, volume=closed_volume, ticket=ticket)
    append_trade_journal_entry(paths, instance, entry)
    return entry
