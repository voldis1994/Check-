from __future__ import annotations
import json
from pathlib import Path
from typing import Any
import pytest
from engine.core.cycle import InstanceCycleResult, run_instance_cycle
from engine.core.instance import Instance
from engine.core.lifecycle import startup
from engine.core.orchestrator import run_runtime_cycles
from engine.core.paths import SystemPaths
from engine.execution.ack_reader import build_ack_path
from engine.core.history import read_archived_control_text
from engine.execution.control_writer import build_control_path
from engine.journal.decision_journal import build_decision_journal_path
from engine.journal.error_journal import build_error_journal_path
from engine.journal.trade_journal import build_trade_journal_path
from engine.protocol.constants import AckStatus, Decision, OrderAction, REASON_ACCOUNT_NOT_TRADEABLE, REASON_EQUAL_SCORES, RiskResult
from engine.protocol.parser import parse_control, parse_decision_journal_line, parse_trade_journal_line
from engine.protocol.writer import DECISION_JOURNAL_REQUIRED_FIELDS, TRADE_JOURNAL_REQUIRED_FIELDS
from engine.state.instance_state import InstanceState
from engine.state.spread_state import SpreadState
from tests.core.config_payload import valid_system_config_payload
from tests.e2e.simulator.mt4_simulator import MT4Simulator, build_market_csv, build_sensor_csv, build_status_json, build_universe_json
from tests.protocol.test_writer import required_fields_present
FIXED_COMMAND_ID = 'cmd-e2e-full-cycle-1'

def _write_config(root: Path, *, instances: list[dict[str, Any]] | None=None, analysis_overrides: dict[str, Any] | None=None) -> Path:
    payload = valid_system_config_payload()
    payload['system']['root_path'] = str(root)
    analysis = {**payload['analysis'], 'lookback_bars': 3, 'structure_lookback_bars': 3}
    if analysis_overrides is not None:
        analysis = {**analysis, **analysis_overrides}
    payload['analysis'] = analysis
    if instances is not None:
        payload['instances'] = instances
    config_dir = root / 'config'
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / 'system.json'
    config_path.write_text(json.dumps(payload), encoding='utf-8')
    return config_path

def _instance(*, account_id: str='12345', symbol: str='EURUSD', magic: int=100001) -> Instance:
    return Instance(account_id=account_id, symbol=symbol, magic=magic)

def _startup_runtime(tmp_path: Path, *, instances: list[dict[str, Any]] | None=None, analysis_overrides: dict[str, Any] | None=None):
    config_path = _write_config(tmp_path, instances=instances, analysis_overrides=analysis_overrides)
    return startup(root_path=tmp_path, config_path=config_path)

def _patch_fixed_command_id(monkeypatch: pytest.MonkeyPatch) -> None:
    counter = {'value': 0}

    def _uuid4() -> str:
        counter['value'] += 1
        return FIXED_COMMAND_ID if counter['value'] == 1 else f'cmd-e2e-{counter['value']}'
    monkeypatch.setattr('engine.execution.command.uuid4', _uuid4)

def _run_simulated_full_cycle(tmp_path: Path, instance: Instance, simulator: MT4Simulator, monkeypatch: pytest.MonkeyPatch, *, analysis_overrides: dict[str, Any] | None=None, market_scenario: str='bullish', status_scenario: str='tradeable', timestamp_utc: str='2026-07-07T06:02:00.000Z') -> InstanceCycleResult:
    _patch_fixed_command_id(monkeypatch)
    runtime = _startup_runtime(tmp_path, analysis_overrides=analysis_overrides)
    simulator.export_tick(instance, market_scenario=market_scenario, status_scenario=status_scenario, timestamp_utc=timestamp_utc)
    simulator.install_auto_ack_hook(monkeypatch)
    return run_instance_cycle(runtime, instance, use_global_universe=False, timestamp_utc=timestamp_utc)

def _assert_phase_outcomes(result: InstanceCycleResult, paths: SystemPaths, instance: Instance, *, expect_trade: bool) -> None:
    assert result.completed
    assert not result.error_logged
    assert result.decision_result is not None
    assert result.risk_engine_result is not None
    assert result.decision_journal_logged
    decision_path = build_decision_journal_path(paths, instance)
    assert decision_path.exists()
    decision_entry = parse_decision_journal_line(decision_path.read_text(encoding='utf-8').strip())
    decision_payload = json.loads(decision_path.read_text(encoding='utf-8').strip())
    assert required_fields_present(decision_payload, DECISION_JOURNAL_REQUIRED_FIELDS)
    assert decision_entry.decision == result.decision_result.decision
    memory_paths = paths
    reloaded_state = InstanceState.load(memory_paths, instance)
    assert reloaded_state.instrument_digits == 5
    assert reloaded_state.instrument_point == 1e-05
    assert reloaded_state.last_decision == result.decision_result.decision
    spread_state = SpreadState.load(memory_paths, instance)
    assert spread_state.record is not None
    assert spread_state.record.sample_count >= 1
    control_path = build_control_path(paths, instance)
    if expect_trade:
        archived_control_text = read_archived_control_text(paths, instance)
        assert archived_control_text is not None
        control = parse_control(archived_control_text)
    else:
        assert not control_path.exists()
        control = None
    if expect_trade:
        assert result.decision_result.decision in {Decision.BUY.value, Decision.SELL.value}
        assert result.risk_engine_result.result == RiskResult.ALLOW.value
        assert result.trade_executed
        assert control.action == OrderAction.OPEN.value
        assert result.execution_result is not None
        assert result.execution_result.trade_journal_entry is not None
        trade_path = build_trade_journal_path(paths, instance)
        assert trade_path.exists()
        trade_entry = parse_trade_journal_line(trade_path.read_text(encoding='utf-8').strip())
        trade_payload = json.loads(trade_path.read_text(encoding='utf-8').strip())
        assert required_fields_present(trade_payload, TRADE_JOURNAL_REQUIRED_FIELDS)
        assert trade_entry.ack_status == AckStatus.SUCCESS.value
        assert reloaded_state.open_ticket is not None
        assert reloaded_state.last_ack_status == AckStatus.SUCCESS.value
    else:
        assert not result.trade_executed
        assert control is None
        assert not build_trade_journal_path(paths, instance).exists()

def test_build_market_csv_supports_bullish_and_bearish_scenarios() -> None:
    bullish = build_market_csv(symbol='EURUSD', scenario='bullish')
    bearish = build_market_csv(symbol='GBPUSD', scenario='bearish')
    assert 'EURUSD' in bullish
    assert 'GBPUSD' in bearish
    assert bullish.splitlines()[1].endswith('1.10150,120,EURUSD,M1,5,0.00001')
    assert bearish.splitlines()[-1].startswith('2026-07-07T06:02:00.000Z,1.10120')

def test_build_sensor_csv_supports_bullish_and_bearish_scenarios() -> None:
    bullish = build_sensor_csv(symbol='EURUSD', scenario='bullish')
    bearish = build_sensor_csv(symbol='EURUSD', scenario='bearish')
    assert bullish.count('\n') == 4
    assert bearish.count('\n') == 4
    assert '1.10290' in bullish
    assert '1.09940' in bearish

def test_build_status_json_reflects_tradeable_state() -> None:
    tradeable = json.loads(build_status_json(account_id='12345', scenario='tradeable'))
    blocked = json.loads(build_status_json(account_id='12345', scenario='not_tradeable'))
    assert tradeable['trade_allowed'] is True
    assert blocked['trade_allowed'] is False
    assert blocked['connected'] is False

def test_build_universe_json_contains_required_context() -> None:
    universe = json.loads(build_universe_json())
    assert universe['market_regime'] == 'trending'
    assert universe['session'] == 'LONDON'

def test_mt4_simulator_export_tick_writes_account_files(tmp_path: Path) -> None:
    paths = SystemPaths(tmp_path)
    simulator = MT4Simulator(paths)
    instance = _instance()
    exported = simulator.export_tick(instance)
    assert exported.market_path.exists()
    assert exported.sensor_path.exists()
    assert exported.status_path.exists()
    assert exported.universe_path.exists()
    assert 'EURUSD' in exported.market_path.read_text(encoding='utf-8')

def test_mt4_simulator_read_control_returns_none_when_missing(tmp_path: Path) -> None:
    simulator = MT4Simulator(SystemPaths(tmp_path))
    assert simulator.read_control(_instance()) is None

def test_mt4_simulator_fulfill_control_writes_ack_matching_command(tmp_path: Path) -> None:
    paths = SystemPaths(tmp_path)
    simulator = MT4Simulator(paths)
    instance = _instance()
    simulator.export_tick(instance)
    from engine.execution.command import OrderCommand
    from engine.execution.control_writer import publish_control
    from engine.protocol.constants import Side
    publish_control(paths, instance, OrderCommand(command_id='cmd-sim-1', action=OrderAction.OPEN.value, reason='BUY: test', decision_id='decision-sim-1', side=Side.BUY.value, volume=0.1, stop_loss=1.09, take_profit=1.12), timestamp_utc='2026-07-07T06:03:00.000Z')
    ack_record = simulator.fulfill_control(instance, ticket=4321)
    assert ack_record is not None
    assert ack_record.command_id == 'cmd-sim-1'
    assert ack_record.ticket == 4321
    assert simulator.read_control(instance) is not None
    assert build_ack_path(paths, instance).exists()

def test_full_cycle_steps_8_to_60_with_simulator(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths = SystemPaths(tmp_path)
    simulator = MT4Simulator(paths)
    instance = _instance()
    result = _run_simulated_full_cycle(tmp_path, instance, simulator, monkeypatch)
    _assert_phase_outcomes(result, paths, instance, expect_trade=True)
    assert result.decision_result is not None
    assert result.decision_result.buy_candidate is not None
    assert result.decision_result.sell_candidate is not None
    assert result.performance_timings is not None
    assert result.performance_timings.load_duration_ms >= 0

def test_e2e_buy_scenario(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths = SystemPaths(tmp_path)
    simulator = MT4Simulator(paths)
    instance = _instance()
    result = _run_simulated_full_cycle(tmp_path, instance, simulator, monkeypatch, market_scenario='bullish')
    assert result.decision_result is not None
    assert result.decision_result.decision == Decision.BUY.value
    _assert_phase_outcomes(result, paths, instance, expect_trade=True)

def test_e2e_sell_scenario(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths = SystemPaths(tmp_path)
    simulator = MT4Simulator(paths)
    instance = _instance()
    result = _run_simulated_full_cycle(tmp_path, instance, simulator, monkeypatch, market_scenario='bearish')
    assert result.decision_result is not None
    assert result.decision_result.decision == Decision.SELL.value
    _assert_phase_outcomes(result, paths, instance, expect_trade=True)

def test_e2e_wait_scenario(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths = SystemPaths(tmp_path)
    simulator = MT4Simulator(paths)
    instance = _instance()
    result = _run_simulated_full_cycle(tmp_path, instance, simulator, monkeypatch, market_scenario='flat', analysis_overrides={'weights': {'momentum': 0.0, 'trend': 0.0, 'structure': 0.0, 'pressure': 0.0, 'behavior': 0.0, 'impact': 0.0, 'context': 1.0}})
    assert result.decision_result is not None
    assert result.decision_result.decision == Decision.WAIT.value
    assert REASON_EQUAL_SCORES in result.decision_result.reason
    _assert_phase_outcomes(result, paths, instance, expect_trade=False)

def test_e2e_block_scenario(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths = SystemPaths(tmp_path)
    simulator = MT4Simulator(paths)
    instance = _instance()
    result = _run_simulated_full_cycle(tmp_path, instance, simulator, monkeypatch, status_scenario='not_tradeable')
    assert result.decision_result is not None
    assert result.decision_result.decision == Decision.BLOCK.value
    assert REASON_ACCOUNT_NOT_TRADEABLE in result.decision_result.reason
    _assert_phase_outcomes(result, paths, instance, expect_trade=False)

def test_multi_instance_e2e(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_fixed_command_id(monkeypatch)
    instance_a = _instance(account_id='12345', symbol='EURUSD', magic=100001)
    instance_b = _instance(account_id='12345', symbol='GBPUSD', magic=100002)
    runtime = _startup_runtime(tmp_path, instances=[{'account_id': '12345', 'symbol': 'EURUSD', 'magic': 100001, 'enabled': True}, {'account_id': '12345', 'symbol': 'GBPUSD', 'magic': 100002, 'enabled': True}])
    simulator = MT4Simulator(runtime.paths)
    simulator.export_tick(instance_a, market_scenario='bullish')
    simulator.export_tick(instance_b, market_scenario='bearish')
    simulator.install_auto_ack_hook(monkeypatch)
    orchestrator_result = run_runtime_cycles(runtime, instances=(instance_a, instance_b), use_global_universe=False, timestamp_utc='2026-07-07T06:02:00.000Z')
    assert orchestrator_result.instance_count == 2
    assert orchestrator_result.completed_count == 2
    assert orchestrator_result.failed_count == 0
    results_by_key = {item.instance.instance_key: item for item in orchestrator_result.instance_results}
    result_a = results_by_key[instance_a.instance_key]
    result_b = results_by_key[instance_b.instance_key]
    assert result_a.decision_result is not None
    assert result_b.decision_result is not None
    assert result_a.decision_result.decision == Decision.BUY.value
    assert result_b.decision_result.decision == Decision.SELL.value
    _assert_phase_outcomes(result_a, runtime.paths, instance_a, expect_trade=True)
    _assert_phase_outcomes(result_b, runtime.paths, instance_b, expect_trade=True)
    journal_a = build_decision_journal_path(runtime.paths, instance_a)
    journal_b = build_decision_journal_path(runtime.paths, instance_b)
    assert journal_a.exists()
    assert journal_b.exists()
    assert journal_a != journal_b

def test_e2e_full_cycle_journal_includes_ai_metadata(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    instance = _instance()
    simulator = MT4Simulator(SystemPaths(tmp_path))
    result = _run_simulated_full_cycle(tmp_path, instance, simulator, monkeypatch)
    paths = SystemPaths(tmp_path)
    decision_path = build_decision_journal_path(paths, instance)
    payload = json.loads(decision_path.read_text(encoding='utf-8').strip())
    assert payload['ai_mode'] == 'advisory'
    assert payload['ai_available'] is True
    assert result.decision_result is not None
    assert payload['decision'] == result.decision_result.decision
    assert payload['system_decision_before_ai'] in {Decision.BUY.value, Decision.SELL.value, Decision.WAIT.value, Decision.BLOCK.value}
