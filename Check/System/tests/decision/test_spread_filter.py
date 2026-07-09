from __future__ import annotations
from engine.decision.filters.spread_filter import evaluate_spread_filter

def test_spread_acceptable_is_based_on_relative_threshold() -> None:
    acceptable = evaluate_spread_filter(relative_spread=1.1, threshold=1.5)
    rejected = evaluate_spread_filter(relative_spread=1.7, threshold=1.5)
    assert acceptable.spread_acceptable
    assert not rejected.spread_acceptable

def test_no_hard_max_spread_numbers_used() -> None:
    very_high_relative = evaluate_spread_filter(relative_spread=999.0, threshold=1000.0)
    assert very_high_relative.spread_acceptable
    assert very_high_relative.reason is None

def test_spread_abnormal_reason_is_generated() -> None:
    result = evaluate_spread_filter(relative_spread=2.2, threshold=1.8)
    assert not result.spread_acceptable
    assert result.reason is not None
    assert 'SPREAD_ABNORMAL' in result.reason
