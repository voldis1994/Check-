from __future__ import annotations
from engine.decision.buy import BuyCandidate
from engine.decision.reason import build_reason
from engine.decision.scorer import ScoringResult
from engine.decision.sell import SellCandidate
from engine.decision.wait_block import BlockDecisionResult, WaitDecisionResult, build_both_directions_invalid_reason, evaluate_block_decision, evaluate_wait_decision
from engine.protocol.constants import REASON_BOTH_DIRECTIONS_INVALID, REASON_EQUAL_SCORES, REASON_RISK_MAX_DRAWDOWN, REASON_SPREAD_ABNORMAL, Side, is_wait_reason_code

def _buy_candidate(*, valid: bool=True, buy_score: float=0.8) -> BuyCandidate:
    return BuyCandidate(valid=valid, invalid_reason=None if valid else 'SPREAD_ABNORMAL: buy spread too high', entry_price=1.1031, stop_loss=1.0988, take_profit=1.1117, component_scores={'momentum': buy_score}, buy_score=buy_score)

def _sell_candidate(*, valid: bool=True, sell_score: float=0.6) -> SellCandidate:
    return SellCandidate(valid=valid, invalid_reason=None if valid else 'VOLATILITY_ABNORMAL: sell volatility too high', entry_price=1.1031, stop_loss=1.1074, take_profit=1.0945, component_scores={'momentum': sell_score}, sell_score=sell_score)

def _scoring(*, preferred_side: str, buy_score: float=0.8, sell_score: float=0.6) -> ScoringResult:
    return ScoringResult(buy_score=buy_score, sell_score=sell_score, score_delta=buy_score - sell_score, preferred_side=preferred_side)

def test_wait_is_not_the_default_when_one_direction_is_valid() -> None:
    result = evaluate_wait_decision(buy_candidate=_buy_candidate(valid=True), sell_candidate=_sell_candidate(valid=False), scoring=_scoring(preferred_side=Side.BUY.value))
    assert not result.is_wait
    assert result.reason is None

def test_both_directions_invalid_produces_wait() -> None:
    buy_candidate = _buy_candidate(valid=False)
    sell_candidate = _sell_candidate(valid=False)
    result = evaluate_wait_decision(buy_candidate=buy_candidate, sell_candidate=sell_candidate, scoring=_scoring(preferred_side=Side.NONE.value))
    assert result.is_wait
    assert result.reason is not None
    assert REASON_BOTH_DIRECTIONS_INVALID in result.reason
    assert buy_candidate.invalid_reason in result.reason
    assert sell_candidate.invalid_reason in result.reason

def test_equal_scores_produces_wait() -> None:
    result = evaluate_wait_decision(buy_candidate=_buy_candidate(valid=True, buy_score=0.7), sell_candidate=_sell_candidate(valid=True, sell_score=0.7), scoring=_scoring(preferred_side=Side.NONE.value, buy_score=0.7, sell_score=0.7))
    assert result.is_wait
    assert result.reason is not None
    assert REASON_EQUAL_SCORES in result.reason

def test_build_both_directions_invalid_reason_includes_both_details() -> None:
    reason = build_both_directions_invalid_reason(_buy_candidate(valid=False), _sell_candidate(valid=False))
    assert REASON_BOTH_DIRECTIONS_INVALID in reason
    assert 'buy_invalid_reason=' in reason
    assert 'sell_invalid_reason=' in reason

def test_block_decision_uses_block_reason_codes() -> None:
    result = evaluate_block_decision(block_reason=build_reason(REASON_SPREAD_ABNORMAL, 'relative spread above threshold'))
    assert isinstance(result, BlockDecisionResult)
    assert result.is_block
    assert result.reason is not None
    assert REASON_SPREAD_ABNORMAL in result.reason

def test_block_is_not_wait() -> None:
    block_reason = build_reason(REASON_RISK_MAX_DRAWDOWN, 'drawdown limit reached')
    block_result = evaluate_block_decision(block_reason=block_reason)
    assert block_result.is_block
    assert block_result.reason is not None
    assert not is_wait_reason_code(block_result.reason.split(':', 1)[0])

def test_non_block_reason_does_not_trigger_block() -> None:
    wait_reason = build_reason(REASON_EQUAL_SCORES, 'buy and sell scores are equal')
    result = evaluate_block_decision(block_reason=wait_reason)
    assert not result.is_block
    assert result.reason is None

def test_every_wait_result_has_reason_when_wait_is_true() -> None:
    wait_cases = [evaluate_wait_decision(buy_candidate=_buy_candidate(valid=False), sell_candidate=_sell_candidate(valid=False), scoring=_scoring(preferred_side=Side.NONE.value)), evaluate_wait_decision(buy_candidate=_buy_candidate(valid=True, buy_score=0.5), sell_candidate=_sell_candidate(valid=True, sell_score=0.5), scoring=_scoring(preferred_side=Side.NONE.value, buy_score=0.5, sell_score=0.5))]
    for result in wait_cases:
        assert isinstance(result, WaitDecisionResult)
        assert result.is_wait
        assert result.reason is not None
        assert ':' in result.reason
