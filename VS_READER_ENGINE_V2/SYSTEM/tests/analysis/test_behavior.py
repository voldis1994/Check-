from __future__ import annotations

from datetime import datetime, timezone

from engine.analysis.behavior import analyze_behavior
from engine.normalizer.market_normalizer import NormalizedMarketBar


def _bar(index: int, open_: float, high: float, low: float, close: float) -> NormalizedMarketBar:
    return NormalizedMarketBar(
        time_utc=datetime(2026, 7, 7, 6, index, tzinfo=timezone.utc),
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=100.0,
        symbol="EURUSD",
        timeframe="M1",
        digits=5,
        point=0.00001,
        bar_index=index,
    )


def test_behavior_object_has_consistent_structure() -> None:
    result = analyze_behavior(
        (
            _bar(0, 1.1000, 1.1020, 1.0990, 1.1015),
            _bar(1, 1.1015, 1.1030, 1.1005, 1.1025),
        )
    )
    assert isinstance(result.dominant_pattern, str)
    assert isinstance(result.indecision_detected, bool)
    assert isinstance(result.rejection_detected, bool)
    assert isinstance(result.behavior_score, float)
    assert 0.0 <= result.behavior_score <= 1.0


def test_behavior_analysis_is_independent_from_decision_logic() -> None:
    result = analyze_behavior(
        (
            _bar(0, 1.1000, 1.1010, 1.0990, 1.1001),
            _bar(1, 1.1001, 1.1025, 1.0985, 1.1000),
        )
    )
    assert not hasattr(result, "decision")
    assert not hasattr(result, "action")
