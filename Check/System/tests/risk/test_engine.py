from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
import pytest
from engine.core.config import parse_config_payload
from engine.core.instance import Instance
from engine.decision.buy import BuyCandidate
from engine.decision.engine import DecisionResult, run_decision_engine
from engine.decision.sell import SellCandidate
from engine.normalizer.market_normalizer import NormalizedMarketBar
from engine.protocol.constants import REASON_ACCOUNT_NOT_TRADEABLE, REASON_DATA_INVALID, REASON_RISK_MAX_POSITIONS, Decision, RiskResult, Side
from engine.protocol.models import RiskConfig, StatusRecord, UniverseRecord
from engine.risk.engine import RiskEngineResult, RiskEngineTradeParams, run_risk_engine
from engine.state.instance_state import InstanceState
from tests.core.config_payload import valid_system_config_payload

def _bar(index: int, open_: float, high: float, low: float, close: float) -> NormalizedMarketBar:
    return NormalizedMarketBar(time_utc=datetime(2026, 7, 7, 6, index, tzinfo=timezone.utc), open=open_, high=high, low=low, close=close, volume=100.0, symbol='EURUSD', timeframe='M1', digits=5, point=1e-05, bar_index=index)

def _bullish_bars() -> tuple[NormalizedMarketBar, ...]:
    return (_bar(0, 1.1, 1.102, 1.099, 1.1015), _bar(1, 1.1015, 1.103, 1.1005, 1.1022), _bar(2, 1.1022, 1.104, 1.101, 1.1031))

def _universe() -> UniverseRecord:
    return UniverseRecord(schema_version='1.0.0', timestamp_utc='2026-07-07T06:00:00.000Z', session='LONDON', market_regime='trending', news_window_active=False)

def _instance_state(*, with_position: bool=False) -> InstanceState:
    state = InstanceState(instance=Instance(account_id='12345', symbol='EURUSD', magic=100001))
    state.update_instrument(digits=5, point=1e-05, pip=0.0001)
    if with_position:
        state.update_position(open_ticket=1001, position_side='BUY', position_volume=0.1)
    return state

def _status(*, trade_allowed: bool=True, equity: float=10000.0) -> StatusRecord:
    return StatusRecord(schema_version='1.0.0', timestamp_utc='2026-07-07T06:00:00.000Z', account_id='12345', connected=True, trade_allowed=trade_allowed, balance=equity, equity=equity, margin_free=9000.0, ea_version='1.0.0')

def _risk_config() -> RiskConfig:
    return RiskConfig(max_open_positions_per_instance=1, max_daily_loss_percent=2.0, max_drawdown_percent=10.0, reward_ratio=2.0, max_risk_per_trade_percent=1.0, max_stop_loss_pips=100.0, volume_step=0.01)

def _trade_params() -> RiskEngineTradeParams:
    return RiskEngineTradeParams(max_risk_per_trade_percent=1.0, volume_step=0.01, max_stop_loss_pips=100.0)

def _system_config(**analysis_overrides: Any) -> object:
    payload = valid_system_config_payload()
    payload['analysis'] = {**payload['analysis'], 'lookback_bars': 3, **analysis_overrides}
    return parse_config_payload(payload)

def _buy_decision_result() -> DecisionResult:
    return run_decision_engine(universe=_universe(), market_bars=_bullish_bars(), instance_state=_instance_state(), relative_spread=1.0, system_config=_system_config())

def _manual_decision_result(*, decision: str, preferred_side: str, buy_candidate: BuyCandidate | None=None, sell_candidate: SellCandidate | None=None, reason: str='test reason') -> DecisionResult:
    default_buy = BuyCandidate(valid=True, invalid_reason=None, entry_price=1.1031, stop_loss=1.0988, take_profit=1.1117, component_scores={}, buy_score=1.0)
    default_sell = SellCandidate(valid=False, invalid_reason='sell invalid', entry_price=0.0, stop_loss=0.0, take_profit=0.0, component_scores={}, sell_score=0.0)
    return DecisionResult(decision_id='test-decision-id', decision=decision, reason=reason, preferred_side=preferred_side, buy_candidate=buy_candidate or default_buy, sell_candidate=sell_candidate or default_sell, buy_score=1.0, sell_score=0.0, analysis_context=_buy_decision_result().analysis_context)

def _run_with_decision(decision_result: DecisionResult, *, status: StatusRecord | None=None, instance_state: InstanceState | None=None, trade_params: RiskEngineTradeParams | None=None) -> RiskEngineResult:
    return run_risk_engine(decision_result=decision_result, risk_config=_risk_config(), instance_state=instance_state or _instance_state(), status=status or _status(), trade_params=trade_params or _trade_params(), swing_low=1.099, swing_high=1.104)

def test_risk_engine_never_returns_wait_for_wait_decision() -> None:
    decision_result = _manual_decision_result(decision=Decision.WAIT.value, preferred_side=Side.BUY.value, reason='WAIT: equal scores')
    result = _run_with_decision(decision_result)
    assert result.result == RiskResult.BLOCK.value
    assert result.result != Decision.WAIT.value
    assert result.reason == 'WAIT: equal scores'

def test_risk_engine_never_returns_wait_for_block_decision() -> None:
    decision_result = _manual_decision_result(decision=Decision.BLOCK.value, preferred_side=Side.BUY.value, reason='BLOCK: spread abnormal')
    result = _run_with_decision(decision_result)
    assert result.result == RiskResult.BLOCK.value
    assert result.result != Decision.WAIT.value

def test_risk_engine_does_not_change_preferred_side() -> None:
    decision_result = _buy_decision_result()
    preferred_side_before = decision_result.preferred_side
    _run_with_decision(decision_result)
    assert decision_result.preferred_side == preferred_side_before

def test_risk_engine_allow_includes_volume_stop_loss_and_take_profit() -> None:
    decision_result = _buy_decision_result()
    assert decision_result.decision == Decision.BUY.value
    result = _run_with_decision(decision_result)
    assert result.result == RiskResult.ALLOW.value
    assert result.position_size is not None
    assert result.position_size > 0
    assert result.stop_loss is not None
    assert result.stop_loss > 0
    assert result.take_profit is not None
    assert result.take_profit > 0
    assert result.reason == ''

def test_risk_engine_block_includes_reason() -> None:
    decision_result = _manual_decision_result(decision=Decision.BUY.value, preferred_side=Side.BUY.value, buy_candidate=BuyCandidate(valid=False, invalid_reason='BUY_INVALID: structure filter failed', entry_price=0.0, stop_loss=0.0, take_profit=0.0, component_scores={}, buy_score=0.0))
    result = _run_with_decision(decision_result)
    assert result.result == RiskResult.BLOCK.value
    assert result.reason == 'BUY_INVALID: structure filter failed'
    assert result.position_size is None
    assert result.stop_loss is None
    assert result.take_profit is None

def test_risk_engine_outputs_only_allow_or_block_not_buy_or_sell() -> None:
    buy_path = _run_with_decision(_buy_decision_result())
    wait_path = _run_with_decision(_manual_decision_result(decision=Decision.WAIT.value, preferred_side=Side.BUY.value, reason='WAIT: equal scores'))
    assert buy_path.result in {RiskResult.ALLOW.value, RiskResult.BLOCK.value}
    assert wait_path.result in {RiskResult.ALLOW.value, RiskResult.BLOCK.value}
    assert buy_path.result not in {Decision.BUY.value, Decision.SELL.value}
    assert wait_path.result not in {Decision.BUY.value, Decision.SELL.value}

def test_risk_engine_blocks_when_trade_not_allowed() -> None:
    decision_result = _buy_decision_result()
    result = _run_with_decision(decision_result, status=_status(trade_allowed=False))
    assert result.result == RiskResult.BLOCK.value
    assert REASON_ACCOUNT_NOT_TRADEABLE in result.reason

def test_risk_engine_blocks_when_open_position_limit_reached() -> None:
    decision_result = _buy_decision_result()
    result = _run_with_decision(decision_result, instance_state=_instance_state(with_position=True))
    assert result.result == RiskResult.BLOCK.value
    assert REASON_RISK_MAX_POSITIONS in result.reason

def test_risk_engine_blocks_when_stop_loss_exceeds_max_pips() -> None:
    decision_result = _buy_decision_result()
    tight_params = RiskEngineTradeParams(max_risk_per_trade_percent=1.0, volume_step=0.01, max_stop_loss_pips=1.0)
    result = _run_with_decision(decision_result, trade_params=tight_params)
    assert result.result == RiskResult.BLOCK.value
    assert 'max_stop_loss_pips' in result.reason

def test_risk_engine_blocks_when_position_size_rounds_to_zero() -> None:
    decision_result = _buy_decision_result()
    tiny_risk_params = RiskEngineTradeParams(max_risk_per_trade_percent=0.0001, volume_step=0.1, max_stop_loss_pips=100.0)
    result = _run_with_decision(decision_result, trade_params=tiny_risk_params)
    assert result.result == RiskResult.BLOCK.value
    assert result.reason

def test_risk_engine_blocks_invalid_preferred_side() -> None:
    decision_result = _manual_decision_result(decision=Decision.BUY.value, preferred_side='NONE')
    result = _run_with_decision(decision_result)
    assert result.result == RiskResult.BLOCK.value
    assert REASON_DATA_INVALID in result.reason

def test_risk_engine_uses_preferred_side_candidate_for_sell() -> None:
    sell_candidate = SellCandidate(valid=True, invalid_reason=None, entry_price=1.1, stop_loss=1.1052, take_profit=1.0896, component_scores={}, sell_score=1.0)
    decision_result = _manual_decision_result(decision=Decision.SELL.value, preferred_side=Side.SELL.value, sell_candidate=sell_candidate)
    result = _run_with_decision(decision_result)
    assert result.result == RiskResult.ALLOW.value
    assert result.stop_loss == pytest.approx(1.1052)
    assert result.take_profit == pytest.approx(1.0896)
    assert result.position_size is not None
    assert result.position_size > 0
