from __future__ import annotations
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, MutableMapping
import pytest
from engine.core.instance import Instance
from engine.core.lifecycle import LiveRuntime, startup
from engine.core.paths import SystemPaths
from engine.core.cycle import InstanceCycleData, load_instance_cycle_data, update_instance_instrument_state, update_instance_spread_model, validate_market_for_cycle, validate_sensor_for_cycle, validate_status_for_cycle, validate_universe_for_cycle
from engine.journal.error_journal import build_error_journal_path, log_error
from engine.normalizer.market_normalizer import NormalizedMarketBar
from engine.normalizer.spread_model import SpreadModelSnapshot
from engine.protocol.constants import ErrorType
from engine.protocol.models import SensorReading, UniverseRecord
from engine.protocol.parser import parse_error_journal_line, parse_spread_state
from engine.state.instance_state import InstanceState
from engine.state.spread_state import SpreadState
from engine.validator.market_validator import ValidationResult
from tests.core.config_payload import valid_system_config_payload
FIXTURES_DIR = Path(__file__).parent / 'fixtures'
MODULE_NAME = 'integration.data_pipeline'

@dataclass(frozen=True)
class DataPipelineResult:
    completed: bool
    error_logged: bool
    loaded: InstanceCycleData | None = None
    market_bars: tuple[NormalizedMarketBar, ...] | None = None
    sensor_reading: SensorReading | None = None
    universe: UniverseRecord | None = None
    spread_snapshot: SpreadModelSnapshot | None = None

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

def _install_integration_fixtures(paths: SystemPaths, instance: Instance) -> None:
    paths.ensure_account_directories(instance.account_id)
    account_dir = paths.account_dir(instance.account_id)
    shutil.copyfile(FIXTURES_DIR / instance.market_filename(), account_dir / instance.market_filename())
    shutil.copyfile(FIXTURES_DIR / instance.sensor_filename(), account_dir / instance.sensor_filename())
    shutil.copyfile(FIXTURES_DIR / instance.status_filename(), account_dir / instance.status_filename())
    shutil.copyfile(FIXTURES_DIR / 'universe.json', account_dir / 'universe.json')

def _startup_runtime(tmp_path: Path) -> tuple[LiveRuntime, Instance]:
    config_path = _write_config(tmp_path)
    instance = _instance()
    _install_integration_fixtures(SystemPaths(tmp_path), instance)
    runtime = startup(root_path=tmp_path, config_path=config_path)
    return (runtime, instance)

def _log_pipeline_error(paths: SystemPaths, instance: Instance, *, message: str, context: dict[str, object] | None=None) -> None:
    log_error(paths, instance, module=MODULE_NAME, error_type=ErrorType.VALIDATION.value, message=message, context=context)

def run_instance_data_pipeline(runtime: LiveRuntime, instance: Instance, *, use_global_universe: bool | None=None, timestamp_utc: str='2026-07-07T06:02:00.000Z', cache: MutableMapping[str, Any] | None=None) -> DataPipelineResult:
    instance_memory = runtime.memory.get_or_create(instance)
    try:
        loaded = load_instance_cycle_data(runtime.paths, instance, use_global_universe=use_global_universe, cache=cache)
    except Exception as exc:
        _log_pipeline_error(runtime.paths, instance, message='failed to load instance cycle data', context={'error': str(exc)})
        return DataPipelineResult(completed=False, error_logged=True)
    market_result = validate_market_for_cycle(loaded.market_raw)
    if isinstance(market_result, ValidationResult):
        _log_pipeline_error(runtime.paths, instance, message='market validation failed', context={'errors': list(market_result.errors)})
        return DataPipelineResult(completed=False, error_logged=True, loaded=loaded)
    market_bars = market_result
    sensor_result = validate_sensor_for_cycle(loaded.sensor_raw)
    if isinstance(sensor_result, ValidationResult):
        _log_pipeline_error(runtime.paths, instance, message='sensor validation failed', context={'errors': list(sensor_result.errors)})
        return DataPipelineResult(completed=False, error_logged=True, loaded=loaded)
    sensor_reading = sensor_result
    status_result = validate_status_for_cycle(loaded.status_raw)
    if not status_result.is_valid or status_result.record is None:
        _log_pipeline_error(runtime.paths, instance, message='status validation failed', context={'errors': list(status_result.errors)})
        return DataPipelineResult(completed=False, error_logged=True, loaded=loaded)
    universe_result = validate_universe_for_cycle(loaded.universe_raw)
    if isinstance(universe_result, ValidationResult):
        _log_pipeline_error(runtime.paths, instance, message='universe validation failed', context={'errors': list(universe_result.errors)})
        return DataPipelineResult(completed=False, error_logged=True, loaded=loaded)
    universe = universe_result
    update_instance_instrument_state(instance_memory, market_bars)
    spread_snapshot = update_instance_spread_model(instance_memory=instance_memory, spread_models=runtime.spread_models, sensor_reading=sensor_reading, lookback_bars=runtime.config.analysis.lookback_bars, timestamp_utc=timestamp_utc)
    instance_memory.instance_state.save(runtime.paths)
    instance_memory.spread_state.save(runtime.paths)
    return DataPipelineResult(completed=True, error_logged=False, loaded=loaded, market_bars=market_bars, sensor_reading=sensor_reading, universe=universe, spread_snapshot=spread_snapshot)

def test_full_data_pipeline_for_one_instance(tmp_path: Path) -> None:
    runtime, instance = _startup_runtime(tmp_path)
    result = run_instance_data_pipeline(runtime, instance, use_global_universe=False)
    assert result.completed
    assert not result.error_logged
    assert result.loaded is not None
    assert result.loaded.market_raw.row_count == 3
    assert result.loaded.sensor_raw.row_count == 3
    assert result.loaded.status_raw.raw_text
    assert result.loaded.universe_raw.raw_text
    assert result.market_bars is not None
    assert len(result.market_bars) == 3
    assert all((isinstance(bar, NormalizedMarketBar) for bar in result.market_bars))
    assert result.market_bars[-1].close > result.market_bars[0].close
    assert result.sensor_reading is not None
    assert result.sensor_reading.symbol == 'EURUSD'
    assert result.universe is not None
    assert result.universe.market_regime == 'trending'
    memory = runtime.memory.get_or_create(instance)
    assert memory.instance_state.instrument_digits == 5
    assert memory.instance_state.instrument_point == 1e-05
    assert memory.instance_state.instrument_pip == 0.0001
    instance_state_path = memory.instance_state.path(runtime.paths)
    spread_state_path = memory.spread_state.path(runtime.paths)
    assert instance_state_path.exists()
    assert spread_state_path.exists()
    reloaded_instance_state = InstanceState.load(runtime.paths, instance)
    assert reloaded_instance_state.instrument_digits == 5
    assert reloaded_instance_state.instrument_point == 1e-05
    reloaded_spread_state = SpreadState.load(runtime.paths, instance)
    assert reloaded_spread_state.record is not None
    assert reloaded_spread_state.record.sample_count >= 1

def test_invalid_file_stops_pipeline_with_error_journal(tmp_path: Path) -> None:
    runtime, instance = _startup_runtime(tmp_path)
    spread_before = dict(runtime.spread_models)
    instrument_digits_before = runtime.memory.get_or_create(instance).instance_state.instrument_digits
    invalid_path = runtime.paths.account_dir(instance.account_id) / instance.market_filename()
    invalid_path.write_text((FIXTURES_DIR / 'market_invalid.csv').read_text(encoding='utf-8'), encoding='utf-8')
    result = run_instance_data_pipeline(runtime, instance, use_global_universe=False)
    assert not result.completed
    assert result.error_logged
    assert result.market_bars is None
    assert result.spread_snapshot is None
    assert runtime.spread_models == spread_before
    error_path = build_error_journal_path(runtime.paths, instance)
    assert error_path.exists()
    error_entry = parse_error_journal_line(error_path.read_text(encoding='utf-8').strip())
    assert error_entry.error_type == ErrorType.VALIDATION.value
    assert error_entry.module == MODULE_NAME
    assert 'market validation failed' in error_entry.message
    memory = runtime.memory.get_or_create(instance)
    assert memory.instance_state.instrument_digits == instrument_digits_before
    assert memory.instance_state.instrument_digits == 0

def test_spread_model_updated_after_data_pipeline(tmp_path: Path) -> None:
    runtime, instance = _startup_runtime(tmp_path)
    result = run_instance_data_pipeline(runtime, instance, use_global_universe=False)
    assert result.completed
    assert result.spread_snapshot is not None
    assert result.spread_snapshot.sample_count >= 1
    assert result.spread_snapshot.current_spread > 0
    assert result.spread_snapshot.mean_spread > 0
    assert result.spread_snapshot.relative_spread != 0.0
    assert instance.instance_key in runtime.spread_models
    runtime_snapshot = runtime.spread_models[instance.instance_key]
    assert runtime_snapshot.sample_count == result.spread_snapshot.sample_count
    assert runtime_snapshot.current_spread == result.spread_snapshot.current_spread
    memory = runtime.memory.get_or_create(instance)
    assert memory.spread_state.record is not None
    assert memory.spread_state.record.current_spread == result.spread_snapshot.current_spread
    assert memory.spread_state.record.mean_spread == result.spread_snapshot.mean_spread
    spread_state_path = memory.spread_state.path(runtime.paths)
    persisted = parse_spread_state(spread_state_path.read_text(encoding='utf-8'))
    assert persisted.sample_count == result.spread_snapshot.sample_count
    assert persisted.relative_spread == result.spread_snapshot.relative_spread
