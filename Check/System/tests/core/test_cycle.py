from __future__ import annotations
import json
import shutil
from pathlib import Path
import pytest
from engine.core.instance import Instance
from engine.core.lifecycle import startup
from engine.core.paths import SystemPaths
from engine.core.cycle import InstanceCycleData, apply_closed_bar_entry_gate, build_account_block_reason, build_risk_trade_params, load_instance_cycle_data, resolve_open_position_from_state, resolve_structure_levels, resolve_use_global_universe, run_instance_cycle, run_instance_decision_phase, run_instance_risk_phase, run_instance_trade_management_phase, should_execute_trade, update_instance_instrument_state, update_instance_spread_model, validate_market_for_cycle, validate_sensor_for_cycle, validate_status_for_cycle, validate_universe_for_cycle
from engine.execution.engine import ExecutionResult
from engine.execution.command import OrderCommand
from engine.execution.control_writer import build_control_path
from engine.journal.decision_journal import build_decision_journal_path
from engine.journal.error_journal import build_error_journal_path
from engine.journal.trade_journal import build_trade_journal_path
from engine.normalizer.market_normalizer import NormalizedMarketBar
from engine.decision.engine import DecisionResult
from engine.protocol.constants import Decision, ErrorType, OrderAction, PROTOCOL_SCHEMA_VERSION, REASON_ACCOUNT_NOT_TRADEABLE, REASON_DATA_INVALID, REASON_ENTRY_DEFERRED, RiskResult, Side
from engine.protocol.parser import parse_decision_journal_line, parse_error_journal_line
from engine.protocol.models import SensorReading, StatusPositionSnapshot, StatusRecord, UniverseRecord
from engine.risk.engine import RiskEngineResult
from engine.state.instance_state import InstanceState
from engine.protocol.writer import write_status
from engine.validator.market_validator import ValidationResult
from tests.core.config_payload import FIXTURE_CYCLE_UTC, valid_system_config_payload
FIXTURES_DIR = Path(__file__).parent.parent / 'loader' / 'fixtures'

def _write_config(root: Path) -> Path:
    payload = valid_system_config_payload()
    payload['system']['root_path'] = str(root)
    payload['analysis'] = {**payload['analysis'], 'lookback_bars': 3, 'structure_lookback_bars': 3}
    config_dir = root / 'config'
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / 'system.json'
    config_path.write_text(json.dumps(payload), encoding='utf-8')
    return config_path

def _bullish_market_csv() -> str:
    return 'time_utc,open,high,low,close,volume,symbol,timeframe,digits,point\n2026-07-07T06:00:00.000Z,1.10000,1.10200,1.09900,1.10150,120,EURUSD,M1,5,0.00001\n2026-07-07T06:01:00.000Z,1.10150,1.10300,1.10050,1.10220,110,EURUSD,M1,5,0.00001\n2026-07-07T06:02:00.000Z,1.10220,1.10400,1.10100,1.10310,105,EURUSD,M1,5,0.00001\n'

def _instance() -> Instance:
    return Instance(account_id='12345', symbol='EURUSD', magic=100001)

def _install_valid_fixtures(paths: SystemPaths, instance: Instance) -> None:
    paths.ensure_account_directories(instance.account_id)
    account_dir = paths.account_dir(instance.account_id)
    (account_dir / instance.market_filename()).write_text(_bullish_market_csv(), encoding='utf-8')
    shutil.copyfile(FIXTURES_DIR / 'sensor_valid.csv', account_dir / instance.sensor_filename())
    shutil.copyfile(FIXTURES_DIR / 'status_valid.json', account_dir / instance.status_filename())
    shutil.copyfile(FIXTURES_DIR / 'universe_valid.json', account_dir / 'universe.json')

def _startup_runtime(tmp_path: Path):
    config_path = _write_config(tmp_path)
    instance = _instance()
    _install_valid_fixtures(SystemPaths(tmp_path), instance)
    runtime = startup(root_path=tmp_path, config_path=config_path)
    return (runtime, instance)

def test_build_risk_trade_params_reads_from_runtime_config(tmp_path: Path) -> None:
    runtime, _instance = _startup_runtime(tmp_path)
    params = build_risk_trade_params(runtime)
    assert params.volume_step == runtime.config.risk.volume_step
    assert params.max_stop_loss_pips == runtime.config.risk.max_stop_loss_pips
    assert params.volume_step > 0
    assert params.max_stop_loss_pips > 0
    assert not hasattr(params, 'max_risk_per_trade_percent')

def test_resolve_use_global_universe_checks_global_file(tmp_path: Path) -> None:
    paths = SystemPaths(tmp_path)
    paths.ensure_directories()
    assert resolve_use_global_universe(paths) is False
    paths.universe_file.write_text('{}', encoding='utf-8')
    assert resolve_use_global_universe(paths) is True

def test_load_instance_cycle_data_loads_all_required_files(tmp_path: Path) -> None:
    runtime, instance = _startup_runtime(tmp_path)
    loaded = load_instance_cycle_data(runtime.paths, instance, use_global_universe=False)
    assert isinstance(loaded, InstanceCycleData)
    assert loaded.market_raw.row_count == 3
    assert loaded.sensor_raw.row_count == 3
    assert loaded.status_raw.raw_text
    assert loaded.universe_raw.raw_text

def test_validate_market_for_cycle_returns_normalized_bars(tmp_path: Path) -> None:
    runtime, instance = _startup_runtime(tmp_path)
    loaded = load_instance_cycle_data(runtime.paths, instance, use_global_universe=False)
    result = validate_market_for_cycle(loaded.market_raw)
    assert isinstance(result, tuple)
    assert len(result) == 3
    assert all((isinstance(bar, NormalizedMarketBar) for bar in result))

def test_validate_market_for_cycle_invalid_market_returns_validation_result(tmp_path: Path) -> None:
    runtime, instance = _startup_runtime(tmp_path)
    invalid_path = runtime.paths.account_dir(instance.account_id) / instance.market_filename()
    invalid_path.write_text((FIXTURES_DIR / 'market_missing.csv').read_text(encoding='utf-8'), encoding='utf-8')
    loaded = load_instance_cycle_data(runtime.paths, instance, use_global_universe=False)
    result = validate_market_for_cycle(loaded.market_raw)
    assert isinstance(result, ValidationResult)
    assert not result.is_valid

def test_validate_sensor_for_cycle_returns_last_reading(tmp_path: Path) -> None:
    runtime, instance = _startup_runtime(tmp_path)
    loaded = load_instance_cycle_data(runtime.paths, instance, use_global_universe=False)
    result = validate_sensor_for_cycle(loaded.sensor_raw)
    assert not isinstance(result, ValidationResult)
    assert result.symbol == 'EURUSD'

def test_validate_status_for_cycle_returns_tradeable_status(tmp_path: Path) -> None:
    runtime, instance = _startup_runtime(tmp_path)
    loaded = load_instance_cycle_data(runtime.paths, instance, use_global_universe=False)
    result = validate_status_for_cycle(loaded.status_raw)
    assert result.is_valid
    assert result.is_tradeable
    assert result.record is not None

def test_validate_universe_for_cycle_returns_universe_record(tmp_path: Path) -> None:
    runtime, instance = _startup_runtime(tmp_path)
    loaded = load_instance_cycle_data(runtime.paths, instance, use_global_universe=False)
    result = validate_universe_for_cycle(loaded.universe_raw)
    assert isinstance(result, UniverseRecord)
    assert result.market_regime == 'trending'

def test_build_account_block_reason_none_for_tradeable_status() -> None:
    status = StatusRecord(schema_version=PROTOCOL_SCHEMA_VERSION, timestamp_utc='2026-07-07T06:00:00.000Z', account_id='12345', connected=True, trade_allowed=True, balance=10000.0, equity=10000.0, margin_free=9000.0, ea_version='1.0.0')
    assert build_account_block_reason(status) is None

def test_build_account_block_reason_for_non_tradeable_status() -> None:
    status = StatusRecord(schema_version=PROTOCOL_SCHEMA_VERSION, timestamp_utc='2026-07-07T06:00:00.000Z', account_id='12345', connected=False, trade_allowed=False, balance=10000.0, equity=10000.0, margin_free=9000.0, ea_version='1.0.0')
    reason = build_account_block_reason(status)
    assert reason is not None
    assert REASON_ACCOUNT_NOT_TRADEABLE in reason

def test_update_instance_instrument_state_sets_digits_point_and_pip(tmp_path: Path) -> None:
    runtime, instance = _startup_runtime(tmp_path)
    loaded = load_instance_cycle_data(runtime.paths, instance, use_global_universe=False)
    market_bars = validate_market_for_cycle(loaded.market_raw)
    assert isinstance(market_bars, tuple)
    memory = runtime.memory.get_or_create(instance)
    update_instance_instrument_state(memory, market_bars)
    assert memory.instance_state.instrument_digits == 5
    assert memory.instance_state.instrument_point == 1e-05
    assert memory.instance_state.instrument_pip == 0.0001

def test_update_instance_spread_model_updates_spread_state_and_runtime_models(tmp_path: Path) -> None:
    runtime, instance = _startup_runtime(tmp_path)
    loaded = load_instance_cycle_data(runtime.paths, instance, use_global_universe=False)
    sensor = validate_sensor_for_cycle(loaded.sensor_raw)
    assert not isinstance(sensor, ValidationResult)
    memory = runtime.memory.get_or_create(instance)
    snapshot = update_instance_spread_model(instance_memory=memory, spread_models=runtime.spread_models, sensor_reading=sensor, lookback_bars=runtime.config.analysis.lookback_bars, timestamp_utc='2026-07-07T06:00:00.000Z')
    assert snapshot.sample_count >= 1
    assert instance.instance_key in runtime.spread_models
    assert memory.spread_state.record is not None

def test_resolve_structure_levels_returns_swing_high_and_low(tmp_path: Path) -> None:
    runtime, instance = _startup_runtime(tmp_path)
    loaded = load_instance_cycle_data(runtime.paths, instance, use_global_universe=False)
    market_bars = validate_market_for_cycle(loaded.market_raw)
    assert isinstance(market_bars, tuple)
    structure = resolve_structure_levels(market_bars, structure_lookback_bars=runtime.config.analysis.structure_lookback_bars)
    assert structure.swing_high >= structure.swing_low

def test_run_instance_decision_phase_calculates_buy_and_sell_candidates(tmp_path: Path) -> None:
    runtime, instance = _startup_runtime(tmp_path)
    loaded = load_instance_cycle_data(runtime.paths, instance, use_global_universe=False)
    market_bars = validate_market_for_cycle(loaded.market_raw)
    sensor = validate_sensor_for_cycle(loaded.sensor_raw)
    universe = validate_universe_for_cycle(loaded.universe_raw)
    assert isinstance(market_bars, tuple)
    assert not isinstance(sensor, ValidationResult)
    assert isinstance(universe, UniverseRecord)
    memory = runtime.memory.get_or_create(instance)
    update_instance_instrument_state(memory, market_bars)
    snapshot = update_instance_spread_model(instance_memory=memory, spread_models=runtime.spread_models, sensor_reading=sensor, lookback_bars=runtime.config.analysis.lookback_bars, timestamp_utc='2026-07-07T06:00:00.000Z')
    decision = run_instance_decision_phase(universe=universe, market_bars=market_bars, instance_memory=memory, relative_spread=snapshot.relative_spread, runtime=runtime)
    assert decision.buy_candidate is not None
    assert decision.sell_candidate is not None

def test_run_instance_risk_phase_returns_allow_or_block(tmp_path: Path) -> None:
    runtime, instance = _startup_runtime(tmp_path)
    loaded = load_instance_cycle_data(runtime.paths, instance, use_global_universe=False)
    market_bars = validate_market_for_cycle(loaded.market_raw)
    sensor = validate_sensor_for_cycle(loaded.sensor_raw)
    universe = validate_universe_for_cycle(loaded.universe_raw)
    status = validate_status_for_cycle(loaded.status_raw).record
    assert isinstance(market_bars, tuple)
    assert not isinstance(sensor, ValidationResult)
    assert isinstance(universe, UniverseRecord)
    assert status is not None
    memory = runtime.memory.get_or_create(instance)
    update_instance_instrument_state(memory, market_bars)
    snapshot = update_instance_spread_model(instance_memory=memory, spread_models=runtime.spread_models, sensor_reading=sensor, lookback_bars=runtime.config.analysis.lookback_bars, timestamp_utc='2026-07-07T06:00:00.000Z')
    decision = run_instance_decision_phase(universe=universe, market_bars=market_bars, instance_memory=memory, relative_spread=snapshot.relative_spread, runtime=runtime)
    risk = run_instance_risk_phase(decision_result=decision, instance_memory=memory, status=status, market_bars=market_bars, runtime=runtime)
    assert risk.result in {RiskResult.ALLOW.value, RiskResult.BLOCK.value}

def test_should_execute_trade_requires_allow_and_direction(tmp_path: Path) -> None:
    runtime, instance = _startup_runtime(tmp_path)
    from engine.risk.engine import RiskEngineResult
    loaded = load_instance_cycle_data(runtime.paths, instance, use_global_universe=False)
    market_bars = validate_market_for_cycle(loaded.market_raw)
    universe = validate_universe_for_cycle(loaded.universe_raw)
    assert isinstance(market_bars, tuple)
    assert isinstance(universe, UniverseRecord)
    memory = runtime.memory.get_or_create(instance)
    update_instance_instrument_state(memory, market_bars)
    decision = run_instance_decision_phase(universe=universe, market_bars=market_bars, instance_memory=memory, relative_spread=1.0, runtime=runtime)
    allow = RiskEngineResult(result=RiskResult.ALLOW.value, reason='', position_size=0.1, stop_loss=1.09, take_profit=1.12)
    block = RiskEngineResult(result=RiskResult.BLOCK.value, reason='blocked', position_size=None, stop_loss=None, take_profit=None)
    assert should_execute_trade(runtime=runtime, decision_result=decision, risk_engine_result=allow) == (decision.decision in {Decision.BUY.value, Decision.SELL.value})
    assert not should_execute_trade(runtime=runtime, decision_result=decision, risk_engine_result=block)

def test_run_instance_cycle_completes_with_fixture_data_and_writes_decision_journal(tmp_path: Path) -> None:
    runtime, instance = _startup_runtime(tmp_path)
    result = run_instance_cycle(runtime, instance, use_global_universe=False, timestamp_utc=FIXTURE_CYCLE_UTC)
    assert result.completed
    assert not result.error_logged
    assert result.decision_result is not None
    assert result.risk_engine_result is not None
    assert result.decision_journal_logged
    journal_path = build_decision_journal_path(runtime.paths, instance)
    assert journal_path.exists()
    entry = parse_decision_journal_line(journal_path.read_text(encoding='utf-8').strip())
    assert entry.decision_id == result.decision_result.decision_id
    assert entry.decision == result.decision_result.decision

def test_run_instance_cycle_invalid_market_logs_error_and_skips_trade(tmp_path: Path) -> None:
    runtime, instance = _startup_runtime(tmp_path)
    invalid_path = runtime.paths.account_dir(instance.account_id) / instance.market_filename()
    invalid_path.write_text((FIXTURES_DIR / 'market_missing.csv').read_text(encoding='utf-8'), encoding='utf-8')
    result = run_instance_cycle(runtime, instance, use_global_universe=False, timestamp_utc=FIXTURE_CYCLE_UTC)
    assert not result.completed
    assert result.error_logged
    assert result.decision_result is None
    error_path = build_error_journal_path(runtime.paths, instance)
    assert error_path.exists()
    error_entry = parse_error_journal_line(error_path.read_text(encoding='utf-8').strip())
    assert error_entry.error_type == ErrorType.VALIDATION.value
    assert 'market validation failed' in error_entry.message
    assert not build_control_path(runtime.paths, instance).exists()
    assert not build_trade_journal_path(runtime.paths, instance).exists()

def test_run_instance_cycle_calculates_buy_and_sell_each_cycle(tmp_path: Path) -> None:
    runtime, instance = _startup_runtime(tmp_path)
    result = run_instance_cycle(runtime, instance, use_global_universe=False, timestamp_utc=FIXTURE_CYCLE_UTC)
    assert result.decision_result is not None
    assert result.decision_result.buy_candidate is not None
    assert result.decision_result.sell_candidate is not None

def test_run_instance_cycle_invalid_status_produces_block_without_trade(tmp_path: Path) -> None:
    runtime, instance = _startup_runtime(tmp_path)
    status_path = runtime.paths.account_dir(instance.account_id) / instance.status_filename()
    status_path.write_text('{not-valid-json', encoding='utf-8')
    result = run_instance_cycle(runtime, instance, use_global_universe=False, timestamp_utc=FIXTURE_CYCLE_UTC)
    assert not result.completed
    assert result.decision_result is not None
    assert result.decision_result.decision == Decision.BLOCK.value
    assert REASON_DATA_INVALID in result.decision_result.reason
    assert not result.trade_executed

def test_run_instance_cycle_account_not_tradeable_produces_block_without_trade(tmp_path: Path) -> None:
    runtime, instance = _startup_runtime(tmp_path)
    status_path = runtime.paths.account_dir(instance.account_id) / instance.status_filename()
    status_path.write_text(json.dumps({'schema_version': PROTOCOL_SCHEMA_VERSION, 'timestamp_utc': '2026-07-07T06:00:00.000Z', 'account_id': '12345', 'connected': False, 'trade_allowed': False, 'balance': 10000.0, 'equity': 10000.0, 'margin_free': 9000.0, 'ea_version': '1.0.0'}), encoding='utf-8')
    result = run_instance_cycle(runtime, instance, use_global_universe=False, timestamp_utc=FIXTURE_CYCLE_UTC)
    assert result.completed
    assert result.decision_result is not None
    assert result.decision_result.decision == Decision.BLOCK.value
    assert REASON_ACCOUNT_NOT_TRADEABLE in result.decision_result.reason
    assert not result.trade_executed

def test_run_instance_trade_management_phase_returns_modify_for_breakeven_progress(tmp_path: Path) -> None:
    runtime, instance = _startup_runtime(tmp_path)
    instance_memory = runtime.memory.get_or_create(instance)
    instance_memory.instance_state.update_position(open_ticket=555, position_side=Side.BUY.value, position_volume=0.1, entry_price=1.1, stop_loss=1.098, take_profit=1.104, position_last_bar_utc=FIXTURE_CYCLE_UTC)
    loaded = load_instance_cycle_data(runtime.paths, instance, use_global_universe=False)
    market_bars = validate_market_for_cycle(loaded.market_raw)
    assert not isinstance(market_bars, ValidationResult)
    bullish_bars = (*market_bars[:-1], NormalizedMarketBar(time_utc=market_bars[-1].time_utc, open=1.1018, high=1.1022, low=1.1015, close=1.102, volume=market_bars[-1].volume, symbol=market_bars[-1].symbol, timeframe=market_bars[-1].timeframe, digits=market_bars[-1].digits, point=market_bars[-1].point, bar_index=market_bars[-1].bar_index))
    sensor = SensorReading(time_utc=FIXTURE_CYCLE_UTC, bid=1.102, ask=1.1022, spread=0.0002, spread_points=20.0, symbol='EURUSD', digits=5, point=1e-05)
    management_result = run_instance_trade_management_phase(instance_memory=instance_memory, market_bars=bullish_bars, runtime=runtime, sensor_reading=sensor, market_bar_time_utc=FIXTURE_CYCLE_UTC, current_utc=FIXTURE_CYCLE_UTC)
    assert management_result.action == OrderAction.MODIFY.value
    assert management_result.stop_loss is not None
    assert management_result.stop_loss > 1.098
    assert management_result.reason.startswith('TRADE_MANAGEMENT_')

def test_resolve_open_position_without_broker_tp_uses_reference_or_synthetic() -> None:
    state = InstanceState(instance=Instance(account_id='12345', symbol='EURUSD', magic=100001))
    state.update_position(open_ticket=555, position_side=Side.BUY.value, position_volume=0.01, entry_price=1.1, stop_loss=1.098, take_profit=0.0)
    without_reward = resolve_open_position_from_state(state)
    assert without_reward is not None
    assert without_reward.take_profit == 0.0
    synthetic = resolve_open_position_from_state(state, reward_ratio=2.0)
    assert synthetic is not None
    assert synthetic.take_profit == pytest.approx(1.104)
    state.position_reference_take_profit = 1.105
    referenced = resolve_open_position_from_state(state, reward_ratio=2.0)
    assert referenced is not None
    assert referenced.take_profit == pytest.approx(1.105)

def test_run_instance_trade_management_phase_trails_without_broker_take_profit(tmp_path: Path) -> None:
    from dataclasses import replace
    from datetime import datetime, timezone
    runtime, instance = _startup_runtime(tmp_path)
    runtime.config = replace(runtime.config, trade_management=replace(runtime.config.trade_management, use_fixed_take_profit=False, allow_close=False))
    instance_memory = runtime.memory.get_or_create(instance)
    instance_memory.instance_state.update_position(open_ticket=555, position_side=Side.BUY.value, position_volume=0.01, entry_price=1.1, stop_loss=1.098, take_profit=0.0, position_last_bar_utc='2026-07-07T06:03:00.000Z')
    instance_memory.instance_state.update_instrument(digits=5, point=1e-05, pip=0.0001)
    market_bars = tuple((NormalizedMarketBar(time_utc=datetime(2026, 7, 7, 6, index, tzinfo=timezone.utc), open=1.1 + index * 0.0002, high=1.101 + index * 0.0002, low=1.0995 + index * 0.0002, close=1.1005 + index * 0.0002, volume=100.0, symbol='EURUSD', timeframe='M1', digits=5, point=1e-05, bar_index=index) for index in range(5)))
    sensor = SensorReading(time_utc='2026-07-07T06:04:00.000Z', bid=1.1005 + 4 * 0.0002, ask=1.1007 + 4 * 0.0002, spread=0.0002, spread_points=20.0, symbol='EURUSD', digits=5, point=1e-05)
    management_result = run_instance_trade_management_phase(instance_memory=instance_memory, market_bars=market_bars, runtime=runtime, sensor_reading=sensor, market_bar_time_utc='2026-07-07T06:04:00.000Z', current_utc='2026-07-07T06:04:00.000Z')
    assert management_result.action == OrderAction.MODIFY.value
    assert management_result.stop_loss is not None
    assert management_result.stop_loss > 1.098
    assert 'TRAILING' in management_result.reason or 'BREAKEVEN' in management_result.reason

def test_run_instance_cycle_passes_trade_management_to_execution(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from engine.risk.trade_management import TradeManagementResult
    runtime, instance = _startup_runtime(tmp_path)
    instance_memory = runtime.memory.get_or_create(instance)
    instance_memory.instance_state.update_position(open_ticket=555, position_side=Side.BUY.value, position_volume=0.1, entry_price=1.1, stop_loss=1.098, take_profit=1.104)
    instance_memory.instance_state.save(runtime.paths)
    status_path = runtime.paths.account_dir(instance.account_id) / instance.status_filename()
    status_path.write_text(write_status(StatusRecord(schema_version=PROTOCOL_SCHEMA_VERSION, timestamp_utc=FIXTURE_CYCLE_UTC, account_id=instance.account_id, connected=True, trade_allowed=True, balance=10000.0, equity=10020.5, margin_free=9800.0, ea_version='1.0.0', open_positions=(StatusPositionSnapshot(symbol=instance.symbol, magic=instance.magic, ticket=555, side=Side.BUY.value, volume=0.1, entry_price=1.1, stop_loss=1.098, take_profit=1.104),))), encoding='utf-8')
    captured: dict[str, object] = {}

    def _mock_tm(**kwargs: object) -> TradeManagementResult:
        return TradeManagementResult(action=OrderAction.MODIFY.value, reason='TRADE_MANAGEMENT_TRAILING: test', stop_loss=1.099, take_profit=1.104)

    def _mock_run_execution_engine(**kwargs: object) -> ExecutionResult:
        captured.setdefault('calls', [])
        captured['calls'].append(kwargs.get('management_result'))
        captured['management_result'] = kwargs.get('management_result')
        return ExecutionResult(order_command=OrderCommand(command_id='mgmt-cmd', action=OrderAction.NONE.value, reason='', decision_id='decision-1'), control_published=True, trade_intent_logged=False, ack_interpretation=None, trade_journal_entry=None, state_updated=False)
    monkeypatch.setattr('engine.core.cycle.run_instance_trade_management_phase', _mock_tm)
    monkeypatch.setattr('engine.core.cycle.run_execution_engine', _mock_run_execution_engine)
    result = run_instance_cycle(runtime, instance, use_global_universe=False, timestamp_utc=FIXTURE_CYCLE_UTC)
    assert result.completed
    assert 'management_result' in captured
    mgmt = captured['management_result']
    assert mgmt is not None
    assert getattr(mgmt, 'action', None) == OrderAction.MODIFY.value
    assert resolve_open_position_from_state(instance_memory.instance_state) is not None

def test_apply_closed_bar_entry_gate_allows_first_cycle_on_new_bar(tmp_path: Path) -> None:
    runtime, instance = _startup_runtime(tmp_path)
    state = InstanceState(instance=instance)
    decision = DecisionResult(decision_id='d1', decision=Decision.BUY.value, reason='BUY', preferred_side=Side.BUY.value, buy_candidate=None, sell_candidate=None, buy_score=0.8, sell_score=0.2, analysis_context={})
    risk = RiskEngineResult(result=RiskResult.ALLOW.value, reason='', position_size=0.1, stop_loss=1.09, take_profit=1.11)
    runtime.allow_control_writes = True
    result = apply_closed_bar_entry_gate(runtime=runtime, instance_state=state, decision_result=decision, risk_engine_result=risk, market_bar_time_utc='2026-07-07T06:02:00.000Z')
    assert result.result == RiskResult.ALLOW.value
    assert state.last_seen_market_bar_utc == '2026-07-07T06:02:00.000Z'

def test_apply_closed_bar_entry_gate_blocks_repeat_open_on_same_bar(tmp_path: Path) -> None:
    runtime, instance = _startup_runtime(tmp_path)
    state = InstanceState(instance=instance)
    state.last_seen_market_bar_utc = '2026-07-07T06:02:00.000Z'
    decision = DecisionResult(decision_id='d1', decision=Decision.BUY.value, reason='BUY', preferred_side=Side.BUY.value, buy_candidate=None, sell_candidate=None, buy_score=0.8, sell_score=0.2, analysis_context={})
    risk = RiskEngineResult(result=RiskResult.ALLOW.value, reason='', position_size=0.1, stop_loss=1.09, take_profit=1.11)
    runtime.allow_control_writes = True
    result = apply_closed_bar_entry_gate(runtime=runtime, instance_state=state, decision_result=decision, risk_engine_result=risk, market_bar_time_utc='2026-07-07T06:02:00.000Z')
    assert result.result == RiskResult.BLOCK.value
    assert 'ENTRY_DEFERRED' in result.reason or REASON_ENTRY_DEFERRED in result.reason

def test_apply_closed_bar_entry_gate_hold_does_not_consume_bar(tmp_path: Path) -> None:
    runtime, instance = _startup_runtime(tmp_path)
    state = InstanceState(instance=instance)
    decision = DecisionResult(decision_id='d1', decision=Decision.WAIT.value, reason='WAIT', preferred_side=None, buy_candidate=None, sell_candidate=None, buy_score=0.4, sell_score=0.4, analysis_context={})
    risk = RiskEngineResult(result=RiskResult.BLOCK.value, reason='no trade', position_size=None, stop_loss=None, take_profit=None)
    runtime.allow_control_writes = True
    result = apply_closed_bar_entry_gate(runtime=runtime, instance_state=state, decision_result=decision, risk_engine_result=risk, market_bar_time_utc='2026-07-07T06:02:00.000Z')
    assert result.result == RiskResult.BLOCK.value
    assert not state.last_seen_market_bar_utc

def test_apply_closed_bar_entry_gate_allows_open_after_prior_hold_on_same_bar(tmp_path: Path) -> None:
    runtime, instance = _startup_runtime(tmp_path)
    state = InstanceState(instance=instance)
    hold = DecisionResult(decision_id='d0', decision=Decision.WAIT.value, reason='WAIT', preferred_side=None, buy_candidate=None, sell_candidate=None, buy_score=0.4, sell_score=0.4, analysis_context={})
    blocked = RiskEngineResult(result=RiskResult.BLOCK.value, reason='no trade', position_size=None, stop_loss=None, take_profit=None)
    runtime.allow_control_writes = True
    apply_closed_bar_entry_gate(runtime=runtime, instance_state=state, decision_result=hold, risk_engine_result=blocked, market_bar_time_utc='2026-07-07T06:02:00.000Z')
    buy = DecisionResult(decision_id='d1', decision=Decision.BUY.value, reason='BUY', preferred_side=Side.BUY.value, buy_candidate=None, sell_candidate=None, buy_score=0.8, sell_score=0.2, analysis_context={})
    allow = RiskEngineResult(result=RiskResult.ALLOW.value, reason='', position_size=0.1, stop_loss=1.09, take_profit=1.11)
    result = apply_closed_bar_entry_gate(runtime=runtime, instance_state=state, decision_result=buy, risk_engine_result=allow, market_bar_time_utc='2026-07-07T06:02:00.000Z')
    assert result.result == RiskResult.ALLOW.value
    assert state.last_seen_market_bar_utc == '2026-07-07T06:02:00.000Z'
