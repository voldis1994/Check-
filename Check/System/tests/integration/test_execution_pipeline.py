from __future__ import annotations
import json
from dataclasses import dataclass
from typing import Callable
import pytest
from engine.core.atomic_io import atomic_write_text
from engine.core.instance import Instance
from engine.core.lifecycle import LiveRuntime
from engine.core.paths import SystemPaths
from engine.core.cycle import should_execute_trade
from engine.execution.ack_reader import build_ack_path
from engine.core.history import read_archived_control_text
from engine.execution.control_writer import build_control_path
from engine.execution.engine import ExecutionResult, run_execution_engine
from engine.journal.error_journal import build_error_journal_path
from engine.journal.trade_journal import build_trade_journal_path
from engine.protocol.constants import AckStatus, Decision, ErrorType, OrderAction, PROTOCOL_SCHEMA_VERSION, RiskResult, TradeEvent
from engine.protocol.parser import parse_control, parse_error_journal_line, parse_trade_journal_line
from engine.protocol.writer import TRADE_JOURNAL_REQUIRED_FIELDS
from engine.risk.engine import RiskEngineResult
from engine.decision.engine import DecisionResult
from engine.state.instance_state import InstanceState
from tests.integration.test_decision_pipeline import _startup_runtime, run_instance_decision_pipeline
from tests.protocol.test_writer import required_fields_present
FIXED_COMMAND_ID = 'cmd-integration-exec-1'
MODULE_NAME = 'integration.execution_pipeline'

@dataclass(frozen=True)
class ExecutionPipelineResult:
    decision_completed: bool
    execution_completed: bool
    trade_executed: bool
    decision_result: DecisionResult | None = None
    risk_engine_result: RiskEngineResult | None = None
    execution_result: ExecutionResult | None = None

def _patch_fixed_command_id(monkeypatch: pytest.MonkeyPatch) -> None:
    counter = {'value': 0}

    def _uuid4() -> str:
        counter['value'] += 1
        return FIXED_COMMAND_ID if counter['value'] == 1 else f'cmd-integration-exec-{counter['value']}'
    monkeypatch.setattr('engine.execution.command.uuid4', _uuid4)

def _ack_payload(*, status: str, command_id: str=FIXED_COMMAND_ID, ticket: int | None=555, error_code: int | None=None, error_message: str | None=None) -> str:
    ticket_field = f',\n  "ticket": {ticket}' if ticket is not None else ''
    error_fields = ''
    if error_code is not None:
        error_fields += f',\n  "error_code": {error_code}'
    if error_message is not None:
        error_fields += f',\n  "error_message": "{error_message}"'
    return f'{{\n  "schema_version": "{PROTOCOL_SCHEMA_VERSION}",\n  "timestamp_utc": "2026-07-07T06:03:00.000Z",\n  "command_id": "{command_id}",\n  "account_id": "12345",\n  "symbol": "EURUSD",\n  "magic": 100001,\n  "status": "{status}"{ticket_field}{error_fields}\n}}'

def _write_ack(paths: SystemPaths, instance: Instance, payload: str) -> None:
    paths.ensure_account_directories(instance.account_id)
    atomic_write_text(build_ack_path(paths, instance), payload)

def run_instance_execution_pipeline(runtime: LiveRuntime, instance: Instance, *, use_global_universe: bool | None=None, timestamp_utc: str='2026-07-07T06:03:00.000Z', ack_payload: str | None=None, started_monotonic: float | None=None, monotonic_fn: Callable[[], float] | None=None, sleep_fn: Callable[[float], None] | None=None) -> ExecutionPipelineResult:
    decision_result = run_instance_decision_pipeline(runtime, instance, use_global_universe=use_global_universe, timestamp_utc=timestamp_utc)
    if not decision_result.completed:
        return ExecutionPipelineResult(decision_completed=False, execution_completed=False, trade_executed=False)
    if decision_result.decision_result is None or decision_result.risk_engine_result is None:
        return ExecutionPipelineResult(decision_completed=False, execution_completed=False, trade_executed=False)
    trade_executed = should_execute_trade(runtime=runtime, decision_result=decision_result.decision_result, risk_engine_result=decision_result.risk_engine_result)
    if ack_payload is not None:
        _write_ack(runtime.paths, instance, ack_payload)
    memory = runtime.memory.get_or_create(instance)
    execution_kwargs: dict[str, object] = {'paths': runtime.paths, 'instance': instance, 'instance_state': memory.instance_state, 'decision_result': decision_result.decision_result, 'risk_engine_result': decision_result.risk_engine_result, 'runtime': runtime.config.runtime, 'timestamp_utc': timestamp_utc}
    if started_monotonic is not None:
        execution_kwargs['started_monotonic'] = started_monotonic
    if monotonic_fn is not None:
        execution_kwargs['monotonic_fn'] = monotonic_fn
    if sleep_fn is not None:
        execution_kwargs['sleep_fn'] = sleep_fn
    execution_result = run_execution_engine(**execution_kwargs)
    memory.instance_state.save(runtime.paths)
    return ExecutionPipelineResult(decision_completed=True, execution_completed=True, trade_executed=trade_executed, decision_result=decision_result.decision_result, risk_engine_result=decision_result.risk_engine_result, execution_result=execution_result)

def _assert_tradeable_decision(decision_result: DecisionResult, risk_engine_result: RiskEngineResult) -> None:
    assert decision_result.decision in {Decision.BUY.value, Decision.SELL.value}
    assert risk_engine_result.result == RiskResult.ALLOW.value

def test_control_file_is_created(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_fixed_command_id(monkeypatch)
    runtime, instance = _startup_runtime(tmp_path)
    result = run_instance_execution_pipeline(runtime, instance, use_global_universe=False, ack_payload=_ack_payload(status=AckStatus.SUCCESS.value, ticket=555))
    assert result.decision_completed
    assert result.execution_completed
    assert result.decision_result is not None
    assert result.risk_engine_result is not None
    assert result.execution_result is not None
    _assert_tradeable_decision(result.decision_result, result.risk_engine_result)
    assert result.trade_executed
    assert result.execution_result.control_published is True
    assert result.execution_result.order_command.action == OrderAction.OPEN.value
    archived_control_text = read_archived_control_text(runtime.paths, instance)
    assert archived_control_text is not None
    control = parse_control(archived_control_text)
    assert control.command_id == FIXED_COMMAND_ID
    assert control.action == OrderAction.OPEN.value
    assert control.side == result.decision_result.preferred_side

def test_simulated_ack_updates_instance_state(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_fixed_command_id(monkeypatch)
    runtime, instance = _startup_runtime(tmp_path)
    result = run_instance_execution_pipeline(runtime, instance, use_global_universe=False, ack_payload=_ack_payload(status=AckStatus.SUCCESS.value, ticket=777))
    assert result.decision_completed
    assert result.execution_completed
    assert result.decision_result is not None
    assert result.risk_engine_result is not None
    assert result.execution_result is not None
    _assert_tradeable_decision(result.decision_result, result.risk_engine_result)
    assert result.execution_result.state_updated is True
    assert result.execution_result.ack_interpretation is not None
    assert result.execution_result.ack_interpretation.is_success is True
    memory = runtime.memory.get_or_create(instance)
    assert memory.instance_state.last_command_id == FIXED_COMMAND_ID
    assert memory.instance_state.last_ack_status == AckStatus.SUCCESS.value
    assert memory.instance_state.open_ticket == 777
    assert memory.instance_state.position_side == result.decision_result.preferred_side
    assert memory.instance_state.position_volume == result.risk_engine_result.position_size
    reloaded = InstanceState.load(runtime.paths, instance)
    assert reloaded.last_command_id == FIXED_COMMAND_ID
    assert reloaded.last_ack_status == AckStatus.SUCCESS.value
    assert reloaded.open_ticket == 777

def test_trade_journal_full_cycle(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_fixed_command_id(monkeypatch)
    runtime, instance = _startup_runtime(tmp_path)
    result = run_instance_execution_pipeline(runtime, instance, use_global_universe=False, ack_payload=_ack_payload(status=AckStatus.SUCCESS.value, ticket=888))
    assert result.decision_completed
    assert result.execution_completed
    assert result.decision_result is not None
    assert result.risk_engine_result is not None
    assert result.execution_result is not None
    _assert_tradeable_decision(result.decision_result, result.risk_engine_result)
    assert result.execution_result.trade_intent_logged is True
    assert result.execution_result.trade_journal_entry is not None
    journal_path = build_trade_journal_path(runtime.paths, instance)
    lines = journal_path.read_text(encoding='utf-8').splitlines()
    assert len(lines) == 1
    entry = parse_trade_journal_line(lines[0])
    payload = json.loads(lines[0])
    assert required_fields_present(payload, TRADE_JOURNAL_REQUIRED_FIELDS)
    assert entry.command_id == FIXED_COMMAND_ID
    assert entry.event == TradeEvent.OPEN.value
    assert entry.side == result.decision_result.preferred_side
    assert entry.volume == result.risk_engine_result.position_size
    assert entry.ack_status == AckStatus.SUCCESS.value
    assert entry.ticket == 888
    assert entry.reason == result.decision_result.reason

def test_failed_ack_writes_error_journal(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_fixed_command_id(monkeypatch)
    runtime, instance = _startup_runtime(tmp_path)
    result = run_instance_execution_pipeline(runtime, instance, use_global_universe=False, ack_payload=_ack_payload(status=AckStatus.FAILED.value, ticket=None, error_code=10006, error_message='trade failed'))
    assert result.decision_completed
    assert result.execution_completed
    assert result.decision_result is not None
    assert result.risk_engine_result is not None
    assert result.execution_result is not None
    _assert_tradeable_decision(result.decision_result, result.risk_engine_result)
    assert result.execution_result.ack_interpretation is not None
    assert result.execution_result.ack_interpretation.is_failed is True
    memory = runtime.memory.get_or_create(instance)
    assert memory.instance_state.last_ack_status == AckStatus.FAILED.value
    assert memory.instance_state.open_ticket is None
    error_path = build_error_journal_path(runtime.paths, instance)
    assert error_path.exists()
    error_entry = parse_error_journal_line(error_path.read_text(encoding='utf-8').strip())
    assert error_entry.module == 'execution.engine'
    assert error_entry.error_type == ErrorType.EXECUTION.value
    assert error_entry.context['command_id'] == FIXED_COMMAND_ID
    assert error_entry.context['status'] == AckStatus.FAILED.value
    assert error_entry.context['error_code'] == 10006
    assert error_entry.context['error_message'] == 'trade failed'
    trade_entry = parse_trade_journal_line(build_trade_journal_path(runtime.paths, instance).read_text(encoding='utf-8').strip())
    assert trade_entry.ack_status == AckStatus.FAILED.value
    assert trade_entry.command_id == FIXED_COMMAND_ID
