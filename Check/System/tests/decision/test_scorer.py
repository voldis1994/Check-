from __future__ import annotations
import inspect
import pytest
from engine.analysis.context import AnalysisContext
from engine.decision.buy import BuyCandidate
from engine.decision.scorer import ScoringResult, compare_candidates, resolve_preferred_side
from engine.decision.sell import SellCandidate
from engine.protocol.constants import Side

def _context() -> AnalysisContext:
    return AnalysisContext(session='LONDON', regime='trending', news_active=False, context_quality=0.9, trade_environment='FAVORABLE', spread_filter_passed=True)

def _buy_candidate(*, valid: bool=True, buy_score: float=0.8) -> BuyCandidate:
    return BuyCandidate(valid=valid, invalid_reason=None if valid else 'DATA_INVALID: buy setup rejected', entry_price=1.1031, stop_loss=1.0988, take_profit=1.1117, component_scores={'momentum': buy_score}, buy_score=buy_score)

def _sell_candidate(*, valid: bool=True, sell_score: float=0.6) -> SellCandidate:
    return SellCandidate(valid=valid, invalid_reason=None if valid else 'DATA_INVALID: sell setup rejected', entry_price=1.1031, stop_loss=1.1074, take_profit=1.0945, component_scores={'momentum': sell_score}, sell_score=sell_score)

def test_resolve_preferred_side_uses_highest_score_when_both_valid() -> None:
    preferred_side = resolve_preferred_side(_buy_candidate(buy_score=0.9), _sell_candidate(sell_score=0.4))
    assert preferred_side == Side.BUY.value

def test_resolve_preferred_side_prefers_sell_when_sell_score_is_higher() -> None:
    preferred_side = resolve_preferred_side(_buy_candidate(buy_score=0.3), _sell_candidate(sell_score=0.7))
    assert preferred_side == Side.SELL.value

def test_resolve_preferred_side_is_none_when_scores_are_equal() -> None:
    preferred_side = resolve_preferred_side(_buy_candidate(buy_score=0.55), _sell_candidate(sell_score=0.55))
    assert preferred_side == Side.NONE.value

def test_resolve_preferred_side_uses_only_valid_direction() -> None:
    buy_only = resolve_preferred_side(_buy_candidate(valid=True), _sell_candidate(valid=False))
    sell_only = resolve_preferred_side(_buy_candidate(valid=False), _sell_candidate(valid=True))
    neither = resolve_preferred_side(_buy_candidate(valid=False), _sell_candidate(valid=False))
    assert buy_only == Side.BUY.value
    assert sell_only == Side.SELL.value
    assert neither == Side.NONE.value

def test_compare_candidates_returns_score_delta_and_context_adjusted_scores() -> None:
    result = compare_candidates(buy_candidate=_buy_candidate(buy_score=0.8), sell_candidate=_sell_candidate(sell_score=0.5), context=_context())
    assert isinstance(result, ScoringResult)
    assert result.buy_score == pytest.approx(0.72)
    assert result.sell_score == pytest.approx(0.45)
    assert result.score_delta == pytest.approx(0.27)
    assert result.preferred_side == Side.BUY.value

def test_scoring_compares_without_filtering_candidates() -> None:
    buy_candidate = _buy_candidate(valid=False, buy_score=0.2)
    sell_candidate = _sell_candidate(valid=False, sell_score=0.9)
    result = compare_candidates(buy_candidate=buy_candidate, sell_candidate=sell_candidate, context=_context())
    assert result.buy_score == pytest.approx(buy_candidate.buy_score * _context().context_quality)
    assert result.sell_score == pytest.approx(sell_candidate.sell_score * _context().context_quality)
    assert result.preferred_side == Side.NONE.value

def test_resolve_preferred_side_matches_compare_candidates_with_context() -> None:
    buy_candidate = _buy_candidate(buy_score=0.8)
    sell_candidate = _sell_candidate(sell_score=0.5)
    context = _context()
    assert resolve_preferred_side(buy_candidate, sell_candidate, context=context) == compare_candidates(buy_candidate=buy_candidate, sell_candidate=sell_candidate, context=context).preferred_side

def test_scoring_does_not_return_block() -> None:
    source = inspect.getsource(compare_candidates)
    assert 'BLOCK' not in source
    assert 'block' not in source.lower().replace('preferred_side', '')
