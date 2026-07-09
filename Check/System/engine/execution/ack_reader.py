from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from engine.core.atomic_io import atomic_read_text
from engine.core.instance import Instance
from engine.core.paths import SystemPaths
from engine.core.retry import RetryAlertContext, RetryPolicy
from engine.journal.error_journal import log_error
from engine.protocol.constants import AckStatus
from engine.protocol.errors import ExecutionError, SystemError, get_error_type
from engine.protocol.models import AckRecord
from engine.protocol.parser import parse_ack
MODULE_NAME = 'execution.ack_reader'

def _execution_error(message: str, **context: object) -> ExecutionError:
    return ExecutionError(message, module=MODULE_NAME, context=dict(context))

@dataclass(frozen=True)
class AckInterpretation:
    status: str
    command_id: str
    is_success: bool
    is_failed: bool
    is_rejected: bool
    is_timeout: bool
    ack_record: AckRecord | None

def build_ack_path(paths: SystemPaths, instance: Instance) -> Path:
    return paths.account_dir(instance.account_id) / instance.ack_filename()

def read_ack_record(paths: SystemPaths, instance: Instance, *, retry_policy: RetryPolicy | None=None, retry_alert_context: RetryAlertContext | None=None) -> AckRecord:
    ack_path = build_ack_path(paths, instance)
    raw_text = atomic_read_text(ack_path, retry_policy=retry_policy, retry_alert_context=retry_alert_context)
    return parse_ack(raw_text)

def validate_ack_record(ack_record: AckRecord, instance: Instance, *, expected_command_id: str) -> None:
    if ack_record.instance_key.as_tuple() != instance.instance_key:
        raise _execution_error('ack instance does not match target instance', expected=instance.instance_key, actual=ack_record.instance_key.as_tuple())
    if ack_record.command_id != expected_command_id:
        raise _execution_error('ack command_id does not match expected command', expected_command_id=expected_command_id, actual_command_id=ack_record.command_id)

def interpret_ack(ack_record: AckRecord) -> AckInterpretation:
    return AckInterpretation(status=ack_record.status, command_id=ack_record.command_id, is_success=ack_record.status == AckStatus.SUCCESS.value, is_failed=ack_record.status == AckStatus.FAILED.value, is_rejected=ack_record.status == AckStatus.REJECTED.value, is_timeout=False, ack_record=ack_record)

def build_ack_timeout_interpretation(*, command_id: str) -> AckInterpretation:
    return AckInterpretation(status=AckStatus.TIMEOUT.value, command_id=command_id, is_success=False, is_failed=False, is_rejected=False, is_timeout=True, ack_record=None)

def build_timeout_ack_record(instance: Instance, *, command_id: str, timestamp_utc: str) -> AckRecord:
    from engine.protocol.constants import PROTOCOL_SCHEMA_VERSION
    return AckRecord(schema_version=PROTOCOL_SCHEMA_VERSION, timestamp_utc=timestamp_utc, command_id=command_id, account_id=instance.account_id, symbol=instance.symbol, magic=instance.magic, status=AckStatus.FAILED.value, error_message=AckStatus.TIMEOUT.value)

def read_ack_for_command(paths: SystemPaths, instance: Instance, *, expected_command_id: str, retry_policy: RetryPolicy | None=None, retry_alert_context: RetryAlertContext | None=None) -> AckRecord:
    ack_record = read_ack_record(paths, instance, retry_policy=retry_policy, retry_alert_context=retry_alert_context)
    validate_ack_record(ack_record, instance, expected_command_id=expected_command_id)
    return ack_record

def read_ack_for_command_with_journal(paths: SystemPaths, instance: Instance, *, expected_command_id: str, retry_policy: RetryPolicy | None=None, retry_alert_context: RetryAlertContext | None=None) -> AckRecord:
    try:
        return read_ack_for_command(paths, instance, expected_command_id=expected_command_id, retry_policy=retry_policy, retry_alert_context=retry_alert_context)
    except SystemError as exc:
        log_error(paths, instance, module=MODULE_NAME, error_type=get_error_type(exc).value, message=str(exc), context=exc.context if isinstance(exc, SystemError) else {'error': str(exc)})
        raise
