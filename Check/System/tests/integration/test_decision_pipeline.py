from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, MutableMapping
import pytest
from engine.core.instance import Instance
from engine.core.lifecycle import LiveRuntime
from engine.core.paths import SystemPaths
from engine.core.cycle import run_instance_ai_risk_pipeline, run_instance_decision_phase, validate_status_for_cycle
from engine.decision.engine import DecisionResult
from engine.journal.decision_journal import build_decision_journal_path, log_decision
from engine.protocol.constants import REASON_EQUAL_SCORES, REASON_RISK_MAX_POSITIONS, Decision, RiskResult
from engine.protocol.models import StatusRecord
from engine.protocol.writer import DECISION_JOURNAL_REQUIRED_FIELDS
from engine.risk.engine import RiskEngineResult, RiskEngineTradeParams
from engine.state.instance_state import InstanceState
from tests.core.config_payload import valid_system_config_payload
from tests.integration.test_data_pipeline import FIXTURES_DIR, _install_integration_fixtures, _instance, run_instance_data_pipeline
from tests.protocol.test_writer import required_fields_present
MODULE_NAME = 'integration.decision_pipeline'

@dataclass(frozen=True)
class DecisionPipelineResult:
    completed: bool
    error_logged: bool
    decision_result: DecisionResult | None = None
    risk_engine_result: RiskEngineResult | None = None
    decision_journal_logged: bool = False

def _write_config(root: Path, *, analysis_overrides: dict[str, Any] | None=None) -> Path:
    payload = valid_system_config_payload()
    payload['system']['root_path'] = str(root)
    analysis = {**payload['analysis'], 'lookback_bars': 3, 'structure_lookback_bars': 3}
    if analysis_overrides is not None:
        analysis = {**analysis, **analysis_overrides}
    payload['analysis'] = analysis
    config_dir = root / 'config'
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / 'system.json'
    config_path.write_text(json.dumps(payload), encoding='utf-8')
    return config_path

def _startup_runtime(tmp_path: Path, *, analysis_overrides: dict[str, Any] | None=None) -> tuple[LiveRuntime, Instance]:
    from engine.core.lifecycle import startup
    config_path = _write_config(tmp_path, analysis_overrides=analysis_overrides)
    instance = _instance()
    _install_integration_fixtures(SystemPaths(tmp_path), instance)
    runtime = startup(root_path=tmp_path, config_path=config_path)
    return (runtime, instance)

def run_instance_decision_pipeline(runtime: LiveRuntime, instance: Instance, *, use_global_universe: bool | None=None, timestamp_utc: str='2026-07-07T06:02:00.000Z', trade_params: RiskEngineTradeParams | None=None, cache: MutableMapping[str, Any] | None=None) -> DecisionPipelineResult:
    data_result = run_instance_data_pipeline(runtime, instance, use_global_universe=use_global_universe, timestamp_utc=timestamp_utc, cache=cache)
    if not data_result.completed or data_result.loaded is None:
        return DecisionPipelineResult(completed=False, error_logged=data_result.error_logged)
    if data_result.market_bars is None or data_result.sensor_reading is None or data_result.universe is None or (data_result.spread_snapshot is None):
        return DecisionPipelineResult(completed=False, error_logged=True)
    status_result = validate_status_for_cycle(data_result.loaded.status_raw)
    if not status_result.is_valid or status_result.record is None:
        return DecisionPipelineResult(completed=False, error_logged=True)
    status = status_result.record
    instance_memory = runtime.memory.get_or_create(instance)
    decision_result = run_instance_decision_phase(universe=data_result.universe, market_bars=data_result.market_bars, instance_memory=instance_memory, relative_spread=data_result.spread_snapshot.relative_spread, runtime=runtime)
    decision_result, risk_engine_result, ai_meta, _ai_query = run_instance_ai_risk_pipeline(decision_result=decision_result, instance_memory=instance_memory, status=status, market_bars=data_result.market_bars, runtime=runtime, spread_snapshot=data_result.spread_snapshot, trade_params=trade_params)
    log_decision(runtime.paths, instance, decision_result, risk_engine_result, timestamp_utc=timestamp_utc, ai_meta=ai_meta)
    return DecisionPipelineResult(completed=True, error_logged=False, decision_result=decision_result, risk_engine_result=risk_engine_result, decision_journal_logged=True)

def _parse_journal_lines(tmp_path: Path, instance: Instance) -> list[dict[str, Any]]:
    journal_path = build_decision_journal_path(SystemPaths(tmp_path), instance)
    lines = journal_path.read_text(encoding='utf-8').splitlines()
    return [json.loads(line) for line in lines if line.strip()]

def test_buy_and_sell_candidates_are_calculated(tmp_path: Path) -> None:
    runtime, instance = _startup_runtime(tmp_path)
    result = run_instance_decision_pipeline(runtime, instance, use_global_universe=False)
    assert result.completed
    assert result.decision_result is not None
    assert result.decision_result.buy_candidate is not None
    assert result.decision_result.sell_candidate is not None
    assert result.decision_result.buy_score >= 0.0
    assert result.decision_result.sell_score >= 0.0
    assert result.decision_result.decision in {Decision.BUY.value, Decision.SELL.value, Decision.WAIT.value}

def test_wait_decision_includes_reason(tmp_path: Path) -> None:
    equal_score_weights = {'momentum': 0.0, 'trend': 0.0, 'structure': 0.0, 'pressure': 0.0, 'behavior': 0.0, 'impact': 0.0, 'context': 1.0}
    runtime, instance = _startup_runtime(tmp_path, analysis_overrides={'weights': equal_score_weights})
    result = run_instance_decision_pipeline(runtime, instance, use_global_universe=False)
    assert result.completed
    assert result.decision_result is not None
    assert result.decision_result.decision == Decision.WAIT.value
    assert result.decision_result.reason
    assert REASON_EQUAL_SCORES in result.decision_result.reason
    assert result.decision_result.buy_candidate.valid
    assert result.decision_result.sell_candidate.valid
    assert result.decision_result.buy_score == result.decision_result.sell_score

def test_risk_block_includes_risk_reason(tmp_path: Path) -> None:
    runtime, instance = _startup_runtime(tmp_path)
    memory = runtime.memory.get_or_create(instance)
    data_result = run_instance_data_pipeline(runtime, instance, use_global_universe=False)
    assert data_result.completed
    memory.instance_state.update_position(open_ticket=1001, position_side='BUY', position_volume=0.1)
    memory.instance_state.save(runtime.paths)
    result = run_instance_decision_pipeline(runtime, instance, use_global_universe=False, timestamp_utc='2026-07-07T06:03:00.000Z')
    assert result.completed
    assert result.decision_result is not None
    assert result.risk_engine_result is not None
    assert result.decision_result.decision == Decision.BLOCK.value
    assert result.risk_engine_result.result == RiskResult.BLOCK.value
    assert REASON_RISK_MAX_POSITIONS in result.risk_engine_result.reason
    journal_path = build_decision_journal_path(runtime.paths, instance)
    last_line = journal_path.read_text(encoding='utf-8').strip().splitlines()[-1]
    entry = json.loads(last_line)
    assert entry['risk_result'] == RiskResult.BLOCK.value
    assert entry['risk_reason'] is not None
    assert REASON_RISK_MAX_POSITIONS in entry['risk_reason']

def test_decision_journal_contains_all_decisions(tmp_path: Path) -> None:
    runtime, instance = _startup_runtime(tmp_path)
    first = run_instance_decision_pipeline(runtime, instance, use_global_universe=False, timestamp_utc='2026-07-07T06:02:00.000Z')
    assert first.completed
    assert first.decision_result is not None
    assert first.decision_result.buy_candidate is not None
    assert first.decision_result.sell_candidate is not None
    equal_score_runtime, equal_instance = _startup_runtime(tmp_path / 'equal_scores', analysis_overrides={'weights': {'momentum': 0.0, 'trend': 0.0, 'structure': 0.0, 'pressure': 0.0, 'behavior': 0.0, 'impact': 0.0, 'context': 1.0}})
    second = run_instance_decision_pipeline(equal_score_runtime, equal_instance, use_global_universe=False, timestamp_utc='2026-07-07T06:02:00.000Z')
    assert second.completed
    assert second.decision_result is not None
    assert second.decision_result.decision == Decision.WAIT.value
    risk_runtime, risk_instance = _startup_runtime(tmp_path / 'risk_block')
    risk_memory = risk_runtime.memory.get_or_create(risk_instance)
    assert run_instance_data_pipeline(risk_runtime, risk_instance, use_global_universe=False).completed
    risk_memory.instance_state.update_position(open_ticket=1001, position_side='BUY', position_volume=0.1)
    risk_memory.instance_state.save(risk_runtime.paths)
    third = run_instance_decision_pipeline(risk_runtime, risk_instance, use_global_universe=False, timestamp_utc='2026-07-07T06:03:00.000Z')
    assert third.completed
    assert third.risk_engine_result is not None
    assert third.risk_engine_result.result == RiskResult.BLOCK.value
    journals = {'directional': _parse_journal_lines(tmp_path, instance), 'wait': _parse_journal_lines(tmp_path / 'equal_scores', equal_instance), 'risk_block': _parse_journal_lines(tmp_path / 'risk_block', risk_instance)}
    assert len(journals['directional']) == 1
    assert len(journals['wait']) == 1
    assert len(journals['risk_block']) == 1
    directional_entry = journals['directional'][0]
    wait_entry = journals['wait'][0]
    risk_entry = journals['risk_block'][0]
    for entry in (directional_entry, wait_entry, risk_entry):
        assert required_fields_present(entry, DECISION_JOURNAL_REQUIRED_FIELDS)
        assert entry['buy_score'] >= 0.0
        assert entry['sell_score'] >= 0.0
    assert directional_entry['decision'] in {Decision.BUY.value, Decision.SELL.value, Decision.WAIT.value}
    assert wait_entry['decision'] == Decision.WAIT.value
    assert wait_entry['reason']
    assert REASON_EQUAL_SCORES in wait_entry['reason']
    assert risk_entry['decision'] == Decision.BLOCK.value
    assert risk_entry['risk_result'] == RiskResult.BLOCK.value
    assert risk_entry['risk_reason']
    assert REASON_RISK_MAX_POSITIONS in risk_entry['risk_reason']
