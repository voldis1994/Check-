from __future__ import annotations
import json
import shutil
from pathlib import Path
import pytest
from engine.core.cycle import InstanceCycleResult
from engine.core.instance import Instance
from engine.core.lifecycle import startup
from engine.core.orchestrator import OrchestratorCycleResult, group_instances_by_account, list_registered_instances, refresh_discovered_instances, register_runtime_instances, reload_instance_state, resolve_runtime_instances, run_instance_cycle_isolated, run_runtime_cycles
from engine.core.paths import SystemPaths
from engine.execution.engine import ExecutionResult
from engine.journal.decision_journal import build_decision_journal_path
from engine.journal.error_journal import build_error_journal_path
from engine.normalizer.spread_model import update_spread_model
from engine.protocol.constants import ErrorType, PROTOCOL_SCHEMA_VERSION
from engine.protocol.parser import parse_decision_journal_line, parse_error_journal_line
from engine.state.instance_state import InstanceState
from engine.state.spread_state import SpreadState
from tests.core.config_payload import FIXTURE_CYCLE_UTC, valid_system_config_payload
FIXTURES_DIR = Path(__file__).parent.parent / 'loader' / 'fixtures'

def _write_config(root: Path, *, instances: list[dict] | None=None) -> Path:
    payload = valid_system_config_payload()
    payload['system']['root_path'] = str(root)
    payload['analysis'] = {**payload['analysis'], 'lookback_bars': 3}
    if instances is not None:
        payload['instances'] = instances
    config_dir = root / 'config'
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / 'system.json'
    config_path.write_text(json.dumps(payload), encoding='utf-8')
    return config_path

def _market_csv(symbol: str) -> str:
    return f'time_utc,open,high,low,close,volume,symbol,timeframe,digits,point\n2026-07-07T06:00:00.000Z,1.10000,1.10200,1.09900,1.10150,120,{symbol},M1,5,0.00001\n2026-07-07T06:01:00.000Z,1.10150,1.10300,1.10050,1.10220,110,{symbol},M1,5,0.00001\n2026-07-07T06:02:00.000Z,1.10220,1.10400,1.10100,1.10310,105,{symbol},M1,5,0.00001\n'

def _install_valid_fixtures(paths: SystemPaths, instance: Instance) -> None:
    paths.ensure_account_directories(instance.account_id)
    account_dir = paths.account_dir(instance.account_id)
    (account_dir / instance.market_filename()).write_text(_market_csv(instance.symbol), encoding='utf-8')
    shutil.copyfile(FIXTURES_DIR / 'sensor_valid.csv', account_dir / instance.sensor_filename())
    shutil.copyfile(FIXTURES_DIR / 'status_valid.json', account_dir / instance.status_filename())
    shutil.copyfile(FIXTURES_DIR / 'universe_valid.json', account_dir / 'universe.json')

def _startup_runtime(tmp_path: Path, *, instances: list[dict] | None=None, install_fixtures: list[Instance] | None=None):
    config_path = _write_config(tmp_path, instances=instances)
    paths = SystemPaths(tmp_path)
    for instance in install_fixtures or ():
        _install_valid_fixtures(paths, instance)
    runtime = startup(root_path=tmp_path, config_path=config_path)
    return runtime

@pytest.fixture(autouse=True)
def _fast_execution(monkeypatch: pytest.MonkeyPatch) -> None:

    def _mock_run_execution_engine(**kwargs: object) -> ExecutionResult:
        from engine.execution.command import build_order_command
        decision_result = kwargs['decision_result']
        risk_engine_result = kwargs['risk_engine_result']
        order_command = build_order_command(decision_result, risk_engine_result)
        return ExecutionResult(order_command=order_command, control_published=False, trade_intent_logged=False, ack_interpretation=None, trade_journal_entry=None, state_updated=False)
    monkeypatch.setattr('engine.core.cycle.run_execution_engine', _mock_run_execution_engine)

def test_orchestrator_cycle_result_counts_instances() -> None:
    instance = Instance(account_id='12345', symbol='EURUSD', magic=100001)
    result = OrchestratorCycleResult(instance_results=(InstanceCycleResult(instance=instance, timestamp_utc='2026-07-07T06:00:00.000Z', completed=True, error_logged=False),), completed_count=1, failed_count=0)
    assert result.instance_count == 1
    assert result.completed_count == 1
    assert result.failed_count == 0

def test_resolve_runtime_instances_returns_discovered_instances(tmp_path: Path) -> None:
    instance_a = Instance(account_id='12345', symbol='EURUSD', magic=100001)
    instance_b = Instance(account_id='12345', symbol='GBPUSD', magic=100002)
    runtime = _startup_runtime(tmp_path, instances=[{'account_id': '12345', 'symbol': 'EURUSD', 'magic': 100001, 'enabled': True}], install_fixtures=[instance_a])
    paths = runtime.paths
    paths.ensure_account_directories('12345')
    (paths.account_dir('12345') / instance_b.market_filename()).write_text('x', encoding='utf-8')
    instances = resolve_runtime_instances(runtime)
    keys = {item.instance_key for item in instances}
    assert instance_a.instance_key in keys
    assert instance_b.instance_key in keys

def test_group_instances_by_account_groups_and_sorts() -> None:
    first = Instance(account_id='12345', symbol='GBPUSD', magic=100002)
    second = Instance(account_id='12345', symbol='EURUSD', magic=100001)
    third = Instance(account_id='67890', symbol='EURUSD', magic=200001)
    grouped = group_instances_by_account((third, second, first))
    assert tuple(grouped.keys()) == ('12345', '67890')
    assert grouped['12345'] == (second, first)
    assert grouped['67890'] == (third,)

def test_register_runtime_instances_loads_memory_for_new_instances(tmp_path: Path) -> None:
    instance = Instance(account_id='12345', symbol='EURUSD', magic=100001)
    runtime = _startup_runtime(tmp_path, install_fixtures=[instance])
    runtime.memory.release(instance)
    registered = register_runtime_instances(runtime, [instance])
    assert registered == (instance,)
    assert runtime.memory.get(instance) is not None

def test_list_registered_instances_returns_runtime_memory_instances(tmp_path: Path) -> None:
    instance = Instance(account_id='12345', symbol='EURUSD', magic=100001)
    runtime = _startup_runtime(tmp_path, install_fixtures=[instance])
    registered = list_registered_instances(runtime)
    assert registered == (instance,)

def test_reload_instance_state_reloads_persisted_state(tmp_path: Path) -> None:
    instance = Instance(account_id='12345', symbol='EURUSD', magic=100001)
    runtime = _startup_runtime(tmp_path, install_fixtures=[instance])
    item = runtime.memory.get_or_create(instance)
    item.instance_state.update_cycle(decision='BUY', reason='TREND', cycle_utc='2026-07-07T06:00:00.000Z')
    snapshot = update_spread_model((0.0001,), current_spread=0.0002, lookback_bars=10)
    item.spread_state.update_from_snapshot(snapshot, '2026-07-07T06:00:00.000Z')
    item.instance_state.save(runtime.paths)
    item.spread_state.save(runtime.paths)
    item.instance_state.update_cycle(decision='WAIT', reason='RESET', cycle_utc='2026-07-07T06:01:00.000Z')
    reload_instance_state(runtime, instance)
    reloaded = runtime.memory.get(instance)
    assert reloaded is not None
    assert reloaded.instance_state.last_decision == 'BUY'
    assert reloaded.spread_state.record is not None
    assert reloaded.spread_state.record.current_spread == 0.0002
    assert instance.instance_key in runtime.spread_models

def test_run_instance_cycle_isolated_returns_error_result_on_unexpected_exception(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    instance = Instance(account_id='12345', symbol='EURUSD', magic=100001)
    runtime = _startup_runtime(tmp_path, install_fixtures=[instance])

    def _raise_error(*_args: object, **_kwargs: object) -> InstanceCycleResult:
        raise RuntimeError('cycle exploded')
    monkeypatch.setattr('engine.core.orchestrator.run_instance_cycle', _raise_error)
    result = run_instance_cycle_isolated(runtime, instance, use_global_universe=False, timestamp_utc='2026-07-07T06:00:00.000Z')
    assert not result.completed
    assert result.error_logged
    error_path = build_error_journal_path(runtime.paths, instance)
    assert error_path.exists()
    error_entry = parse_error_journal_line(error_path.read_text(encoding='utf-8').strip())
    assert error_entry.error_type == ErrorType.PROTOCOL.value
    assert 'cycle exploded' in error_entry.context['error']

def test_run_runtime_cycles_returns_empty_result_when_shutdown_requested(tmp_path: Path) -> None:
    instance = Instance(account_id='12345', symbol='EURUSD', magic=100001)
    runtime = _startup_runtime(tmp_path, install_fixtures=[instance])
    runtime.shutdown_requested = True
    result = run_runtime_cycles(runtime, use_global_universe=False, timestamp_utc=FIXTURE_CYCLE_UTC)
    assert result.instance_results == ()
    assert result.completed_count == 0
    assert result.failed_count == 0

def test_two_instances_one_account_have_isolated_state_and_journal(tmp_path: Path) -> None:
    instance_a = Instance(account_id='12345', symbol='EURUSD', magic=100001)
    instance_b = Instance(account_id='12345', symbol='GBPUSD', magic=100002)
    runtime = _startup_runtime(tmp_path, instances=[{'account_id': '12345', 'symbol': 'EURUSD', 'magic': 100001, 'enabled': True}, {'account_id': '12345', 'symbol': 'GBPUSD', 'magic': 100002, 'enabled': True}], install_fixtures=[instance_a, instance_b])
    result = run_runtime_cycles(runtime, use_global_universe=False, timestamp_utc=FIXTURE_CYCLE_UTC)
    assert result.instance_count == 2
    assert result.completed_count == 2
    journal_a = build_decision_journal_path(runtime.paths, instance_a)
    journal_b = build_decision_journal_path(runtime.paths, instance_b)
    assert journal_a != journal_b
    assert journal_a.exists()
    assert journal_b.exists()
    entry_a = parse_decision_journal_line(journal_a.read_text(encoding='utf-8').strip())
    entry_b = parse_decision_journal_line(journal_b.read_text(encoding='utf-8').strip())
    assert entry_a.decision_id != entry_b.decision_id
    state_a = InstanceState.load(runtime.paths, instance_a)
    state_b = InstanceState.load(runtime.paths, instance_b)
    assert state_a.last_decision is not None
    assert state_b.last_decision is not None
    assert runtime.memory.get(instance_a) is not runtime.memory.get(instance_b)

def test_two_accounts_use_isolated_paths(tmp_path: Path) -> None:
    instance_a = Instance(account_id='12345', symbol='EURUSD', magic=100001)
    instance_b = Instance(account_id='67890', symbol='EURUSD', magic=200001)
    runtime = _startup_runtime(tmp_path, instances=[{'account_id': '12345', 'symbol': 'EURUSD', 'magic': 100001, 'enabled': True}, {'account_id': '67890', 'symbol': 'EURUSD', 'magic': 200001, 'enabled': True}], install_fixtures=[instance_a, instance_b])
    result = run_runtime_cycles(runtime, use_global_universe=False, timestamp_utc=FIXTURE_CYCLE_UTC)
    assert result.completed_count == 2
    journal_dir_a = runtime.paths.account_journal_dir('12345')
    journal_dir_b = runtime.paths.account_journal_dir('67890')
    assert journal_dir_a != journal_dir_b
    assert (journal_dir_a / instance_a.decision_journal_filename()).exists()
    assert (journal_dir_b / instance_b.decision_journal_filename()).exists()
    assert not (journal_dir_a / instance_b.decision_journal_filename()).exists()
    assert not (journal_dir_b / instance_a.decision_journal_filename()).exists()

def test_one_instance_failure_does_not_stop_other_instance(tmp_path: Path) -> None:
    good_instance = Instance(account_id='12345', symbol='EURUSD', magic=100001)
    bad_instance = Instance(account_id='12345', symbol='GBPUSD', magic=100002)
    runtime = _startup_runtime(tmp_path, instances=[{'account_id': '12345', 'symbol': 'EURUSD', 'magic': 100001, 'enabled': True}, {'account_id': '12345', 'symbol': 'GBPUSD', 'magic': 100002, 'enabled': True}], install_fixtures=[good_instance, bad_instance])
    invalid_path = runtime.paths.account_dir('12345') / bad_instance.market_filename()
    invalid_path.write_text((FIXTURES_DIR / 'market_missing.csv').read_text(encoding='utf-8'), encoding='utf-8')
    result = run_runtime_cycles(runtime, instances=(bad_instance, good_instance), use_global_universe=False, timestamp_utc=FIXTURE_CYCLE_UTC)
    assert result.instance_count == 2
    assert result.completed_count == 1
    assert result.failed_count == 1
    assert not result.instance_results[0].completed
    assert result.instance_results[1].completed
    good_journal = build_decision_journal_path(runtime.paths, good_instance)
    assert good_journal.exists()
    bad_error = build_error_journal_path(runtime.paths, bad_instance)
    assert bad_error.exists()

def test_refresh_discovered_instances_discovers_new_instance_from_filesystem(tmp_path: Path) -> None:
    configured = Instance(account_id='12345', symbol='EURUSD', magic=100001)
    discovered = Instance(account_id='12345', symbol='GBPUSD', magic=100002)
    runtime = _startup_runtime(tmp_path, instances=[{'account_id': '12345', 'symbol': 'EURUSD', 'magic': 100001, 'enabled': True}], install_fixtures=[configured])
    assert list_registered_instances(runtime) == (configured,)
    paths = runtime.paths
    paths.ensure_account_directories('12345')
    (paths.account_dir('12345') / discovered.market_filename()).write_text('x', encoding='utf-8')
    refreshed = refresh_discovered_instances(runtime)
    keys = {instance.instance_key for instance in refreshed}
    assert configured.instance_key in keys
    assert discovered.instance_key in keys
    assert runtime.memory.get(discovered) is not None

def test_auto_discover_instances_registers_new_instance_for_runtime_cycles(tmp_path: Path) -> None:
    configured = Instance(account_id='12345', symbol='EURUSD', magic=100001)
    discovered = Instance(account_id='12345', symbol='GBPUSD', magic=100002)
    runtime = _startup_runtime(tmp_path, instances=[{'account_id': '12345', 'symbol': 'EURUSD', 'magic': 100001, 'enabled': True}], install_fixtures=[configured])
    paths = runtime.paths
    paths.ensure_account_directories('12345')
    _install_valid_fixtures(paths, discovered)
    result = run_runtime_cycles(runtime, use_global_universe=False, timestamp_utc=FIXTURE_CYCLE_UTC)
    assert result.instance_count == 2
    assert result.completed_count == 2
    assert runtime.memory.get(discovered) is not None
