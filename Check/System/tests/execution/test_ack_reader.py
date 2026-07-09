from __future__ import annotations
import pytest
from engine.core.atomic_io import atomic_write_text
from engine.core.instance import Instance
from engine.core.paths import SystemPaths
from engine.execution.ack_reader import AckInterpretation, build_ack_path, build_ack_timeout_interpretation, interpret_ack, read_ack_for_command, read_ack_for_command_with_journal, read_ack_record, validate_ack_record
from engine.journal.error_journal import build_error_journal_path
from engine.protocol.constants import AckStatus, PROTOCOL_SCHEMA_VERSION
from engine.protocol.errors import ExecutionError, ProtocolError
from engine.protocol.models import AckRecord
from engine.protocol.parser import parse_ack, parse_error_journal_line

def _instance() -> Instance:
    return Instance(account_id='12345', symbol='EURUSD', magic=100001)

def _ack_payload(*, status: str, command_id: str='cmd-1', ticket: int | None=555) -> str:
    ticket_field = f',\n  "ticket": {ticket}' if ticket is not None else ''
    return f'{{\n  "schema_version": "{PROTOCOL_SCHEMA_VERSION}",\n  "timestamp_utc": "2026-07-07T06:00:00.000Z",\n  "command_id": "{command_id}",\n  "account_id": "12345",\n  "symbol": "EURUSD",\n  "magic": 100001,\n  "status": "{status}"{ticket_field}\n}}'

def _write_ack(tmp_path, payload: str) -> SystemPaths:
    paths = SystemPaths(root_path=tmp_path)
    instance = _instance()
    paths.ensure_account_directories(instance.account_id)
    atomic_write_text(build_ack_path(paths, instance), payload)
    return paths

def test_build_ack_path_uses_instance_filename(tmp_path) -> None:
    paths = SystemPaths(root_path=tmp_path)
    ack_path = build_ack_path(paths, _instance())
    assert ack_path.name == 'ack_EURUSD_100001.json'
    assert ack_path.parent.name == '12345'

def test_read_ack_record_parses_valid_ack_json(tmp_path) -> None:
    paths = _write_ack(tmp_path, _ack_payload(status=AckStatus.SUCCESS.value))
    ack_record = read_ack_record(paths, _instance())
    assert ack_record.status == AckStatus.SUCCESS.value
    assert ack_record.command_id == 'cmd-1'
    assert ack_record.ticket == 555

def test_interpret_ack_success_failed_and_rejected() -> None:
    success = interpret_ack(AckRecord(schema_version=PROTOCOL_SCHEMA_VERSION, timestamp_utc='2026-07-07T06:00:00.000Z', command_id='cmd-1', account_id='12345', symbol='EURUSD', magic=100001, status=AckStatus.SUCCESS.value, ticket=555))
    failed = interpret_ack(AckRecord(schema_version=PROTOCOL_SCHEMA_VERSION, timestamp_utc='2026-07-07T06:00:00.000Z', command_id='cmd-2', account_id='12345', symbol='EURUSD', magic=100001, status=AckStatus.FAILED.value, error_code=10006, error_message='trade failed'))
    rejected = interpret_ack(AckRecord(schema_version=PROTOCOL_SCHEMA_VERSION, timestamp_utc='2026-07-07T06:00:00.000Z', command_id='cmd-3', account_id='12345', symbol='EURUSD', magic=100001, status=AckStatus.REJECTED.value))
    assert success.is_success
    assert not success.is_failed
    assert not success.is_rejected
    assert not success.is_timeout
    assert failed.is_failed
    assert not failed.is_success
    assert rejected.is_rejected
    assert not rejected.is_success

def test_build_ack_timeout_interpretation_marks_timeout_state() -> None:
    interpretation = build_ack_timeout_interpretation(command_id='cmd-timeout')
    assert isinstance(interpretation, AckInterpretation)
    assert interpretation.status == AckStatus.TIMEOUT.value
    assert interpretation.is_timeout
    assert not interpretation.is_success
    assert interpretation.ack_record is None

def test_validate_ack_record_requires_matching_command_id() -> None:
    ack_record = parse_ack(_ack_payload(status=AckStatus.SUCCESS.value))
    validate_ack_record(ack_record, _instance(), expected_command_id='cmd-1')
    with pytest.raises(ExecutionError, match='command_id does not match'):
        validate_ack_record(ack_record, _instance(), expected_command_id='cmd-other')

def test_validate_ack_record_requires_matching_instance() -> None:
    ack_record = parse_ack(_ack_payload(status=AckStatus.SUCCESS.value))
    other_instance = Instance(account_id='12345', symbol='GBPUSD', magic=100002)
    with pytest.raises(ExecutionError, match='instance does not match'):
        validate_ack_record(ack_record, other_instance, expected_command_id='cmd-1')

def test_read_ack_for_command_reads_and_validates_matching_ack(tmp_path) -> None:
    paths = _write_ack(tmp_path, _ack_payload(status=AckStatus.SUCCESS.value))
    ack_record = read_ack_for_command(paths, _instance(), expected_command_id='cmd-1')
    assert ack_record.status == AckStatus.SUCCESS.value
    assert interpret_ack(ack_record).is_success

def test_read_ack_for_command_with_journal_logs_invalid_ack_and_reraises(tmp_path) -> None:
    paths = _write_ack(tmp_path, _ack_payload(status=AckStatus.SUCCESS.value, command_id='cmd-wrong'))
    instance = _instance()
    with pytest.raises(ExecutionError, match='command_id does not match'):
        read_ack_for_command_with_journal(paths, instance, expected_command_id='cmd-1')
    journal_text = build_error_journal_path(paths, instance).read_text(encoding='utf-8')
    entry = parse_error_journal_line(journal_text.strip())
    assert entry.module == 'execution.ack_reader'
    assert 'command_id does not match' in entry.message

def test_read_ack_for_command_with_journal_logs_parse_errors(tmp_path) -> None:
    paths = SystemPaths(root_path=tmp_path)
    instance = _instance()
    paths.ensure_account_directories(instance.account_id)
    atomic_write_text(build_ack_path(paths, instance), '{not-json')
    instance = _instance()
    with pytest.raises(ProtocolError):
        read_ack_for_command_with_journal(paths, instance, expected_command_id='cmd-1')
    journal_text = build_error_journal_path(paths, instance).read_text(encoding='utf-8')
    entry = parse_error_journal_line(journal_text.strip())
    assert entry.module == 'execution.ack_reader'
    assert entry.error_type == 'PROTOCOL'
