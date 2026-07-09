from __future__ import annotations
import pytest
from engine.ai_decision_layer import AIDecision, AIQueryResult, apply_ai_advisory_decision, decide_final_decision, get_ai_decision
from engine.protocol.constants import Decision, RiskResult
from engine.protocol.models import AIConfig
from engine.risk.engine import RiskEngineResult

def _advisory_config() -> AIConfig:
    return AIConfig(mode='advisory', fail_closed=False, reject_action='BLOCK', timeout_ms=10000, retry_max=2, retry_delay_ms=500)

def _required_config() -> AIConfig:
    return AIConfig(mode='required', fail_closed=True, reject_action='BLOCK', timeout_ms=10000, retry_max=2, retry_delay_ms=500)

def _risk_allow() -> RiskEngineResult:
    return RiskEngineResult(result=RiskResult.ALLOW.value, reason='', position_size=0.1, stop_loss=1.09, take_profit=1.11)

def _risk_block() -> RiskEngineResult:
    return RiskEngineResult(result=RiskResult.BLOCK.value, reason='rules blocked', position_size=None, stop_loss=None, take_profit=None)

def _ai(*, bias: str='NEUTRAL', confidence: float=0.8, allow_buy: bool=True, allow_sell: bool=False, allow_close: bool=True, reason: str='ai ok') -> AIDecision:
    return AIDecision(bias=bias, confidence=confidence, allow_buy=allow_buy, allow_sell=allow_sell, allow_close=allow_close, reason=reason)

def _ai_query(decision: AIDecision | None, error_type: str | None=None) -> AIQueryResult:
    return AIQueryResult(decision=decision, error_type=error_type)

def test_buy_ai_allows_risk_pass_final_buy() -> None:
    ai = _ai(allow_buy=True)
    decision, _reason, _meta = decide_final_decision(system_signal=Decision.BUY.value, system_reason='BUY: test', ai_query=_ai_query(ai), risk_engine_result=_risk_allow(), ai_config=_advisory_config())
    assert decision == Decision.BUY.value

def test_buy_ai_rejects_final_block() -> None:
    ai = _ai(allow_buy=False)
    decision, _reason, _meta = decide_final_decision(system_signal=Decision.BUY.value, system_reason='BUY: test', ai_query=_ai_query(ai), risk_engine_result=_risk_allow(), ai_config=_advisory_config())
    assert decision == Decision.BLOCK.value

def test_sell_ai_allows_risk_pass_final_sell() -> None:
    ai = _ai(bias='NEUTRAL', allow_buy=False, allow_sell=True)
    decision, _reason, _meta = decide_final_decision(system_signal=Decision.SELL.value, system_reason='SELL: test', ai_query=_ai_query(ai), risk_engine_result=_risk_allow(), ai_config=_advisory_config())
    assert decision == Decision.SELL.value

def test_sell_ai_rejects_final_block() -> None:
    ai = _ai(allow_buy=False, allow_sell=False)
    decision, _reason, _meta = decide_final_decision(system_signal=Decision.SELL.value, system_reason='SELL: test', ai_query=_ai_query(ai), risk_engine_result=_risk_allow(), ai_config=_advisory_config())
    assert decision == Decision.BLOCK.value

def test_ai_avoid_final_block() -> None:
    ai = _ai(bias='AVOID', allow_buy=True, allow_sell=True)
    decision, _reason, _meta = decide_final_decision(system_signal=Decision.BUY.value, system_reason='BUY: test', ai_query=_ai_query(ai), risk_engine_result=_risk_allow(), ai_config=_advisory_config())
    assert decision == Decision.BLOCK.value

def test_advisory_timeout_falls_back_to_system_buy() -> None:
    decision, reason, meta = decide_final_decision(system_signal=Decision.BUY.value, system_reason='BUY: system signal', ai_query=_ai_query(None, error_type='timeout'), risk_engine_result=_risk_allow(), ai_config=_advisory_config())
    assert decision == Decision.BUY.value
    assert 'ai_timeout_system_fallback' in reason
    assert meta.ai_fallback_used is True

def test_advisory_wait_timeout_stays_wait() -> None:
    decision, _reason, meta = decide_final_decision(system_signal=Decision.WAIT.value, system_reason='WAIT: equal scores', ai_query=_ai_query(None, error_type='timeout'), risk_engine_result=_risk_allow(), ai_config=_advisory_config())
    assert decision == Decision.WAIT.value
    assert meta.ai_fallback_used is True

def test_advisory_invalid_json_falls_back_to_system_buy() -> None:
    decision, reason, _meta = decide_final_decision(system_signal=Decision.BUY.value, system_reason='BUY: system signal', ai_query=_ai_query(None, error_type='invalid_json'), risk_engine_result=_risk_allow(), ai_config=_advisory_config())
    assert decision == Decision.BUY.value
    assert 'ai_invalid_json_system_fallback' in reason

def test_required_timeout_returns_block(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('OPENAI_API_KEY', 'test-key')
    from engine import ai_decision_layer as mdl

    def _raise_timeout(*_args, **_kwargs):
        raise TimeoutError('timeout')
    monkeypatch.setattr(mdl, '_call_openai', _raise_timeout)
    ai_query = get_ai_decision(system_signal=Decision.BUY.value, market_context={}, ai_config=_required_config())
    assert ai_query.decision is None
    assert ai_query.error_type == 'timeout'
    decision, reason, _meta = decide_final_decision(system_signal=Decision.BUY.value, system_reason='BUY: system signal', ai_query=ai_query, risk_engine_result=_risk_allow(), ai_config=_required_config())
    assert decision == Decision.BLOCK.value
    assert reason == 'ai_required_missing_block'

def test_required_api_error_returns_block(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('OPENAI_API_KEY', 'test-key')
    from engine import ai_decision_layer as mdl

    def _raise_error(*_args, **_kwargs):
        raise RuntimeError('api error')
    monkeypatch.setattr(mdl, '_call_openai', _raise_error)
    ai_query = get_ai_decision(system_signal=Decision.BUY.value, market_context={}, ai_config=_required_config())
    assert ai_query.decision is None
    decision, _reason, _meta = decide_final_decision(system_signal=Decision.BUY.value, system_reason='BUY: system signal', ai_query=ai_query, risk_engine_result=_risk_allow(), ai_config=_required_config())
    assert decision == Decision.BLOCK.value

def test_advisory_reject_action_wait() -> None:
    config = AIConfig(mode='advisory', fail_closed=False, reject_action='WAIT', timeout_ms=10000, retry_max=2, retry_delay_ms=500)
    decision, reason, _fallback, _ai_reason = apply_ai_advisory_decision(system_decision=Decision.BUY.value, system_reason='BUY: test', ai_result=_ai(allow_buy=False), ai_error=None, config=config)
    assert decision == Decision.WAIT.value
    assert 'ai_veto_buy_rejected' in reason

def test_risk_fail_always_blocks_even_if_ai_allows() -> None:
    ai = _ai(allow_buy=True)
    decision, _reason, _meta = decide_final_decision(system_signal=Decision.BUY.value, system_reason='BUY: test', ai_query=_ai_query(ai), risk_engine_result=_risk_block(), ai_config=_advisory_config())
    assert decision == Decision.BLOCK.value

def test_apply_risk_block_updates_decision_result() -> None:
    from engine.ai_decision_layer import apply_risk_block_to_decision_result
    from tests.journal.test_decision_journal import _manual_decision_result
    original = _manual_decision_result()
    blocked = apply_risk_block_to_decision_result(decision_result=original, risk_engine_result=_risk_block())
    assert blocked.decision == Decision.BLOCK.value
    assert blocked.decision_id == original.decision_id
    assert 'RISK_FAIL' in blocked.reason
