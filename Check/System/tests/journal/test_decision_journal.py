from __future__ import annotations
import json
from datetime import datetime, timezone
import pytest
from engine.core.config import parse_config_payload
from engine.core.instance import Instance
from engine.core.paths import SystemPaths
from engine.decision.buy import BuyCandidate
from engine.decision.engine import DecisionResult, run_decision_engine
from engine.decision.sell import SellCandidate
from engine.journal.decision_journal import append_decision_journal_entry, build_decision_journal_entry, build_decision_journal_path, log_decision
from engine.normalizer.market_normalizer import NormalizedMarketBar
from engine.protocol.constants import Decision, RiskResult, Side
from engine.protocol.models import UniverseRecord
from engine.protocol.parser import parse_decision_journal_line
from engine.protocol.writer import DECISION_JOURNAL_REQUIRED_FIELDS, write_decision_journal_entry
from engine.protocol.models import RiskConfig, StatusRecord
from engine.risk.engine import RiskEngineResult, RiskEngineTradeParams, run_risk_engine
from engine.state.instance_state import InstanceState
from tests.core.config_payload import valid_system_config_payload
from tests.protocol.test_writer import required_fields_present

def _system_config():
    payload = valid_system_config_payload()
    payload['analysis'] = {**payload['analysis'], 'lookback_bars': 3, 'structure_lookback_bars': 3}
    return parse_config_payload(payload)

def _bar(index: int, open_: float, high: float, low: float, close: float) -> NormalizedMarketBar:
    return NormalizedMarketBar(time_utc=datetime(2026, 7, 7, 6, index, tzinfo=timezone.utc), open=open_, high=high, low=low, close=close, volume=100.0, symbol='EURUSD', timeframe='M1', digits=5, point=1e-05, bar_index=index)

def _bullish_bars() -> tuple[NormalizedMarketBar, ...]:
    return (_bar(0, 1.1, 1.102, 1.099, 1.1015), _bar(1, 1.1015, 1.103, 1.1005, 1.1022), _bar(2, 1.1022, 1.104, 1.101, 1.1031))

def _universe() -> UniverseRecord:
    return UniverseRecord(schema_version='1.0.0', timestamp_utc='2026-07-07T06:00:00.000Z', session='LONDON', market_regime='trending', news_window_active=False)

def _instance_state() -> InstanceState:
    state = InstanceState(instance=Instance(account_id='12345', symbol='EURUSD', magic=100001))
    state.update_instrument(digits=5, point=1e-05, pip=0.0001)
    return state

def _manual_decision_result() -> DecisionResult:
    return DecisionResult(decision_id='decision-123', decision=Decision.BUY.value, reason='BUY: preferred side selected after scoring (buy_score=0.8, sell_score=0.3)', preferred_side=Side.BUY.value, buy_candidate=BuyCandidate(valid=True, invalid_reason=None, entry_price=1.1031, stop_loss=1.0988, take_profit=1.1117, component_scores={}, buy_score=0.8), sell_candidate=SellCandidate(valid=False, invalid_reason='sell invalid', entry_price=0.0, stop_loss=0.0, take_profit=0.0, component_scores={}, sell_score=0.3), buy_score=0.8, sell_score=0.3, analysis_context=run_decision_engine(universe=_universe(), market_bars=_bullish_bars(), instance_state=_instance_state(), relative_spread=1.0, system_config=_system_config()).analysis_context)

def _allow_risk_result() -> RiskEngineResult:
    return RiskEngineResult(result=RiskResult.ALLOW.value, reason='', position_size=0.1, stop_loss=1.0988, take_profit=1.1117)

def _block_risk_result() -> RiskEngineResult:
    return RiskEngineResult(result=RiskResult.BLOCK.value, reason='RISK_MAX_POSITIONS: open position limit reached', position_size=None, stop_loss=None, take_profit=None)

def test_build_decision_journal_path_uses_instance_filename(tmp_path) -> None:
    paths = SystemPaths(root_path=tmp_path)
    instance = Instance(account_id='12345', symbol='EURUSD', magic=100001)
    journal_path = build_decision_journal_path(paths, instance)
    assert journal_path.name == 'decision_EURUSD_100001.jsonl'
    assert journal_path.parent.name == 'journal'

def test_build_decision_journal_entry_maps_decision_and_risk_fields() -> None:
    instance = Instance(account_id='12345', symbol='EURUSD', magic=100001)
    decision_result = _manual_decision_result()
    risk_engine_result = _allow_risk_result()
    entry = build_decision_journal_entry(instance, decision_result, risk_engine_result, timestamp_utc='2026-07-07T06:00:00.000Z')
    assert entry.decision_id == decision_result.decision_id
    assert entry.timestamp_utc == '2026-07-07T06:00:00.000Z'
    assert entry.account_id == '12345'
    assert entry.symbol == 'EURUSD'
    assert entry.magic == 100001
    assert entry.decision == Decision.BUY.value
    assert entry.reason == decision_result.reason
    assert entry.buy_score == pytest.approx(0.8)
    assert entry.sell_score == pytest.approx(0.3)
    assert entry.risk_result == RiskResult.ALLOW.value
    assert entry.risk_reason is None

def test_build_decision_journal_entry_includes_risk_reason_on_block() -> None:
    instance = Instance(account_id='12345', symbol='EURUSD', magic=100001)
    decision_result = _manual_decision_result()
    entry = build_decision_journal_entry(instance, decision_result, _block_risk_result(), timestamp_utc='2026-07-07T06:00:00.000Z')
    assert entry.risk_result == RiskResult.BLOCK.value
    assert entry.risk_reason == 'RISK_MAX_POSITIONS: open position limit reached'

def test_decision_journal_entry_contains_all_section_19_8_fields() -> None:
    instance = Instance(account_id='12345', symbol='EURUSD', magic=100001)
    entry = build_decision_journal_entry(instance, _manual_decision_result(), _allow_risk_result(), timestamp_utc='2026-07-07T06:00:00.000Z')
    data = json.loads(write_decision_journal_entry(entry))
    assert required_fields_present(data, DECISION_JOURNAL_REQUIRED_FIELDS)
    assert data['buy_score'] == pytest.approx(0.8)
    assert data['sell_score'] == pytest.approx(0.3)
    assert 'risk_reason' not in data

def test_append_decision_journal_entry_is_append_only(tmp_path) -> None:
    paths = SystemPaths(root_path=tmp_path)
    instance = Instance(account_id='12345', symbol='EURUSD', magic=100001)
    first = build_decision_journal_entry(instance, _manual_decision_result(), _allow_risk_result(), timestamp_utc='2026-07-07T06:00:00.000Z')
    base_decision = _manual_decision_result()
    second = build_decision_journal_entry(instance, DecisionResult(decision_id='decision-456', decision=Decision.WAIT.value, reason='WAIT: equal scores', preferred_side=Side.NONE.value, buy_candidate=base_decision.buy_candidate, sell_candidate=base_decision.sell_candidate, buy_score=0.5, sell_score=0.5, analysis_context=base_decision.analysis_context), _block_risk_result(), timestamp_utc='2026-07-07T06:01:00.000Z')
    append_decision_journal_entry(paths, instance, first)
    append_decision_journal_entry(paths, instance, second)
    journal_text = build_decision_journal_path(paths, instance).read_text(encoding='utf-8')
    lines = [line for line in journal_text.splitlines() if line.strip()]
    assert len(lines) == 2
    assert parse_decision_journal_line(lines[0]).decision_id == 'decision-123'
    assert parse_decision_journal_line(lines[1]).decision_id == 'decision-456'

def test_decision_journal_is_isolated_by_instance(tmp_path) -> None:
    paths = SystemPaths(root_path=tmp_path)
    instance_a = Instance(account_id='12345', symbol='EURUSD', magic=100001)
    instance_b = Instance(account_id='12345', symbol='GBPUSD', magic=100002)
    log_decision(paths, instance_a, _manual_decision_result(), _allow_risk_result(), timestamp_utc='2026-07-07T06:00:00.000Z')
    log_decision(paths, instance_b, DecisionResult(decision_id='decision-789', decision=Decision.SELL.value, reason='SELL: preferred side selected', preferred_side=Side.SELL.value, buy_candidate=_manual_decision_result().buy_candidate, sell_candidate=_manual_decision_result().sell_candidate, buy_score=0.2, sell_score=0.9, analysis_context=_manual_decision_result().analysis_context), _block_risk_result(), timestamp_utc='2026-07-07T06:02:00.000Z')
    path_a = build_decision_journal_path(paths, instance_a)
    path_b = build_decision_journal_path(paths, instance_b)
    assert path_a.exists()
    assert path_b.exists()
    assert path_a != path_b
    assert parse_decision_journal_line(path_a.read_text(encoding='utf-8').strip()).symbol == 'EURUSD'
    assert parse_decision_journal_line(path_b.read_text(encoding='utf-8').strip()).symbol == 'GBPUSD'

def test_log_decision_writes_entry_for_decision_engine_result(tmp_path) -> None:
    paths = SystemPaths(root_path=tmp_path)
    instance = Instance(account_id='12345', symbol='EURUSD', magic=100001)
    instance_state = _instance_state()
    system_config = _system_config()
    decision_result = run_decision_engine(universe=_universe(), market_bars=_bullish_bars(), instance_state=instance_state, relative_spread=1.0, system_config=system_config)
    risk_engine_result = run_risk_engine(decision_result=decision_result, risk_config=RiskConfig(max_open_positions_per_instance=1, max_daily_loss_percent=2.0, max_drawdown_percent=10.0, daily_loss_limit_enabled=True, drawdown_limit_enabled=True, reward_ratio=2.0, max_risk_per_trade_percent=1.0, max_stop_loss_pips=100.0, volume_step=0.01, fixed_lot_volume=0.0), instance_state=instance_state, status=StatusRecord(schema_version='1.0.0', timestamp_utc='2026-07-07T06:00:00.000Z', account_id='12345', connected=True, trade_allowed=True, balance=10000.0, equity=10000.0, margin_free=9000.0, ea_version='1.0.0'), trade_params=RiskEngineTradeParams(max_risk_per_trade_percent=1.0, volume_step=0.01, max_stop_loss_pips=100.0), swing_low=1.099, swing_high=1.104)
    entry = log_decision(paths, instance, decision_result, risk_engine_result, timestamp_utc='2026-07-07T06:00:00.000Z')
    assert entry.decision_id == decision_result.decision_id
    assert entry.decision == decision_result.decision
    assert entry.risk_result == risk_engine_result.result
    journal_line = build_decision_journal_path(paths, instance).read_text(encoding='utf-8').strip()
    restored = parse_decision_journal_line(journal_line)
    assert restored.decision_id == decision_result.decision_id
    assert restored.buy_score == pytest.approx(decision_result.buy_score)
    assert restored.sell_score == pytest.approx(decision_result.sell_score)

def test_log_decision_has_no_silent_exception_on_invalid_risk_result(tmp_path) -> None:
    paths = SystemPaths(root_path=tmp_path)
    instance = Instance(account_id='12345', symbol='EURUSD', magic=100001)
    invalid_risk = RiskEngineResult(result='INVALID', reason='invalid', position_size=None, stop_loss=None, take_profit=None)
    with pytest.raises(Exception):
        log_decision(paths, instance, _manual_decision_result(), invalid_risk, timestamp_utc='2026-07-07T06:00:00.000Z')
