from __future__ import annotations
import json
from pathlib import Path
import pytest
from engine.core.cycle import run_instance_cycle
from engine.core.instance import Instance
from engine.core.lifecycle import startup
from engine.core.monitoring_store import PersistedMonitoringMetrics, build_monitoring_snapshot_path, persist_instance_metrics
from engine.core.orchestrator import run_runtime_cycles
from engine.core.paths import SystemPaths
from engine.journal.error_journal import build_error_journal_path
from engine.protocol.constants import REASON_CYCLE_TIMEOUT, REASON_DATA_INVALID, PROTOCOL_SCHEMA_VERSION
from engine.protocol.parser import parse_error_journal_line
from tests.core.config_payload import FIXTURE_CYCLE_UTC, valid_system_config_payload
from tests.core.test_cycle import _install_valid_fixtures, _startup_runtime
from tests.core.test_orchestrator import _install_valid_fixtures as install_orchestrator_fixtures
from tests.core.test_orchestrator import _startup_runtime as startup_orchestrator_runtime

def _write_config(root: Path, *, runtime_overrides: dict | None=None) -> Path:
    payload = valid_system_config_payload()
    payload['system']['root_path'] = str(root)
    payload['analysis'] = {**payload['analysis'], 'lookback_bars': 3, 'structure_lookback_bars': 3}
    if runtime_overrides:
        payload['runtime'] = {**payload['runtime'], **runtime_overrides}
    config_dir = root / 'config'
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / 'system.json'
    config_path.write_text(json.dumps(payload), encoding='utf-8')
    return config_path

def test_run_instance_cycle_skips_stale_market_data(tmp_path: Path) -> None:
    import os
    import time
    config_path = _write_config(tmp_path, runtime_overrides={'data_stale_threshold_ms': 1000})
    instance = Instance(account_id='12345', symbol='EURUSD', magic=100001)
    paths = SystemPaths(tmp_path)
    _install_valid_fixtures(paths, instance)
    stale_mtime = time.time() - 60
    for filename in (instance.market_filename(), instance.sensor_filename()):
        export_path = paths.account_dir(instance.account_id) / filename
        os.utime(export_path, (stale_mtime, stale_mtime))
    runtime = startup(root_path=tmp_path, config_path=config_path)
    result = run_instance_cycle(runtime, instance, use_global_universe=False)
    assert result.completed is False
    assert result.error_logged is True
    assert result.market_data_utc is not None
    error_text = build_error_journal_path(runtime.paths, instance).read_text(encoding='utf-8')
    entry = parse_error_journal_line(error_text.strip())
    assert 'stale market or sensor data' in entry.message
    assert entry.context['reason'] == REASON_DATA_INVALID

def test_run_instance_cycle_aborts_on_cycle_timeout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = _write_config(tmp_path, runtime_overrides={'cycle_max_duration_ms': 1})
    instance = Instance(account_id='12345', symbol='EURUSD', magic=100001)
    paths = SystemPaths(tmp_path)
    _install_valid_fixtures(paths, instance)
    runtime = startup(root_path=tmp_path, config_path=config_path)
    values = iter([0.0, 0.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0])
    monkeypatch.setattr('engine.core.cycle.time.monotonic', lambda: next(values))
    result = run_instance_cycle(runtime, instance, use_global_universe=False, timestamp_utc=FIXTURE_CYCLE_UTC)
    assert result.completed is False
    assert result.error_logged is True
    error_text = build_error_journal_path(runtime.paths, instance).read_text(encoding='utf-8')
    entry = parse_error_journal_line(error_text.strip())
    assert REASON_CYCLE_TIMEOUT in str(entry.context.get('reason', ''))

def test_run_runtime_cycles_archives_market_snapshot(tmp_path: Path) -> None:
    instance = Instance(account_id='12345', symbol='EURUSD', magic=100001)
    runtime = startup_orchestrator_runtime(tmp_path, install_fixtures=[instance])
    journal_path = runtime.paths.account_journal_dir(instance.account_id) / instance.decision_journal_filename()
    journal_path.parent.mkdir(parents=True, exist_ok=True)
    old_line = json.dumps({'decision_id': 'old-1', 'timestamp_utc': '2020-01-01T00:00:00.000Z', 'account_id': '12345', 'symbol': 'EURUSD', 'magic': 100001, 'decision': 'WAIT', 'reason': 'test', 'risk_result': 'ALLOW'})
    journal_path.write_text(old_line + '\n', encoding='utf-8')
    run_runtime_cycles(runtime, instances=[instance], use_global_universe=False, timestamp_utc=FIXTURE_CYCLE_UTC)
    history_dir = runtime.paths.instance_history_dir(instance.account_id, instance.symbol, instance.magic)
    assert (history_dir / f'market_{FIXTURE_CYCLE_UTC[:10]}.csv').exists()
    archive_files = list(history_dir.glob('decision_*.jsonl'))
    assert archive_files
    assert old_line not in journal_path.read_text(encoding='utf-8')

def test_startup_registers_account_log_file(tmp_path: Path) -> None:
    instance = Instance(account_id='12345', symbol='EURUSD', magic=100001)
    install_orchestrator_fixtures(SystemPaths(tmp_path), instance)
    config_path = _write_config(tmp_path)
    runtime = startup(root_path=tmp_path, config_path=config_path)
    assert '12345' in runtime.account_loggers
    run_runtime_cycles(runtime, instances=[instance], use_global_universe=False, timestamp_utc=FIXTURE_CYCLE_UTC)
    for handler in runtime.account_loggers['12345'].handlers:
        handler.flush()
    account_logs = list(runtime.paths.logs_dir.glob('account_12345_*.log'))
    assert account_logs
    assert 'metrics account=12345' in account_logs[0].read_text(encoding='utf-8')

def test_dashboard_reads_monitoring_snapshot_from_state_dir(tmp_path: Path) -> None:
    from engine.dashboard.reader import read_instance_dashboard_view
    from tests.dashboard.test_console import _dashboard_paths, _install_dashboard_fixtures
    paths, _ = _dashboard_paths(tmp_path)
    instance = Instance(account_id='12345', symbol='EURUSD', magic=100001)
    _install_dashboard_fixtures(paths, instance)
    persist_instance_metrics(paths, instance, PersistedMonitoringMetrics(schema_version=PROTOCOL_SCHEMA_VERSION, account_id=instance.account_id, symbol=instance.symbol, magic=instance.magic, timestamp_utc=FIXTURE_CYCLE_UTC, cycle_latency_ms=900, ack_latency_ms=400, data_freshness_ms=5000, error_count=1, error_rate_per_min=0.5, instance_health='VALID'))
    assert build_monitoring_snapshot_path(paths, instance).parent.name == 'state'
    view = read_instance_dashboard_view(paths, instance)
    assert view.cycle_latency_ms == 900
    assert view.error_rate_per_min == 0.5
