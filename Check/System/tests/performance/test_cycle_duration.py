from __future__ import annotations
import json
from pathlib import Path
from typing import Any
import pytest
from engine.core.cycle import run_instance_cycle
from engine.core.instance import Instance
from engine.core.lifecycle import startup
from engine.core.orchestrator import run_runtime_cycles
from engine.core.paths import SystemPaths
from engine.execution.engine import ExecutionResult
from tests.core.config_payload import FIXTURE_CYCLE_UTC, valid_system_config_payload
from tests.e2e.simulator.mt4_simulator import MT4Simulator
CYCLE_MAX_DURATION_MS = 30000

def _write_config(root: Path, *, instances: list[dict[str, Any]] | None=None, cycle_max_duration_ms: int=CYCLE_MAX_DURATION_MS) -> Path:
    payload = valid_system_config_payload()
    payload['system']['root_path'] = str(root)
    payload['analysis'] = {**payload['analysis'], 'lookback_bars': 3}
    payload['runtime'] = {**payload['runtime'], 'cycle_max_duration_ms': cycle_max_duration_ms, 'metrics_interval_ms': 1, 'ack_timeout_ms': 100}
    if instances is not None:
        payload['instances'] = instances
    config_dir = root / 'config'
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / 'system.json'
    config_path.write_text(json.dumps(payload), encoding='utf-8')
    return config_path

def _instance(*, magic: int=100001, symbol: str='EURUSD') -> Instance:
    return Instance(account_id='12345', symbol=symbol, magic=magic)

def _build_ten_instances() -> tuple[Instance, ...]:
    return tuple((_instance(magic=100001 + offset) for offset in range(10)))

def _build_instance_config_entries(instances: tuple[Instance, ...]) -> list[dict[str, Any]]:
    return [{'account_id': instance.account_id, 'symbol': instance.symbol, 'magic': instance.magic, 'enabled': True} for instance in instances]

def _startup_runtime(tmp_path: Path, *, instances: tuple[Instance, ...] | None=None, cycle_max_duration_ms: int=CYCLE_MAX_DURATION_MS):
    instance_list = instances or (_instance(),)
    config_path = _write_config(tmp_path, instances=_build_instance_config_entries(instance_list), cycle_max_duration_ms=cycle_max_duration_ms)
    runtime = startup(root_path=tmp_path, config_path=config_path)
    simulator = MT4Simulator(runtime.paths)
    for instance in instance_list:
        simulator.export_tick(instance)
    return (runtime, simulator, instance_list)

@pytest.fixture(autouse=True)
def _fast_execution(monkeypatch: pytest.MonkeyPatch) -> None:

    def _mock_run_execution_engine(**kwargs: object) -> ExecutionResult:
        from engine.execution.command import build_order_command
        order_command = build_order_command(kwargs['decision_result'], kwargs['risk_engine_result'])
        return ExecutionResult(order_command=order_command, control_published=False, trade_intent_logged=False, ack_interpretation=None, trade_journal_entry=None, state_updated=False)
    monkeypatch.setattr('engine.core.cycle.run_execution_engine', _mock_run_execution_engine)

def test_single_instance_cycle_duration_under_limit(tmp_path: Path) -> None:
    runtime, _simulator, instances = _startup_runtime(tmp_path)
    instance = instances[0]
    limit_ms = runtime.config.runtime.cycle_max_duration_ms
    result = run_instance_cycle(runtime, instance, use_global_universe=False, timestamp_utc=FIXTURE_CYCLE_UTC)
    assert result.completed
    assert result.performance_timings is not None
    assert result.performance_timings.cycle_duration_ms < limit_ms

def test_ten_instances_sequential_under_combined_limit(tmp_path: Path) -> None:
    instances = _build_ten_instances()
    runtime, _simulator, _ = _startup_runtime(tmp_path, instances=instances)
    limit_ms = runtime.config.runtime.cycle_max_duration_ms
    combined_limit_ms = limit_ms * len(instances)
    orchestrator_result = run_runtime_cycles(runtime, instances=instances, use_global_universe=False, timestamp_utc=FIXTURE_CYCLE_UTC)
    assert orchestrator_result.instance_count == len(instances)
    assert orchestrator_result.completed_count == len(instances)
    assert orchestrator_result.failed_count == 0
    total_cycle_duration_ms = 0
    for instance_result in orchestrator_result.instance_results:
        assert instance_result.performance_timings is not None
        cycle_duration_ms = instance_result.performance_timings.cycle_duration_ms
        assert cycle_duration_ms < limit_ms
        total_cycle_duration_ms += cycle_duration_ms
    assert total_cycle_duration_ms < combined_limit_ms
