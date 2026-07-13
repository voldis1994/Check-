from __future__ import annotations
import json
import logging
import os
import shutil
import time
from datetime import datetime, timezone
from engine.core.clock import format_utc_timestamp
from pathlib import Path
import pytest
from engine.core.alerts import Alert, alert_level_to_log_level, alerts_affect_trading, build_ack_timeout_alert, build_data_stale_alert, dispatch_cycle_alerts, emit_alert, format_alert_message, should_emit_account_not_tradeable_alert
from engine.core.cycle import InstanceCycleResult
from engine.core.instance import Instance
from engine.core.lifecycle import startup
from engine.core.logging_setup import setup_system_logger
from engine.core.monitoring import INSTANCE_HEALTH_BLOCKED, INSTANCE_HEALTH_ERROR, INSTANCE_HEALTH_VALID, MonitoringState, build_instance_metrics, compute_data_freshness_ms, compute_elapsed_ms, format_metrics_message, is_data_stale, log_instance_metrics, observe_instance_cycle, parse_utc_timestamp, record_cycle_error, resolve_ack_latency_ms, resolve_instance_health
from engine.core.paths import SystemPaths
from engine.execution.command import OrderCommand
from engine.execution.engine import ExecutionResult
from engine.execution.ack_reader import build_ack_timeout_interpretation
from engine.protocol.constants import AlertLevel, Decision, LogLevel, OrderAction, REASON_ACCOUNT_NOT_TRADEABLE, REASON_ACK_TIMEOUT
from tests.core.config_payload import valid_system_config_payload
FIXTURES_DIR = Path(__file__).parent.parent / 'loader' / 'fixtures'

def _write_config(root: Path) -> Path:
    payload = valid_system_config_payload()
    payload['system']['root_path'] = str(root)
    payload['analysis'] = {**payload['analysis'], 'lookback_bars': 3, 'structure_lookback_bars': 3}
    payload['runtime'] = {**payload['runtime'], 'data_stale_threshold_ms': 15000}
    config_dir = root / 'config'
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / 'system.json'
    config_path.write_text(json.dumps(payload), encoding='utf-8')
    return config_path

def _instance() -> Instance:
    return Instance(account_id='12345', symbol='EURUSD', magic=100001)

def _install_fixtures(paths: SystemPaths, instance: Instance) -> None:
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
    _install_fixtures(SystemPaths(tmp_path), instance)
    runtime = startup(root_path=tmp_path, config_path=config_path)
    return (runtime, instance)

def _read_system_log(paths: SystemPaths) -> str:
    log_files = sorted(paths.logs_dir.glob('system_*.log'))
    assert log_files
    return log_files[-1].read_text(encoding='utf-8')

def test_alerts_affect_trading_returns_false() -> None:
    assert alerts_affect_trading() is False

def test_alert_level_to_log_level_maps_alert_levels() -> None:
    assert alert_level_to_log_level(AlertLevel.WARNING.value) == LogLevel.WARNING.value
    assert alert_level_to_log_level(AlertLevel.ERROR.value) == LogLevel.ERROR.value

def test_build_data_stale_alert_uses_warning_level() -> None:
    alert = build_data_stale_alert(_instance(), freshness_ms=20000, threshold_ms=15000)
    assert alert.level == AlertLevel.WARNING.value
    assert 'freshness_ms=20000' in alert.message

def test_build_ack_timeout_alert_uses_error_level() -> None:
    alert = build_ack_timeout_alert(_instance(), command_id='cmd-1')
    assert alert.level == AlertLevel.ERROR.value
    assert alert.message == REASON_ACK_TIMEOUT

def test_emit_alert_writes_to_logger(tmp_path: Path) -> None:
    paths = SystemPaths(tmp_path)
    paths.ensure_directories()
    logger = setup_system_logger(paths, level=LogLevel.INFO.value, format_name='standard')
    alert = build_data_stale_alert(_instance(), freshness_ms=20000, threshold_ms=15000)
    emit_alert(logger, alert)
    for handler in logger.handlers:
        handler.flush()
    log_text = _read_system_log(paths)
    assert 'DATA_STALE' in log_text
    assert 'WARNING' in log_text

def test_parse_utc_timestamp_and_elapsed_helpers() -> None:
    start = '2026-07-07T06:00:00.000Z'
    end = '2026-07-07T06:00:05.500Z'
    assert parse_utc_timestamp(start).tzinfo is not None
    assert compute_elapsed_ms(start, end) == 5500
    assert compute_data_freshness_ms(start, end) == 5500

def test_is_data_stale_compares_against_threshold() -> None:
    assert is_data_stale(20000, 15000) is True
    assert is_data_stale(10000, 15000) is False

def test_resolve_instance_health_from_cycle_result() -> None:
    instance = _instance()
    assert resolve_instance_health(InstanceCycleResult(instance=instance, timestamp_utc='2026-07-07T06:00:00.000Z', completed=True, error_logged=False)) == INSTANCE_HEALTH_VALID
    assert resolve_instance_health(InstanceCycleResult(instance=instance, timestamp_utc='2026-07-07T06:00:00.000Z', completed=False, error_logged=True)) == INSTANCE_HEALTH_ERROR

def test_resolve_ack_latency_ms_uses_timeout_threshold() -> None:
    instance = _instance()
    order_command = OrderCommand(command_id='cmd-1', action=OrderAction.NONE.value, reason='WAIT', decision_id='decision-1')
    cycle_result = InstanceCycleResult(instance=instance, timestamp_utc='2026-07-07T06:00:00.000Z', completed=True, error_logged=False, execution_result=ExecutionResult(order_command=order_command, control_published=True, trade_intent_logged=False, ack_interpretation=build_ack_timeout_interpretation(command_id='cmd-1'), trade_journal_entry=None, state_updated=True))
    assert resolve_ack_latency_ms(cycle_result, measured_ack_latency_ms=None, ack_timeout_ms=5000) == 5000

def test_record_cycle_error_increments_monitoring_state() -> None:
    state = MonitoringState()
    instance = _instance()
    record_cycle_error(state, instance)
    assert state.error_counts[instance.instance_key] == 1

def test_format_metrics_message_includes_metric_fields() -> None:
    metrics = build_instance_metrics(_instance(), InstanceCycleResult(instance=_instance(), timestamp_utc='2026-07-07T06:00:20.000Z', completed=True, error_logged=False), market_timestamp_utc='2026-07-07T06:00:00.000Z', measured_ack_latency_ms=1200, ack_timeout_ms=5000, current_utc='2026-07-07T06:00:20.000Z', error_count=0, error_rate_per_min=0.0)
    rendered = format_metrics_message(metrics)
    assert 'ack_latency_ms=1200' in rendered
    assert 'data_freshness_ms=20000' in rendered

def test_log_instance_metrics_writes_metrics_to_system_log(tmp_path: Path) -> None:
    runtime, instance = _startup_runtime(tmp_path)
    metrics = build_instance_metrics(instance, InstanceCycleResult(instance=instance, timestamp_utc='2026-07-07T06:00:10.000Z', completed=True, error_logged=False), market_timestamp_utc='2026-07-07T06:00:00.000Z', measured_ack_latency_ms=None, ack_timeout_ms=5000, current_utc='2026-07-07T06:00:10.000Z', error_count=0, error_rate_per_min=0.0)
    log_instance_metrics(runtime, metrics)
    for handler in runtime.system_logger.handlers:
        handler.flush()
    assert 'metrics account=12345' in _read_system_log(runtime.paths)

def test_data_stale_generates_warning_alert(tmp_path: Path) -> None:
    runtime, instance = _startup_runtime(tmp_path)
    current_utc = '2026-07-07T06:02:00.000Z'
    observe_instance_cycle(runtime, instance, InstanceCycleResult(instance=instance, timestamp_utc=current_utc, completed=True, error_logged=False, market_data_utc='2026-07-07T06:00:00.000Z'))
    for handler in runtime.system_logger.handlers:
        handler.flush()
    log_text = _read_system_log(runtime.paths)
    assert 'WARNING' in log_text
    assert 'DATA_STALE' in log_text

def test_ack_timeout_generates_error_alert(tmp_path: Path) -> None:
    runtime, instance = _startup_runtime(tmp_path)
    order_command = OrderCommand(command_id='cmd-timeout-1', action=OrderAction.OPEN.value, reason='BUY: preferred side selected', decision_id='decision-1', side='BUY', volume=0.1)
    observe_instance_cycle(runtime, instance, InstanceCycleResult(instance=instance, timestamp_utc='2026-07-07T06:00:00.000Z', completed=True, error_logged=False, execution_result=ExecutionResult(order_command=order_command, control_published=True, trade_intent_logged=True, ack_interpretation=build_ack_timeout_interpretation(command_id='cmd-timeout-1'), trade_journal_entry=None, state_updated=True), ack_latency_ms=5000), measured_ack_latency_ms=5000)
    for handler in runtime.system_logger.handlers:
        handler.flush()
    log_text = _read_system_log(runtime.paths)
    assert 'ERROR' in log_text
    assert REASON_ACK_TIMEOUT in log_text

def test_alert_does_not_trigger_trade_execution(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    runtime, instance = _startup_runtime(tmp_path)

    def _forbidden_publish(*_args: object, **_kwargs: object) -> None:
        raise AssertionError('alerts must not publish control')
    monkeypatch.setattr('engine.execution.control_writer.publish_control', _forbidden_publish)
    runtime.allow_control_writes = True
    dispatch_cycle_alerts(runtime.system_logger, instance, data_stale=True, freshness_ms=20000, stale_threshold_ms=15000, ack_timed_out=True, command_id='cmd-1', validation_failed=False, validation_message=None, account_not_tradeable=False)
    assert runtime.allow_control_writes is True
    assert alerts_affect_trading() is False

def test_should_emit_account_not_tradeable_alert() -> None:
    assert should_emit_account_not_tradeable_alert(Decision.BLOCK.value, f'BLOCK: {REASON_ACCOUNT_NOT_TRADEABLE}')
    assert not should_emit_account_not_tradeable_alert(Decision.BUY.value, 'BUY')

def test_format_alert_message_includes_instance_details() -> None:
    alert = Alert(level=AlertLevel.WARNING.value, code='DATA_STALE', message='stale', instance=_instance())
    rendered = format_alert_message(alert)
    assert 'account=12345' in rendered
    assert 'symbol=EURUSD' in rendered
