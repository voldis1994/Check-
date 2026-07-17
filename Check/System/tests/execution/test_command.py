from __future__ import annotations
from datetime import datetime, timezone
import pytest
from engine.core.config import parse_config_payload
from engine.core.instance import Instance
from engine.decision.buy import BuyCandidate
from engine.decision.engine import DecisionResult, run_decision_engine
from engine.decision.sell import SellCandidate
from engine.execution.command import OrderCommand, build_close_order_command, build_management_order_command, build_modify_order_command, build_order_command, resolve_order_command
from engine.normalizer.market_normalizer import NormalizedMarketBar
from engine.protocol.constants import Decision, OrderAction, RiskResult, Side
from engine.protocol.models import RiskConfig, StatusRecord, UniverseRecord
from engine.risk.engine import RiskEngineResult, RiskEngineTradeParams, run_risk_engine
from engine.risk.trade_management import TradeManagementResult
from engine.state.instance_state import InstanceState
from tests.core.config_payload import valid_system_config_payload

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

def _system_config():
    payload = valid_system_config_payload()
    payload['analysis'] = {**payload['analysis'], 'lookback_bars': 3, 'structure_lookback_bars': 3}
    return parse_config_payload(payload)

def _manual_decision_result(*, decision: str, preferred_side: str, reason: str, decision_id: str='decision-123') -> DecisionResult:
    engine_result = run_decision_engine(universe=_universe(), market_bars=_bullish_bars(), instance_state=_instance_state(), relative_spread=1.0, system_config=_system_config())
    return DecisionResult(decision_id=decision_id, decision=decision, reason=reason, preferred_side=preferred_side, buy_candidate=BuyCandidate(valid=True, invalid_reason=None, entry_price=1.1031, stop_loss=1.0988, take_profit=1.1117, component_scores={}, buy_score=0.8), sell_candidate=SellCandidate(valid=False, invalid_reason='sell invalid', entry_price=0.0, stop_loss=0.0, take_profit=0.0, component_scores={}, sell_score=0.3), buy_score=0.8, sell_score=0.3, analysis_context=engine_result.analysis_context)

def _allow_risk_result() -> RiskEngineResult:
    return RiskEngineResult(result=RiskResult.ALLOW.value, reason='', position_size=0.1, stop_loss=1.0988, take_profit=1.1117)

def test_build_order_command_buy_allow_produces_open_with_buy_side() -> None:
    decision_result = _manual_decision_result(decision=Decision.BUY.value, preferred_side=Side.BUY.value, reason='BUY: preferred side selected')
    command = build_order_command(decision_result, _allow_risk_result())
    assert isinstance(command, OrderCommand)
    assert command.action == OrderAction.OPEN.value
    assert command.side == Side.BUY.value
    assert command.volume == pytest.approx(0.1)
    assert command.stop_loss == pytest.approx(1.0988)
    assert command.take_profit == pytest.approx(1.1117)
    assert command.reason == 'BUY: preferred side selected'
    assert command.decision_id == decision_result.decision_id
    assert command.ticket is None

def test_build_order_command_sell_allow_produces_open_with_sell_side() -> None:
    decision_result = _manual_decision_result(decision=Decision.SELL.value, preferred_side=Side.SELL.value, reason='SELL: preferred side selected')
    command = build_order_command(decision_result, _allow_risk_result())
    assert command.action == OrderAction.OPEN.value
    assert command.side == Side.SELL.value
    assert command.volume == pytest.approx(0.1)

def test_build_order_command_wait_produces_none_action() -> None:
    decision_result = _manual_decision_result(decision=Decision.WAIT.value, preferred_side=Side.NONE.value, reason='WAIT: equal scores')
    command = build_order_command(decision_result, _allow_risk_result())
    assert command.action == OrderAction.NONE.value
    assert command.side is None
    assert command.volume is None
    assert command.reason == 'WAIT: equal scores'

def test_build_order_command_block_produces_none_action_with_reason() -> None:
    decision_result = _manual_decision_result(decision=Decision.BLOCK.value, preferred_side=Side.BUY.value, reason='BLOCK: spread abnormal')
    command = build_order_command(decision_result, _allow_risk_result())
    assert command.action == OrderAction.NONE.value
    assert command.side is None
    assert command.reason == 'BLOCK: spread abnormal'

def test_build_order_command_risk_block_produces_none_action_with_risk_reason() -> None:
    decision_result = _manual_decision_result(decision=Decision.BUY.value, preferred_side=Side.BUY.value, reason='BUY: preferred side selected')
    risk_result = RiskEngineResult(result=RiskResult.BLOCK.value, reason='RISK_MAX_POSITIONS: open position limit reached', position_size=None, stop_loss=None, take_profit=None)
    command = build_order_command(decision_result, risk_result)
    assert command.action == OrderAction.NONE.value
    assert command.reason == 'RISK_MAX_POSITIONS: open position limit reached'

def test_build_order_command_generates_unique_command_ids() -> None:
    decision_result = _manual_decision_result(decision=Decision.BUY.value, preferred_side=Side.BUY.value, reason='BUY: preferred side selected')
    first = build_order_command(decision_result, _allow_risk_result())
    second = build_order_command(decision_result, _allow_risk_result())
    assert first.command_id
    assert second.command_id
    assert first.command_id != second.command_id

def test_build_order_command_preserves_decision_id_and_allows_explicit_command_id() -> None:
    decision_a = _manual_decision_result(decision=Decision.BUY.value, preferred_side=Side.BUY.value, reason='BUY: preferred side selected', decision_id='decision-a')
    decision_b = _manual_decision_result(decision=Decision.BUY.value, preferred_side=Side.BUY.value, reason='BUY: preferred side selected', decision_id='decision-b')
    command_a = build_order_command(decision_a, _allow_risk_result(), command_id='cmd-fixed-1')
    command_b = build_order_command(decision_b, _allow_risk_result())
    assert command_a.command_id == 'cmd-fixed-1'
    assert command_a.decision_id == 'decision-a'
    assert command_b.decision_id == 'decision-b'
    assert command_a.decision_id != command_b.decision_id

def test_build_order_command_from_decision_and_risk_engines() -> None:
    instance_state = _instance_state()
    decision_result = run_decision_engine(universe=_universe(), market_bars=_bullish_bars(), instance_state=instance_state, relative_spread=1.0, system_config=_system_config())
    risk_engine_result = run_risk_engine(decision_result=decision_result, risk_config=RiskConfig(max_open_positions_per_instance=1, max_daily_loss_percent=2.0, max_drawdown_percent=10.0, daily_loss_limit_enabled=True, drawdown_limit_enabled=True, reward_ratio=2.0, max_stop_loss_pips=100.0, volume_step=0.01, fixed_lot_volume=0.01), instance_state=instance_state, status=StatusRecord(schema_version='1.0.0', timestamp_utc='2026-07-07T06:00:00.000Z', account_id='12345', connected=True, trade_allowed=True, balance=10000.0, equity=10000.0, margin_free=9000.0, ea_version='1.0.0'), trade_params=RiskEngineTradeParams(volume_step=0.01, max_stop_loss_pips=100.0), swing_low=1.099, swing_high=1.104)
    command = build_order_command(decision_result, risk_engine_result)
    assert command.decision_id == decision_result.decision_id
    if decision_result.decision == Decision.BUY.value and risk_engine_result.result == RiskResult.ALLOW.value:
        assert command.action == OrderAction.OPEN.value
        assert command.side == Side.BUY.value
        assert command.volume is not None and command.volume > 0
    else:
        assert command.action == OrderAction.NONE.value

def test_build_modify_order_command_sets_ticket_and_levels() -> None:
    command = build_modify_order_command(ticket=123456, side=Side.BUY.value, stop_loss=1.101, take_profit=1.1117, reason='TRADE_MANAGEMENT_BREAKEVEN: stop loss moved to entry', decision_id='decision-modify', command_id='cmd-modify')
    assert command.action == OrderAction.MODIFY.value
    assert command.ticket == 123456
    assert command.side == Side.BUY.value
    assert command.stop_loss == pytest.approx(1.101)
    assert command.take_profit == pytest.approx(1.1117)
    assert command.volume is None

def test_build_close_order_command_sets_ticket_and_volume() -> None:
    command = build_close_order_command(ticket=654321, side=Side.SELL.value, volume=0.05, reason='TRADE_MANAGEMENT_PARTIAL_CLOSE: partial volume close triggered', decision_id='decision-close', command_id='cmd-close')
    assert command.action == OrderAction.CLOSE.value
    assert command.ticket == 654321
    assert command.side == Side.SELL.value
    assert command.volume == pytest.approx(0.05)
    assert command.stop_loss is None
    assert command.take_profit is None

def test_build_management_order_command_returns_none_for_none_action() -> None:
    result = TradeManagementResult(action=OrderAction.NONE.value, reason='')
    command = build_management_order_command(result, ticket=123456, side=Side.BUY.value, decision_id='decision-mgmt')
    assert command is None

def test_build_management_order_command_maps_modify_result() -> None:
    result = TradeManagementResult(action=OrderAction.MODIFY.value, reason='TRADE_MANAGEMENT_TRAILING: stop loss raised to follow structure', stop_loss=1.102, take_profit=1.1117)
    command = build_management_order_command(result, ticket=123456, side=Side.BUY.value, decision_id='decision-mgmt', command_id='cmd-mgmt-modify')
    assert command is not None
    assert command.action == OrderAction.MODIFY.value
    assert command.command_id == 'cmd-mgmt-modify'
    assert command.stop_loss == pytest.approx(1.102)

def test_build_management_order_command_maps_close_result() -> None:
    result = TradeManagementResult(action=OrderAction.CLOSE.value, reason='TRADE_MANAGEMENT_TIME_STOP: maximum bars in trade reached', volume=0.1)
    command = build_management_order_command(result, ticket=123456, side=Side.BUY.value, decision_id='decision-mgmt')
    assert command is not None
    assert command.action == OrderAction.CLOSE.value
    assert command.volume == pytest.approx(0.1)

def test_resolve_order_command_prefers_management_over_wait_decision() -> None:
    decision_result = _manual_decision_result(decision=Decision.WAIT.value, preferred_side=Side.NONE.value, reason='WAIT: equal scores')
    management_result = TradeManagementResult(action=OrderAction.MODIFY.value, reason='TRADE_MANAGEMENT_BREAKEVEN: stop loss moved to entry', stop_loss=1.101, take_profit=1.1117)
    command = resolve_order_command(decision_result, _allow_risk_result(), management_result, ticket=123456, side=Side.BUY.value, command_id='cmd-resolve')
    assert command.action == OrderAction.MODIFY.value
    assert command.ticket == 123456

def test_resolve_order_command_falls_back_to_decision_command() -> None:
    decision_result = _manual_decision_result(decision=Decision.BUY.value, preferred_side=Side.BUY.value, reason='BUY: preferred side selected')
    command = resolve_order_command(decision_result, _allow_risk_result(), None, ticket=123456, side=Side.BUY.value)
    assert command.action == OrderAction.OPEN.value
