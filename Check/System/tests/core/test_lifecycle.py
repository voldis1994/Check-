from __future__ import annotations
import json
from pathlib import Path
import pytest
from engine.core.config import load_system_config, parse_config_payload
from engine.core.instance import Instance
from engine.core.lifecycle import STARTUP_ERROR_EXIT_CODE, STARTUP_EXIT_CODE, LiveRuntime, build_spread_models, build_system_paths, close_runtime_logging, discover_instances, discover_instances_from_account, ensure_runtime_paths_aligned, format_mt4_missing_exports_message, instances_from_config, invalidate_runtime_cache, load_runtime_memory, parse_market_filename, persist_runtime_state, read_status_connected, request_shutdown, run_live_main, shutdown, spread_snapshot_from_record, startup, validate_config_root_path, validate_mt4_runtime_ready, validate_root_path
from engine.core.paths import SystemPaths
from engine.normalizer.spread_model import update_spread_model
from engine.protocol.constants import PROTOCOL_SCHEMA_VERSION
from engine.protocol.errors import ConfigurationError
from engine.state.instance_state import InstanceState
from engine.state.spread_state import SpreadState
from tests.core.config_payload import valid_system_config_payload

def _write_config(root: Path, payload: dict | None=None) -> Path:
    config_dir = root / 'config'
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / 'system.json'
    config_path.write_text(json.dumps(payload or valid_system_config_payload()), encoding='utf-8')
    return config_path

def _prepare_runtime_root(tmp_path: Path) -> tuple[Path, Path]:
    payload = valid_system_config_payload()
    payload['system']['root_path'] = str(tmp_path)
    config_path = _write_config(tmp_path, payload)
    return (tmp_path, config_path)

def test_build_system_paths_uses_config_paths() -> None:
    config = parse_config_payload(valid_system_config_payload())
    paths = build_system_paths(config)
    assert paths.clients_dir == paths.root / 'data/clients'
    assert paths.logs_dir == paths.root / 'data/logs'
    assert paths.config_path == paths.root / 'config/system.json'

def test_build_system_paths_runtime_root_overrides_config_root(tmp_path: Path) -> None:
    payload = valid_system_config_payload()
    payload['system']['root_path'] = str(tmp_path / 'stale')
    config = parse_config_payload(payload)
    runtime_root = tmp_path / 'actual'
    runtime_root.mkdir()
    paths = build_system_paths(config, runtime_root=runtime_root)
    assert paths.root == runtime_root.resolve()
    assert paths.clients_dir == runtime_root.resolve() / 'data/clients'

def test_ensure_runtime_paths_aligned_syncs_stale_config_root(tmp_path: Path) -> None:
    root, config_path = _prepare_runtime_root(tmp_path)
    payload = valid_system_config_payload()
    payload['system']['root_path'] = str(tmp_path / 'wrong')
    config_path.write_text(json.dumps(payload), encoding='utf-8')
    bootstrap_paths = SystemPaths(root)
    config = load_system_config(config_path, system_paths=bootstrap_paths)
    aligned = ensure_runtime_paths_aligned(bootstrap_paths, config, config_path=config_path)
    assert Path(aligned.system.root_path).resolve() == root.resolve()

def test_validate_mt4_runtime_ready_reports_missing_market_file(tmp_path: Path) -> None:
    root, config_path = _prepare_runtime_root(tmp_path)
    paths = SystemPaths(root)
    config = load_system_config(config_path, system_paths=paths)
    instances = discover_instances(config, paths)
    with pytest.raises(ConfigurationError, match='MT4 export files not found'):
        validate_mt4_runtime_ready(paths, instances)

def test_format_mt4_missing_exports_message_lists_expected_paths(tmp_path: Path) -> None:
    root, config_path = _prepare_runtime_root(tmp_path)
    paths = SystemPaths(root)
    config = load_system_config(config_path, system_paths=paths)
    instances = discover_instances(config, paths)
    message = format_mt4_missing_exports_message(paths, instances)
    assert 'market_EURUSD_100001.csv' in message
    assert str(paths.clients_dir) in message

def test_startup_with_require_mt4_exports_fails_when_exports_missing(tmp_path: Path) -> None:
    root, config_path = _prepare_runtime_root(tmp_path)
    with pytest.raises(ConfigurationError, match='MT4 export files not found'):
        startup(root_path=root, config_path=config_path, require_mt4_exports=True)

def test_startup_with_require_mt4_exports_succeeds_when_exports_present(tmp_path: Path) -> None:
    root, config_path = _prepare_runtime_root(tmp_path)
    paths = SystemPaths(root)
    paths.ensure_account_directories('12345')
    (paths.account_dir('12345') / 'market_EURUSD_100001.csv').write_text('time_utc,open,high,low,close,volume\n', encoding='utf-8')
    runtime = startup(root_path=root, config_path=config_path, require_mt4_exports=True)
    assert isinstance(runtime, LiveRuntime)

def test_startup_soft_continues_without_mt4_after_wait(tmp_path: Path) -> None:
    root, config_path = _prepare_runtime_root(tmp_path)
    runtime = startup(root_path=root, config_path=config_path, require_mt4_exports=False, wait_for_mt4_seconds=0.1)
    assert isinstance(runtime, LiveRuntime)
    shutdown(runtime)

def test_validate_root_path_requires_existing_directory(tmp_path: Path) -> None:
    paths = SystemPaths(tmp_path)
    validate_root_path(paths)

def test_validate_root_path_missing_root_raises(tmp_path: Path) -> None:
    missing = tmp_path / 'missing'
    with pytest.raises(ConfigurationError, match='does not exist'):
        validate_root_path(SystemPaths(missing))

def test_validate_root_path_file_root_raises(tmp_path: Path) -> None:
    file_path = tmp_path / 'not-a-dir'
    file_path.write_text('x', encoding='utf-8')
    with pytest.raises(ConfigurationError, match='not a directory'):
        validate_root_path(SystemPaths(file_path))

def test_parse_market_filename_extracts_symbol_and_magic() -> None:
    assert parse_market_filename('market_EURUSD_100001.csv') == ('EURUSD', 100001)
    assert parse_market_filename('market_US30_200002.csv') == ('US30', 200002)
    assert parse_market_filename('sensor_EURUSD_100001.csv') is None

def test_instances_from_config_returns_enabled_instances_only() -> None:
    payload = valid_system_config_payload()
    payload['instances'].append({'account_id': '12345', 'symbol': 'GBPUSD', 'magic': 100002, 'enabled': False})
    config = parse_config_payload(payload)
    instances = instances_from_config(config)
    assert len(instances) == 1
    assert instances[0].symbol == 'EURUSD'

def test_discover_instances_from_account_reads_market_files(tmp_path: Path) -> None:
    paths = SystemPaths(tmp_path)
    paths.ensure_account_directories('12345')
    (paths.account_dir('12345') / 'market_EURUSD_100001.csv').write_text('x', encoding='utf-8')
    (paths.account_dir('12345') / 'market_GBPUSD_100002.csv').write_text('x', encoding='utf-8')
    discovered = discover_instances_from_account(paths, '12345')
    keys = {instance.instance_key for instance in discovered}
    assert ('12345', 'EURUSD', 100001) in keys
    assert ('12345', 'GBPUSD', 100002) in keys

def test_discover_instances_merges_config_and_filesystem(tmp_path: Path) -> None:
    root, config_path = _prepare_runtime_root(tmp_path)
    paths = SystemPaths(root)
    paths.ensure_account_directories('12345')
    (paths.account_dir('12345') / 'market_GBPUSD_100002.csv').write_text('x', encoding='utf-8')
    config = load_system_config(config_path, system_paths=paths)
    instances = discover_instances(config, paths)
    keys = {instance.instance_key for instance in instances}
    assert ('12345', 'EURUSD', 100001) in keys
    assert ('12345', 'GBPUSD', 100002) in keys

def test_load_runtime_memory_loads_persisted_state(tmp_path: Path) -> None:
    root, _ = _prepare_runtime_root(tmp_path)
    paths = SystemPaths(root)
    instance = Instance(account_id='12345', symbol='EURUSD', magic=100001)
    state = InstanceState(instance=instance)
    state.update_cycle(decision='BUY', reason='TREND', cycle_utc='2026-07-07T06:00:00.000Z')
    state.save(paths)
    memory = load_runtime_memory(paths, [instance], lookback_bars=120)
    item = memory.get(instance)
    assert item is not None
    assert item.instance_state.last_decision == 'BUY'

def test_spread_snapshot_from_record_rebuilds_model_snapshot(tmp_path: Path) -> None:
    instance = Instance(account_id='12345', symbol='EURUSD', magic=100001)
    spread_state = SpreadState(instance=instance)
    snapshot = update_spread_model((0.0001, 0.0002), current_spread=0.0003, lookback_bars=10)
    record = spread_state.update_from_snapshot(snapshot, '2026-07-07T06:00:00.000Z')
    rebuilt = spread_snapshot_from_record(record)
    assert rebuilt.sample_count == record.sample_count
    assert rebuilt.mean_spread == record.mean_spread
    assert rebuilt.current_spread == record.current_spread

def test_build_spread_models_initializes_from_loaded_spread_state(tmp_path: Path) -> None:
    root, _ = _prepare_runtime_root(tmp_path)
    paths = SystemPaths(root)
    instance = Instance(account_id='12345', symbol='EURUSD', magic=100001)
    spread_state = SpreadState(instance=instance)
    snapshot = update_spread_model((0.0001,), current_spread=0.0002, lookback_bars=10)
    spread_state.update_from_snapshot(snapshot, '2026-07-07T06:00:00.000Z')
    spread_state.save(paths)
    memory = load_runtime_memory(paths, [instance], lookback_bars=120)
    models = build_spread_models(memory)
    assert instance.instance_key in models
    assert models[instance.instance_key].current_spread == 0.0002

def test_invalidate_runtime_cache_removes_instance_hash_files(tmp_path: Path) -> None:
    root, _ = _prepare_runtime_root(tmp_path)
    paths = SystemPaths(root)
    instance = Instance(account_id='12345', symbol='EURUSD', magic=100001)
    paths.ensure_instance_directories(instance.account_id, instance.symbol, instance.magic)
    cache_dir = paths.instance_cache_dir(instance.account_id, instance.symbol, instance.magic)
    (cache_dir / 'last_market.hash').write_text('{}', encoding='utf-8')
    removed = invalidate_runtime_cache(paths, [instance])
    assert removed == 1
    assert not (cache_dir / 'last_market.hash').exists()

def test_read_status_connected_returns_none_when_status_missing(tmp_path: Path) -> None:
    paths = SystemPaths(tmp_path)
    assert read_status_connected(paths, '12345') is None

def test_read_status_connected_reads_connected_flag(tmp_path: Path) -> None:
    paths = SystemPaths(tmp_path)
    paths.ensure_account_directories('12345')
    status_path = paths.account_dir('12345') / 'status_12345.json'
    status_path.write_text(json.dumps({'schema_version': PROTOCOL_SCHEMA_VERSION, 'timestamp_utc': '2026-07-07T06:00:00.000Z', 'account_id': '12345', 'connected': False, 'trade_allowed': True, 'balance': 10000.0, 'equity': 10020.5, 'margin_free': 9800.0, 'ea_version': '1.0.0'}), encoding='utf-8')
    assert read_status_connected(paths, '12345') is False

def test_validate_config_root_path_rejects_mismatched_root(tmp_path: Path) -> None:
    root, config_path = _prepare_runtime_root(tmp_path)
    config = load_system_config(config_path, system_paths=SystemPaths(root))
    other_root = tmp_path / 'other'
    other_root.mkdir()
    from dataclasses import replace
    from engine.protocol.models import SystemSection
    mismatched = replace(config, system=SystemSection(name=config.system.name, root_path=str(other_root), timeframe=config.system.timeframe))
    with pytest.raises(ConfigurationError, match='system.root_path does not match'):
        validate_config_root_path(mismatched, SystemPaths(root))

def test_startup_with_valid_configuration(tmp_path: Path) -> None:
    root, config_path = _prepare_runtime_root(tmp_path)
    runtime = startup(root_path=root, config_path=config_path)
    assert isinstance(runtime, LiveRuntime)
    assert runtime.config.system.timeframe == 'M1'
    assert len(runtime.memory.items()) == 1
    assert runtime.paths.logs_dir.exists()

def test_startup_with_invalid_configuration_exits_with_error(tmp_path: Path) -> None:
    root, config_path = _prepare_runtime_root(tmp_path)
    payload = valid_system_config_payload()
    payload['system']['timeframe'] = 'H1'
    config_path.write_text(json.dumps(payload), encoding='utf-8')
    with pytest.raises(ConfigurationError, match='invalid config payload'):
        startup(root_path=root, config_path=config_path)

def test_run_live_main_invalid_configuration_returns_error_exit_code(tmp_path: Path) -> None:
    root, config_path = _prepare_runtime_root(tmp_path)
    payload = valid_system_config_payload()
    payload['system']['timeframe'] = 'H1'
    config_path.write_text(json.dumps(payload), encoding='utf-8')
    exit_code = run_live_main(root_path=root, config_path=config_path, wait_for_shutdown=lambda runtime: request_shutdown(runtime))
    assert exit_code == STARTUP_ERROR_EXIT_CODE

def test_request_shutdown_disables_control_writes(tmp_path: Path) -> None:
    root, config_path = _prepare_runtime_root(tmp_path)
    runtime = startup(root_path=root, config_path=config_path)
    request_shutdown(runtime)
    assert runtime.shutdown_requested is True
    assert runtime.allow_control_writes is False

def test_persist_runtime_state_writes_instance_and_spread_state(tmp_path: Path) -> None:
    root, config_path = _prepare_runtime_root(tmp_path)
    runtime = startup(root_path=root, config_path=config_path)
    instance = Instance(account_id='12345', symbol='EURUSD', magic=100001)
    item = runtime.memory.get(instance)
    assert item is not None
    item.instance_state.update_cycle(decision='SELL', reason='PRESSURE', cycle_utc='2026-07-07T06:05:00.000Z')
    snapshot = update_spread_model((0.0001,), current_spread=0.0002, lookback_bars=10)
    item.spread_state.update_from_snapshot(snapshot, '2026-07-07T06:05:00.000Z')
    persist_runtime_state(runtime)
    loaded_state = InstanceState.load(runtime.paths, instance)
    loaded_spread = SpreadState.load(runtime.paths, instance)
    assert loaded_state.last_decision == 'SELL'
    assert loaded_spread.record is not None
    assert loaded_spread.record.current_spread == 0.0002

def test_shutdown_persists_state(tmp_path: Path) -> None:
    root, config_path = _prepare_runtime_root(tmp_path)
    runtime = startup(root_path=root, config_path=config_path)
    instance = Instance(account_id='12345', symbol='EURUSD', magic=100001)
    item = runtime.memory.get(instance)
    assert item is not None
    item.instance_state.update_cycle(decision='WAIT', reason='NO_EDGE', cycle_utc='2026-07-07T06:10:00.000Z')
    exit_code = shutdown(runtime)
    assert exit_code == STARTUP_EXIT_CODE
    loaded_state = InstanceState.load(runtime.paths, instance)
    assert loaded_state.last_decision == 'WAIT'
    assert loaded_state.last_reason == 'NO_EDGE'

def test_shutdown_with_connected_false_status_does_not_block_shutdown(tmp_path: Path) -> None:
    root, config_path = _prepare_runtime_root(tmp_path)
    paths = SystemPaths(root)
    paths.ensure_account_directories('12345')
    status_path = paths.account_dir('12345') / 'status_12345.json'
    status_path.write_text(json.dumps({'schema_version': PROTOCOL_SCHEMA_VERSION, 'timestamp_utc': '2026-07-07T06:00:00.000Z', 'account_id': '12345', 'connected': False, 'trade_allowed': False, 'balance': 10000.0, 'equity': 10020.5, 'margin_free': 9800.0, 'ea_version': '1.0.0'}), encoding='utf-8')
    runtime = startup(root_path=root, config_path=config_path)
    assert read_status_connected(runtime.paths, '12345') is False
    exit_code = shutdown(runtime)
    assert exit_code == STARTUP_EXIT_CODE

def test_close_runtime_logging_closes_handlers(tmp_path: Path) -> None:
    root, config_path = _prepare_runtime_root(tmp_path)
    runtime = startup(root_path=root, config_path=config_path)
    assert runtime.system_logger.handlers
    close_runtime_logging(runtime)
    assert not runtime.system_logger.handlers

def test_run_live_main_completes_startup_and_shutdown(tmp_path: Path) -> None:
    root, config_path = _prepare_runtime_root(tmp_path)
    exit_code = run_live_main(root_path=root, config_path=config_path, wait_for_shutdown=lambda runtime: request_shutdown(runtime))
    assert exit_code == STARTUP_EXIT_CODE

def test_run_live_main_prints_startup_banner(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root, config_path = _prepare_runtime_root(tmp_path)
    paths = SystemPaths(root)
    paths.ensure_account_directories('12345')
    (paths.account_dir('12345') / 'market_EURUSD_100001.csv').write_text('time_utc,open,high,low,close,volume,symbol,timeframe,digits,point\n2026-07-07T06:02:00.000Z,1.1,1.2,1.0,1.15,1,EURUSD,M1,5,0.00001\n', encoding='utf-8')
    exit_code = run_live_main(root_path=root, config_path=config_path, require_mt4_exports=True, wait_for_shutdown=lambda runtime: request_shutdown(runtime))
    captured = capsys.readouterr()
    assert exit_code == STARTUP_EXIT_CODE
    assert 'live started' in captured.out
    assert 'SYSTEM v' in captured.out

def test_print_live_cycle_summary_shows_skip_reason(capsys: pytest.CaptureFixture[str]) -> None:
    from engine.core.cycle import InstanceCycleResult
    from engine.core.lifecycle import print_live_cycle_summary
    from engine.core.orchestrator import OrchestratorCycleResult
    instance = Instance(account_id='231054', symbol='EURUSD', magic=100001)
    result = OrchestratorCycleResult(instance_results=(InstanceCycleResult(instance=instance, timestamp_utc='2026-07-15T19:00:00.000Z', completed=False, error_logged=True, skip_reason='stale_data:market_file=120000ms threshold=90000ms'),), completed_count=0, failed_count=1)
    print_live_cycle_summary(result)
    captured = capsys.readouterr()
    assert 'SKIP' in captured.out
    assert 'stale_data' in captured.out
