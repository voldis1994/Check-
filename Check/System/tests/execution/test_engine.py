from __future__ import annotations
from datetime import datetime, timezone
from unittest.mock import MagicMock
import pytest
from engine.core.atomic_io import atomic_write_text
from engine.core.config import parse_config_payload
from engine.core.instance import Instance
from engine.core.paths import SystemPaths
from engine.decision.buy import BuyCandidate
from engine.decision.engine import DecisionResult, run_decision_engine
from engine.decision.sell import SellCandidate
from engine.execution.ack_reader import build_ack_path
from engine.execution.command import OrderCommand
from engine.core.history import read_archived_control_text
from engine.execution.control_writer import build_control_path
from engine.execution.engine import ExecutionResult, apply_ack_to_instance_state, build_trade_intent_params, execution_engine_performs_analysis, log_ack_failure, resolve_entry_price_for_open, run_execution_engine, wait_for_ack
from engine.risk.trade_management import TradeManagementResult
from engine.journal.error_journal import build_error_journal_path
from engine.journal.trade_journal import INTENT_REASON_PREFIX, build_trade_journal_path
from engine.normalizer.market_normalizer import NormalizedMarketBar
from engine.protocol.constants import AckStatus, Decision, ErrorType, OrderAction, PROTOCOL_SCHEMA_VERSION, REASON_ACK_TIMEOUT, RiskResult, Side, TradeEvent
from engine.protocol.models import RiskConfig, RuntimeConfig, StatusRecord, UniverseRecord
from engine.protocol.parser import parse_control, parse_error_journal_line, parse_trade_journal_line
from engine.risk.engine import RiskEngineResult, run_risk_engine
from engine.state.instance_state import InstanceState
from tests.core.config_payload import valid_system_config_payload
FIXED_COMMAND_ID = 'cmd-exec-integration-1'

def _bar(index: int, open_: float, high: float, low: float, close: float) -> NormalizedMarketBar:
    return NormalizedMarketBar(time_utc=datetime(2026, 7, 7, 6, index, tzinfo=timezone.utc), open=open_, high=high, low=low, close=close, volume=100.0, symbol='EURUSD', timeframe='M1', digits=5, point=1e-05, bar_index=index)

def _bullish_bars() -> tuple[NormalizedMarketBar, ...]:
    return (_bar(0, 1.1, 1.102, 1.099, 1.1015), _bar(1, 1.1015, 1.103, 1.1005, 1.1022), _bar(2, 1.1022, 1.104, 1.101, 1.1031))

def _universe() -> UniverseRecord:
    return UniverseRecord(schema_version='1.0.0', timestamp_utc='2026-07-07T06:00:00.000Z', session='LONDON', market_regime='trending', news_window_active=False)

def _instance() -> Instance:
    return Instance(account_id='12345', symbol='EURUSD', magic=100001)

def _instance_state() -> InstanceState:
    state = InstanceState(instance=_instance())
    state.update_instrument(digits=5, point=1e-05, pip=0.0001)
    return state

def _system_config():
    payload = valid_system_config_payload()
    payload['analysis'] = {**payload['analysis'], 'lookback_bars': 3}
    return parse_config_payload(payload)

def _runtime_config(*, ack_timeout_ms: int=5000) -> RuntimeConfig:
    return RuntimeConfig(cycle_interval_ms=1000, ack_timeout_ms=ack_timeout_ms, retry_max=3, retry_delay_ms=200, data_stale_threshold_ms=15000, cycle_max_duration_ms=30000, metrics_interval_ms=60000, auto_discover_instances=True)

def _buy_decision_result() -> DecisionResult:
    engine_result = run_decision_engine(universe=_universe(), market_bars=_bullish_bars(), instance_state=_instance_state(), relative_spread=1.0, system_config=_system_config())
    return DecisionResult(decision_id='decision-123', decision=Decision.BUY.value, reason='BUY: preferred side selected', preferred_side=Side.BUY.value, buy_candidate=BuyCandidate(valid=True, invalid_reason=None, entry_price=1.1031, stop_loss=1.0988, take_profit=1.1117, component_scores={}, buy_score=0.8), sell_candidate=SellCandidate(valid=False, invalid_reason='sell invalid', entry_price=0.0, stop_loss=0.0, take_profit=0.0, component_scores={}, sell_score=0.3), buy_score=0.8, sell_score=0.3, analysis_context=engine_result.analysis_context)

def _wait_decision_result() -> DecisionResult:
    engine_result = run_decision_engine(universe=_universe(), market_bars=_bullish_bars(), instance_state=_instance_state(), relative_spread=1.0, system_config=_system_config())
    return DecisionResult(decision_id='decision-wait', decision=Decision.WAIT.value, reason='WAIT: equal scores', preferred_side=Side.NONE.value, buy_candidate=engine_result.buy_candidate, sell_candidate=engine_result.sell_candidate, buy_score=engine_result.buy_score, sell_score=engine_result.sell_score, analysis_context=engine_result.analysis_context)

def _allow_risk_result() -> RiskEngineResult:
    return RiskEngineResult(result=RiskResult.ALLOW.value, reason='', position_size=0.1, stop_loss=1.0988, take_profit=1.1117)

def _ack_payload(*, status: str, command_id: str=FIXED_COMMAND_ID, ticket: int | None=555, error_code: int | None=None, error_message: str | None=None) -> str:
    ticket_field = f',\n  "ticket": {ticket}' if ticket is not None else ''
    error_fields = ''
    if error_code is not None:
        error_fields += f',\n  "error_code": {error_code}'
    if error_message is not None:
        error_fields += f',\n  "error_message": "{error_message}"'
    return f'{{\n  "schema_version": "{PROTOCOL_SCHEMA_VERSION}",\n  "timestamp_utc": "2026-07-07T06:00:00.000Z",\n  "command_id": "{command_id}",\n  "account_id": "12345",\n  "symbol": "EURUSD",\n  "magic": 100001,\n  "status": "{status}"{ticket_field}{error_fields}\n}}'

def _write_ack(paths: SystemPaths, instance: Instance, payload: str) -> None:
    paths.ensure_account_directories(instance.account_id)
    atomic_write_text(build_ack_path(paths, instance), payload)

def _open_order_command() -> OrderCommand:
    return OrderCommand(command_id=FIXED_COMMAND_ID, action=OrderAction.OPEN.value, reason='BUY: preferred side selected', decision_id='decision-123', side=Side.BUY.value, volume=0.1, stop_loss=1.0988, take_profit=1.1117)

def _patch_fixed_command_id(monkeypatch: pytest.MonkeyPatch) -> None:
    counter = {'value': 0}

    def _uuid4() -> str:
        counter['value'] += 1
        return FIXED_COMMAND_ID if counter['value'] == 1 else f'cmd-exec-{counter['value']}'
    monkeypatch.setattr('engine.execution.command.uuid4', _uuid4)

def test_build_trade_intent_params_maps_order_command_fields() -> None:
    order_command = _open_order_command()
    params = build_trade_intent_params(order_command)
    assert params.command_id == order_command.command_id
    assert params.event == TradeEvent.OPEN.value
    assert params.reason == order_command.reason
    assert params.side == Side.BUY.value
    assert params.volume == pytest.approx(0.1)
    assert params.ticket is None

def test_wait_for_ack_returns_true_when_ack_available_before_timeout() -> None:
    available = {'value': False}

    def _ack_available() -> bool:
        available['value'] = True
        return True
    result = wait_for_ack(started_monotonic=100.0, ack_timeout_ms=5000, ack_available=_ack_available, monotonic_fn=lambda: 100.1, sleep_fn=lambda _: None)
    assert result is True
    assert available['value'] is True

def test_wait_for_ack_returns_false_when_timeout_elapses_without_ack() -> None:
    result = wait_for_ack(started_monotonic=0.0, ack_timeout_ms=100, ack_available=lambda: False, monotonic_fn=lambda: 1.0, sleep_fn=lambda _: None)
    assert result is False

def test_wait_for_ack_polls_until_ack_becomes_available() -> None:
    polls = {'count': 0}

    def _ack_available() -> bool:
        polls['count'] += 1
        return polls['count'] >= 3
    result = wait_for_ack(started_monotonic=100.0, ack_timeout_ms=5000, ack_available=_ack_available, monotonic_fn=lambda: 100.0 + polls['count'] * 0.01, sleep_fn=lambda _: None, poll_interval_ms=10)
    assert result is True
    assert polls['count'] == 3

def test_apply_ack_to_instance_state_updates_execution_and_position_on_success_open() -> None:
    state = _instance_state()
    order_command = _open_order_command()
    ack_record = MagicMock(command_id=FIXED_COMMAND_ID, status=AckStatus.SUCCESS.value, ticket=555)
    apply_ack_to_instance_state(state, order_command, ack_record, entry_price=1.1031)
    assert state.last_command_id == FIXED_COMMAND_ID
    assert state.last_ack_status == AckStatus.SUCCESS.value
    assert state.open_ticket == 555
    assert state.position_side == Side.BUY.value
    assert state.position_volume == pytest.approx(0.1)
    assert state.position_entry_price == pytest.approx(1.1031)
    assert state.position_stop_loss == pytest.approx(1.0988)
    assert state.position_take_profit == pytest.approx(1.1117)

def test_apply_ack_to_instance_state_updates_position_levels_on_success_modify() -> None:
    state = _instance_state()
    state.update_position(open_ticket=555, position_side=Side.BUY.value, position_volume=0.1, entry_price=1.1031, stop_loss=1.0988, take_profit=1.1117)
    order_command = OrderCommand(command_id='cmd-modify-1', action=OrderAction.MODIFY.value, reason='TRADE_MANAGEMENT_BREAKEVEN: stop loss moved to entry', decision_id='decision-123', side=Side.BUY.value, stop_loss=1.1031, take_profit=1.1117, ticket=555)
    ack_record = MagicMock(command_id='cmd-modify-1', status=AckStatus.SUCCESS.value, ticket=555)
    apply_ack_to_instance_state(state, order_command, ack_record)
    assert state.position_stop_loss == pytest.approx(1.1031)
    assert state.position_take_profit == pytest.approx(1.1117)
    assert state.open_ticket == 555

def test_apply_ack_to_instance_state_clears_position_on_success_close() -> None:
    state = _instance_state()
    state.update_position(open_ticket=555, position_side=Side.BUY.value, position_volume=0.1, entry_price=1.1031, stop_loss=1.0988, take_profit=1.1117)
    order_command = OrderCommand(command_id='cmd-close-1', action=OrderAction.CLOSE.value, reason='TRADE_MANAGEMENT_TIME_STOP: maximum bars in trade reached', decision_id='decision-123', side=Side.BUY.value, volume=0.1, ticket=555)
    ack_record = MagicMock(command_id='cmd-close-1', status=AckStatus.SUCCESS.value, ticket=555)
    apply_ack_to_instance_state(state, order_command, ack_record)
    assert state.open_ticket is None
    assert state.position_side is None
    assert state.position_volume is None
    assert state.position_entry_price is None

def test_apply_ack_to_instance_state_reduces_volume_on_partial_close() -> None:
    state = _instance_state()
    state.update_position(open_ticket=555, position_side=Side.BUY.value, position_volume=0.1, entry_price=1.1031, stop_loss=1.0988, take_profit=1.1117)
    order_command = OrderCommand(command_id='cmd-close-partial', action=OrderAction.CLOSE.value, reason='TRADE_MANAGEMENT_PARTIAL_CLOSE: partial volume close triggered', decision_id='decision-123', side=Side.BUY.value, volume=0.05, ticket=555)
    ack_record = MagicMock(command_id='cmd-close-partial', status=AckStatus.SUCCESS.value, ticket=555)
    apply_ack_to_instance_state(state, order_command, ack_record)
    assert state.open_ticket == 555
    assert state.position_volume == pytest.approx(0.05)

def test_resolve_entry_price_for_open_uses_buy_candidate() -> None:
    entry_price = resolve_entry_price_for_open(_buy_decision_result(), _open_order_command())
    assert entry_price == pytest.approx(1.1031)

def test_apply_ack_to_instance_state_updates_execution_only_for_failed_open() -> None:
    state = _instance_state()
    order_command = _open_order_command()
    ack_record = MagicMock(command_id=FIXED_COMMAND_ID, status=AckStatus.FAILED.value, ticket=None)
    apply_ack_to_instance_state(state, order_command, ack_record)
    assert state.last_command_id == FIXED_COMMAND_ID
    assert state.last_ack_status == AckStatus.FAILED.value
    assert state.open_ticket is None
    assert state.position_side is None

def test_log_ack_failure_writes_error_journal_for_failed_ack(tmp_path) -> None:
    paths = SystemPaths(root_path=tmp_path)
    instance = _instance()
    ack_record = MagicMock(command_id=FIXED_COMMAND_ID, status=AckStatus.FAILED.value, error_code=10006, error_message='trade failed')
    log_ack_failure(paths, instance, ack_record)
    journal_text = build_error_journal_path(paths, instance).read_text(encoding='utf-8')
    entry = parse_error_journal_line(journal_text.strip())
    assert entry.module == 'execution.engine'
    assert entry.error_type == ErrorType.EXECUTION.value
    assert 'failed' in entry.message
    assert entry.context['command_id'] == FIXED_COMMAND_ID
    assert entry.context['status'] == AckStatus.FAILED.value
    assert entry.context['error_code'] == 10006
    assert entry.context['error_message'] == 'trade failed'

def test_log_ack_failure_writes_error_journal_for_rejected_ack(tmp_path) -> None:
    paths = SystemPaths(root_path=tmp_path)
    instance = _instance()
    ack_record = MagicMock(command_id=FIXED_COMMAND_ID, status=AckStatus.REJECTED.value, error_code=None, error_message='invalid volume')
    log_ack_failure(paths, instance, ack_record)
    journal_text = build_error_journal_path(paths, instance).read_text(encoding='utf-8')
    entry = parse_error_journal_line(journal_text.strip())
    assert entry.context['status'] == AckStatus.REJECTED.value
    assert entry.context['error_message'] == 'invalid volume'

def test_log_ack_failure_ignores_success_ack(tmp_path) -> None:
    paths = SystemPaths(root_path=tmp_path)
    instance = _instance()
    ack_record = MagicMock(command_id=FIXED_COMMAND_ID, status=AckStatus.SUCCESS.value, error_code=None, error_message=None)
    log_ack_failure(paths, instance, ack_record)
    assert not build_error_journal_path(paths, instance).exists()

def test_run_execution_engine_buy_allow_success_updates_control_state_and_trade_journal(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_fixed_command_id(monkeypatch)
    paths = SystemPaths(root_path=tmp_path)
    instance = _instance()
    state = _instance_state()
    _write_ack(paths, instance, _ack_payload(status=AckStatus.SUCCESS.value, ticket=555))
    result = run_execution_engine(paths=paths, instance=instance, instance_state=state, decision_result=_buy_decision_result(), risk_engine_result=_allow_risk_result(), runtime=_runtime_config(), timestamp_utc='2026-07-07T06:00:00.000Z')
    assert isinstance(result, ExecutionResult)
    assert result.control_published is True
    assert result.trade_intent_logged is True
    assert result.state_updated is True
    assert result.order_command.action == OrderAction.OPEN.value
    assert result.order_command.side == Side.BUY.value
    assert result.ack_interpretation is not None
    assert result.ack_interpretation.is_success is True
    assert result.trade_journal_entry is not None
    assert result.trade_journal_entry.ack_status == AckStatus.SUCCESS.value
    assert result.trade_journal_entry.ticket == 555
    archived_control_text = read_archived_control_text(paths, instance)
    assert archived_control_text is not None
    control = parse_control(archived_control_text)
    assert control.command_id == FIXED_COMMAND_ID
    assert control.action == OrderAction.OPEN.value
    assert control.side == Side.BUY.value
    assert state.last_command_id == FIXED_COMMAND_ID
    assert state.last_ack_status == AckStatus.SUCCESS.value
    assert state.open_ticket == 555
    assert state.position_side == Side.BUY.value
    assert state.position_volume == pytest.approx(0.1)
    assert state.position_entry_price == pytest.approx(1.1031)
    assert state.position_stop_loss == pytest.approx(1.0988)
    assert state.position_take_profit == pytest.approx(1.1117)
    journal_lines = build_trade_journal_path(paths, instance).read_text(encoding='utf-8').splitlines()
    assert len(journal_lines) == 1
    journal_entry = parse_trade_journal_line(journal_lines[0])
    assert journal_entry.command_id == FIXED_COMMAND_ID
    assert journal_entry.event == TradeEvent.OPEN.value
    assert journal_entry.ack_status == AckStatus.SUCCESS.value
    assert journal_entry.reason == 'BUY: preferred side selected'
    assert not journal_entry.reason.startswith(INTENT_REASON_PREFIX)

def test_run_execution_engine_failed_ack_writes_error_journal_and_updates_state(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_fixed_command_id(monkeypatch)
    paths = SystemPaths(root_path=tmp_path)
    instance = _instance()
    state = _instance_state()
    _write_ack(paths, instance, _ack_payload(status=AckStatus.FAILED.value, ticket=None, error_code=10006, error_message='trade failed'))
    result = run_execution_engine(paths=paths, instance=instance, instance_state=state, decision_result=_buy_decision_result(), risk_engine_result=_allow_risk_result(), runtime=_runtime_config(), timestamp_utc='2026-07-07T06:00:00.000Z')
    assert result.ack_interpretation is not None
    assert result.ack_interpretation.is_failed is True
    assert state.last_ack_status == AckStatus.FAILED.value
    assert state.open_ticket is None
    journal_text = build_error_journal_path(paths, instance).read_text(encoding='utf-8')
    entry = parse_error_journal_line(journal_text.strip())
    assert entry.module == 'execution.engine'
    assert entry.context['command_id'] == FIXED_COMMAND_ID
    assert entry.context['status'] == AckStatus.FAILED.value
    trade_entry = parse_trade_journal_line(build_trade_journal_path(paths, instance).read_text(encoding='utf-8').strip())
    assert trade_entry.ack_status == AckStatus.FAILED.value

def test_run_execution_engine_trade_journal_reflects_full_intent_to_ack_cycle(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_fixed_command_id(monkeypatch)
    paths = SystemPaths(root_path=tmp_path)
    instance = _instance()
    state = _instance_state()
    _write_ack(paths, instance, _ack_payload(status=AckStatus.SUCCESS.value, ticket=777))
    run_execution_engine(paths=paths, instance=instance, instance_state=state, decision_result=_buy_decision_result(), risk_engine_result=_allow_risk_result(), runtime=_runtime_config(), timestamp_utc='2026-07-07T06:00:00.000Z')
    journal_path = build_trade_journal_path(paths, instance)
    lines = journal_path.read_text(encoding='utf-8').splitlines()
    assert len(lines) == 1
    entry = parse_trade_journal_line(lines[0])
    assert entry.command_id == FIXED_COMMAND_ID
    assert entry.event == TradeEvent.OPEN.value
    assert entry.side == Side.BUY.value
    assert entry.volume == pytest.approx(0.1)
    assert entry.ack_status == AckStatus.SUCCESS.value
    assert entry.ticket == 777
    assert entry.price == pytest.approx(1.1031)
    assert entry.reason == 'BUY: preferred side selected'

def test_run_execution_engine_ack_timeout_writes_error_journal_and_timeout_state(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_fixed_command_id(monkeypatch)
    paths = SystemPaths(root_path=tmp_path)
    instance = _instance()
    state = _instance_state()
    result = run_execution_engine(paths=paths, instance=instance, instance_state=state, decision_result=_buy_decision_result(), risk_engine_result=_allow_risk_result(), runtime=_runtime_config(ack_timeout_ms=100), timestamp_utc='2026-07-07T06:00:00.000Z', started_monotonic=0.0, monotonic_fn=lambda: 1.0, sleep_fn=lambda _: None)
    assert result.ack_interpretation is not None
    assert result.ack_interpretation.is_timeout is True
    assert result.trade_journal_entry is not None
    assert result.trade_journal_entry.ack_status == AckStatus.FAILED.value
    assert state.last_ack_status == AckStatus.TIMEOUT.value
    journal_text = build_error_journal_path(paths, instance).read_text(encoding='utf-8')
    entry = parse_error_journal_line(journal_text.strip())
    assert entry.module == 'core.timeout'
    assert entry.context['command_id'] == FIXED_COMMAND_ID
    assert not build_control_path(paths, instance).exists()
    archived_control = paths.instance_history_dir(instance.account_id, instance.symbol, instance.magic) / instance.control_filename()
    assert archived_control.exists()
    intent_lines = build_trade_journal_path(paths, instance).read_text(encoding='utf-8').splitlines()
    assert len(intent_lines) == 1
    intent_entry = parse_trade_journal_line(intent_lines[0])
    assert intent_entry.ack_status == AckStatus.FAILED.value
    assert REASON_ACK_TIMEOUT in intent_entry.reason

def test_run_execution_engine_none_action_publishes_control_without_ack_or_trade_journal(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_fixed_command_id(monkeypatch)
    paths = SystemPaths(root_path=tmp_path)
    instance = _instance()
    state = _instance_state()
    result = run_execution_engine(paths=paths, instance=instance, instance_state=state, decision_result=_wait_decision_result(), risk_engine_result=_allow_risk_result(), runtime=_runtime_config(), timestamp_utc='2026-07-07T06:00:00.000Z')
    assert result.order_command.action == OrderAction.NONE.value
    assert result.control_published is True
    assert result.trade_intent_logged is False
    assert result.ack_interpretation is None
    assert result.trade_journal_entry is None
    assert result.state_updated is False
    assert not build_trade_journal_path(paths, instance).exists()
    control = parse_control(build_control_path(paths, instance).read_text(encoding='utf-8'))
    assert control.action == OrderAction.NONE.value
    assert control.reason == 'WAIT: equal scores'

def test_run_execution_engine_prefers_trade_management_modify_before_wait_decision(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_fixed_command_id(monkeypatch)
    paths = SystemPaths(root_path=tmp_path)
    instance = _instance()
    state = _instance_state()
    state.update_position(open_ticket=555, position_side=Side.BUY.value, position_volume=0.1, entry_price=1.1031, stop_loss=1.0988, take_profit=1.1117)
    _write_ack(paths, instance, _ack_payload(status=AckStatus.SUCCESS.value, ticket=555))
    management_result = TradeManagementResult(action=OrderAction.MODIFY.value, reason='TRADE_MANAGEMENT_BREAKEVEN: stop loss moved to entry', stop_loss=1.1031, take_profit=1.1117)
    result = run_execution_engine(paths=paths, instance=instance, instance_state=state, decision_result=_wait_decision_result(), risk_engine_result=_allow_risk_result(), runtime=_runtime_config(), management_result=management_result, timestamp_utc='2026-07-07T06:00:00.000Z')
    assert result.order_command.action == OrderAction.MODIFY.value
    assert result.order_command.ticket == 555
    assert result.trade_intent_logged is True
    assert state.position_stop_loss == pytest.approx(1.1031)

def test_execution_engine_performs_analysis_returns_false() -> None:
    assert execution_engine_performs_analysis() is False
