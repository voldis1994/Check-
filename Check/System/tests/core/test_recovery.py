from __future__ import annotations
import json
import shutil
from pathlib import Path
import pytest
from engine.core.atomic_io import atomic_write_text
from engine.core.instance import Instance
from engine.core.lifecycle import startup
from engine.core.paths import SystemPaths
from engine.core.recovery import AckRecoveryResult, InstanceRecoveryResult, RuntimeRecoveryResult, UnconfirmedControlInfo, detect_unconfirmed_control, is_control_republish_allowed, is_terminal_ack_status, load_status_for_recovery, order_command_from_control, read_control_command_if_exists, recover_instance, recover_pending_ack, recover_spread_model_from_sensor, reconcile_instance_cache, reload_instance_state_from_disk, run_runtime_recovery, sync_position_with_status
from engine.core.retry import validate_control_command_retry
from engine.execution.ack_reader import build_ack_path
from engine.execution.command import OrderCommand
from engine.core.history import read_archived_control_text
from engine.execution.control_writer import build_control_path, publish_control
from engine.journal.error_journal import build_error_journal_path
from engine.normalizer.spread_model import update_spread_model
from engine.protocol.constants import AckStatus, Decision, ErrorType, OrderAction, PROTOCOL_SCHEMA_VERSION, Side
from engine.protocol.errors import ExecutionError
from engine.protocol.models import StatusRecord
from engine.protocol.parser import parse_control, parse_error_journal_line
from engine.state.instance_state import InstanceState
from engine.state.spread_state import SpreadState
from tests.core.config_payload import valid_system_config_payload
FIXTURES_DIR = Path(__file__).parent.parent / 'loader' / 'fixtures'
FIXED_COMMAND_ID = 'cmd-recovery-1'

def _write_config(root: Path) -> Path:
    payload = valid_system_config_payload()
    payload['system']['root_path'] = str(root)
    payload['analysis'] = {**payload['analysis'], 'lookback_bars': 3}
    config_dir = root / 'config'
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / 'system.json'
    config_path.write_text(json.dumps(payload), encoding='utf-8')
    return config_path

def _instance() -> Instance:
    return Instance(account_id='12345', symbol='EURUSD', magic=100001)

def _install_valid_fixtures(paths: SystemPaths, instance: Instance) -> None:
    paths.ensure_account_directories(instance.account_id)
    account_dir = paths.account_dir(instance.account_id)
    market_csv = 'time_utc,open,high,low,close,volume,symbol,timeframe,digits,point\n2026-07-07T06:00:00.000Z,1.10000,1.10200,1.09900,1.10150,120,EURUSD,M1,5,0.00001\n2026-07-07T06:01:00.000Z,1.10150,1.10300,1.10050,1.10220,110,EURUSD,M1,5,0.00001\n2026-07-07T06:02:00.000Z,1.10220,1.10400,1.10100,1.10310,105,EURUSD,M1,5,0.00001\n'
    (account_dir / instance.market_filename()).write_text(market_csv, encoding='utf-8')
    shutil.copyfile(FIXTURES_DIR / 'sensor_valid.csv', account_dir / instance.sensor_filename())
    shutil.copyfile(FIXTURES_DIR / 'status_valid.json', account_dir / instance.status_filename())
    shutil.copyfile(FIXTURES_DIR / 'universe_valid.json', account_dir / 'universe.json')

def _startup_runtime(tmp_path: Path):
    config_path = _write_config(tmp_path)
    instance = _instance()
    _install_valid_fixtures(SystemPaths(tmp_path), instance)
    runtime = startup(root_path=tmp_path, config_path=config_path)
    return (runtime, instance)

def _open_order_command(command_id: str=FIXED_COMMAND_ID) -> OrderCommand:
    return OrderCommand(command_id=command_id, action=OrderAction.OPEN.value, reason='BUY: preferred side selected', decision_id='decision-recovery-1', side=Side.BUY.value, volume=0.1, stop_loss=1.0988, take_profit=1.1117)

def _publish_open_control(paths: SystemPaths, instance: Instance, command_id: str=FIXED_COMMAND_ID) -> None:
    publish_control(paths, instance, _open_order_command(command_id), timestamp_utc='2026-07-07T06:00:00.000Z')

def _ack_payload(*, command_id: str, status: str, ticket: int=555) -> str:
    return f'{{\n  "schema_version": "{PROTOCOL_SCHEMA_VERSION}",\n  "timestamp_utc": "2026-07-07T06:00:00.000Z",\n  "command_id": "{command_id}",\n  "account_id": "12345",\n  "symbol": "EURUSD",\n  "magic": 100001,\n  "status": "{status}",\n  "ticket": {ticket}\n}}'

def test_is_terminal_ack_status_recognizes_terminal_values() -> None:
    assert is_terminal_ack_status(AckStatus.SUCCESS.value)
    assert is_terminal_ack_status(AckStatus.TIMEOUT.value)
    assert not is_terminal_ack_status('PENDING')

def test_order_command_from_control_maps_fields(tmp_path: Path) -> None:
    paths = SystemPaths(tmp_path)
    instance = _instance()
    paths.ensure_account_directories(instance.account_id)
    publish_control(paths, instance, _open_order_command(), timestamp_utc='2026-07-07T06:00:00.000Z')
    control = read_control_command_if_exists(paths, instance)
    assert control is not None
    order_command = order_command_from_control(control)
    assert order_command.command_id == FIXED_COMMAND_ID
    assert order_command.action == OrderAction.OPEN.value
    assert order_command.side == Side.BUY.value

def test_reload_instance_state_from_disk_restores_persisted_state(tmp_path: Path) -> None:
    runtime, instance = _startup_runtime(tmp_path)
    item = runtime.memory.get(instance)
    assert item is not None
    item.instance_state.update_cycle(decision='BUY', reason='TREND', cycle_utc='2026-07-07T06:00:00.000Z')
    snapshot = update_spread_model((0.0001,), current_spread=0.0002, lookback_bars=3)
    item.spread_state.update_from_snapshot(snapshot, '2026-07-07T06:00:00.000Z')
    item.instance_state.save(runtime.paths)
    item.spread_state.save(runtime.paths)
    item.instance_state.update_cycle(decision='WAIT', reason='RESET', cycle_utc='2026-07-07T06:01:00.000Z')
    assert reload_instance_state_from_disk(runtime, instance) is True
    reloaded = runtime.memory.get(instance)
    assert reloaded is not None
    assert reloaded.instance_state.last_decision == 'BUY'
    assert reloaded.spread_state.record is not None
    assert reloaded.spread_state.record.current_spread == 0.0002

def test_detect_unconfirmed_control_finds_pending_open_control(tmp_path: Path) -> None:
    runtime, instance = _startup_runtime(tmp_path)
    _publish_open_control(runtime.paths, instance)
    item = runtime.memory.get(instance)
    assert item is not None
    unconfirmed = detect_unconfirmed_control(runtime.paths, instance, item.instance_state)
    assert isinstance(unconfirmed, UnconfirmedControlInfo)
    assert unconfirmed.control.command_id == FIXED_COMMAND_ID
    assert unconfirmed.pending_ack is True

def test_recover_pending_ack_marks_timeout_when_ack_missing(tmp_path: Path) -> None:
    runtime, instance = _startup_runtime(tmp_path)
    _publish_open_control(runtime.paths, instance)
    item = runtime.memory.get(instance)
    assert item is not None
    unconfirmed = detect_unconfirmed_control(runtime.paths, instance, item.instance_state)
    assert unconfirmed is not None
    result = recover_pending_ack(runtime, instance, unconfirmed=unconfirmed, timestamp_utc='2026-07-07T06:00:00.000Z')
    assert isinstance(result, AckRecoveryResult)
    assert result.recovered is True
    assert result.timed_out is True
    assert result.command_id == FIXED_COMMAND_ID
    assert item.instance_state.last_command_id == FIXED_COMMAND_ID
    assert item.instance_state.last_ack_status == AckStatus.TIMEOUT.value
    error_path = build_error_journal_path(runtime.paths, instance)
    assert error_path.exists()
    error_entry = parse_error_journal_line(error_path.read_text(encoding='utf-8').strip())
    assert error_entry.error_type == ErrorType.EXECUTION.value
    assert error_entry.context['command_id'] == FIXED_COMMAND_ID
    assert not build_control_path(runtime.paths, instance).exists()
    archived_control = runtime.paths.instance_history_dir(instance.account_id, instance.symbol, instance.magic) / instance.control_filename()
    assert archived_control.exists()

def test_recover_pending_ack_applies_success_ack_and_position(tmp_path: Path) -> None:
    runtime, instance = _startup_runtime(tmp_path)
    _publish_open_control(runtime.paths, instance)
    atomic_write_text(build_ack_path(runtime.paths, instance), _ack_payload(command_id=FIXED_COMMAND_ID, status=AckStatus.SUCCESS.value, ticket=888))
    item = runtime.memory.get(instance)
    assert item is not None
    unconfirmed = detect_unconfirmed_control(runtime.paths, instance, item.instance_state)
    assert unconfirmed is not None
    result = recover_pending_ack(runtime, instance, unconfirmed=unconfirmed)
    assert result.recovered is True
    assert result.timed_out is False
    assert item.instance_state.last_ack_status == AckStatus.SUCCESS.value
    assert item.instance_state.open_ticket == 888
    assert item.instance_state.position_side == Side.BUY.value
    assert item.instance_state.position_volume == pytest.approx(0.1)
    assert item.instance_state.position_entry_price == pytest.approx(1.1031)

def test_recover_pending_ack_applies_late_success_after_timeout(tmp_path: Path) -> None:
    runtime, instance = _startup_runtime(tmp_path)
    _publish_open_control(runtime.paths, instance)
    item = runtime.memory.get(instance)
    assert item is not None
    unconfirmed = detect_unconfirmed_control(runtime.paths, instance, item.instance_state)
    assert unconfirmed is not None
    timeout_result = recover_pending_ack(runtime, instance, unconfirmed=unconfirmed, timestamp_utc='2026-07-07T06:00:00.000Z')
    assert timeout_result.timed_out is True
    assert item.instance_state.last_ack_status == AckStatus.TIMEOUT.value
    atomic_write_text(build_ack_path(runtime.paths, instance), _ack_payload(command_id=FIXED_COMMAND_ID, status=AckStatus.SUCCESS.value, ticket=999))
    late_result = recover_pending_ack(runtime, instance, unconfirmed=unconfirmed)
    assert late_result.recovered is True
    assert late_result.timed_out is False
    assert item.instance_state.last_ack_status == AckStatus.SUCCESS.value
    assert item.instance_state.open_ticket == 999
    assert item.instance_state.position_entry_price == pytest.approx(1.1031)

def test_unconfirmed_control_is_not_republished_without_new_decision(tmp_path: Path) -> None:
    runtime, instance = _startup_runtime(tmp_path)
    _publish_open_control(runtime.paths, instance)
    control_path = build_control_path(runtime.paths, instance)
    control_before = control_path.read_text(encoding='utf-8')
    item = runtime.memory.get(instance)
    assert item is not None
    unconfirmed = detect_unconfirmed_control(runtime.paths, instance, item.instance_state)
    assert unconfirmed is not None
    assert not is_control_republish_allowed(item.instance_state, unconfirmed, proposed_command_id=FIXED_COMMAND_ID)
    recover_instance(runtime, instance, timestamp_utc='2026-07-07T06:00:00.000Z')
    archived_control_text = read_archived_control_text(runtime.paths, instance)
    assert archived_control_text is not None
    assert archived_control_text == control_before
    assert not control_path.exists()
    item.instance_state.update_execution(command_id=FIXED_COMMAND_ID, ack_status=AckStatus.TIMEOUT.value)
    with pytest.raises(ExecutionError, match='must not be retried'):
        validate_control_command_retry(previous_command_id=item.instance_state.last_command_id, command_id=FIXED_COMMAND_ID)

def test_recover_spread_model_from_sensor_rebuilds_runtime_spread_model(tmp_path: Path) -> None:
    runtime, instance = _startup_runtime(tmp_path)
    runtime.spread_models.pop(instance.instance_key, None)
    item = runtime.memory.get(instance)
    assert item is not None
    item.spread_state.record = None
    snapshot = recover_spread_model_from_sensor(runtime, instance, timestamp_utc='2026-07-07T06:00:00.000Z')
    assert snapshot is not None
    assert snapshot.sample_count >= 1
    assert instance.instance_key in runtime.spread_models
    assert item.spread_state.record is not None
    assert item.spread_state.record.current_spread == snapshot.current_spread

def test_sync_position_with_status_updates_risk_metrics() -> None:
    state = InstanceState(instance=_instance())
    status = StatusRecord(schema_version=PROTOCOL_SCHEMA_VERSION, timestamp_utc='2026-07-07T06:00:00.000Z', account_id='12345', connected=True, trade_allowed=True, balance=10000.0, equity=10050.0, margin_free=9800.0, ea_version='1.0.0')
    assert sync_position_with_status(state, status, _instance()) is True
    assert state.day_start_balance == pytest.approx(10000.0)
    assert state.peak_equity == pytest.approx(10050.0)

def test_load_status_for_recovery_returns_valid_status(tmp_path: Path) -> None:
    runtime, instance = _startup_runtime(tmp_path)
    status = load_status_for_recovery(runtime, instance)
    assert status is not None
    assert status.account_id == '12345'
    assert status.connected is True

def test_reconcile_instance_cache_removes_hash_files(tmp_path: Path) -> None:
    runtime, instance = _startup_runtime(tmp_path)
    cache_dir = runtime.paths.instance_cache_dir(instance.account_id, instance.symbol, instance.magic)
    (cache_dir / 'last_sensor.hash').write_text('{}', encoding='utf-8')
    assert reconcile_instance_cache(runtime, instance) is True
    assert not (cache_dir / 'last_sensor.hash').exists()

def test_recover_instance_runs_full_recovery_pipeline(tmp_path: Path) -> None:
    runtime, instance = _startup_runtime(tmp_path)
    item = runtime.memory.get(instance)
    assert item is not None
    item.instance_state.update_cycle(decision=Decision.BUY.value, reason='TREND', cycle_utc='2026-07-07T06:00:00.000Z')
    item.instance_state.save(runtime.paths)
    result = recover_instance(runtime, instance, timestamp_utc='2026-07-07T06:00:00.000Z')
    assert isinstance(result, InstanceRecoveryResult)
    assert result.state_reloaded is True
    assert result.spread_recovered is True
    assert result.instance == instance

def test_run_runtime_recovery_processes_all_instances(tmp_path: Path) -> None:
    runtime, instance = _startup_runtime(tmp_path)
    result = run_runtime_recovery(runtime, timestamp_utc='2026-07-07T06:00:00.000Z')
    assert isinstance(result, RuntimeRecoveryResult)
    assert result.instance_count == 1
    assert result.instance_results[0].instance == instance

def test_read_control_command_if_exists_returns_none_when_missing(tmp_path: Path) -> None:
    runtime, instance = _startup_runtime(tmp_path)
    assert read_control_command_if_exists(runtime.paths, instance) is None

def test_detect_unconfirmed_control_ignores_resolved_command(tmp_path: Path) -> None:
    runtime, instance = _startup_runtime(tmp_path)
    _publish_open_control(runtime.paths, instance)
    item = runtime.memory.get(instance)
    assert item is not None
    item.instance_state.update_execution(command_id=FIXED_COMMAND_ID, ack_status=AckStatus.SUCCESS.value)
    assert detect_unconfirmed_control(runtime.paths, instance, item.instance_state) is None

def test_is_control_republish_allowed_after_terminal_ack(tmp_path: Path) -> None:
    runtime, instance = _startup_runtime(tmp_path)
    _publish_open_control(runtime.paths, instance)
    item = runtime.memory.get(instance)
    assert item is not None
    item.instance_state.update_execution(command_id=FIXED_COMMAND_ID, ack_status=AckStatus.TIMEOUT.value)
    unconfirmed = detect_unconfirmed_control(runtime.paths, instance, item.instance_state)
    assert is_control_republish_allowed(item.instance_state, unconfirmed, proposed_command_id='cmd-new-decision')

def test_recover_instance_persists_reloaded_state_to_disk(tmp_path: Path) -> None:
    runtime, instance = _startup_runtime(tmp_path)
    recover_spread_model_from_sensor(runtime, instance, timestamp_utc='2026-07-07T06:00:00.000Z')
    recover_instance(runtime, instance, timestamp_utc='2026-07-07T06:00:00.000Z')
    loaded_spread = SpreadState.load(runtime.paths, instance)
    assert loaded_spread.record is not None
    loaded_state = InstanceState.load(runtime.paths, instance)
    assert loaded_state.last_command_id == runtime.memory.get(instance).instance_state.last_command_id
