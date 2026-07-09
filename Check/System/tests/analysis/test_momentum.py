from __future__ import annotations
from datetime import datetime, timezone
from engine.analysis.momentum import analyze_momentum_and_trend
from engine.normalizer.market_normalizer import NormalizedMarketBar

def _bar(index: int, open_: float, high: float, low: float, close: float) -> NormalizedMarketBar:
    return NormalizedMarketBar(time_utc=datetime(2026, 7, 7, 6, index, tzinfo=timezone.utc), open=open_, high=high, low=low, close=close, volume=100.0, symbol='EURUSD', timeframe='M1', digits=5, point=1e-05, bar_index=index)

def test_momentum_score_is_in_minus_one_to_one_range() -> None:
    result = analyze_momentum_and_trend((_bar(0, 1.1, 1.101, 1.099, 1.1), _bar(1, 1.1, 1.12, 1.099, 1.2)))
    assert -1.0 <= result.momentum_score <= 1.0

def test_trend_direction_can_be_up_down_sideways() -> None:
    up = analyze_momentum_and_trend((_bar(0, 1.0, 1.1, 0.9, 1.0), _bar(1, 1.0, 1.2, 0.95, 1.1)))
    down = analyze_momentum_and_trend((_bar(0, 1.0, 1.2, 0.95, 1.1), _bar(1, 1.1, 1.15, 0.8, 0.9)))
    sideways = analyze_momentum_and_trend((_bar(0, 1.0, 1.1, 0.9, 1.0), _bar(1, 1.0, 1.1, 0.9, 1.0)))
    assert up.trend_direction == 'UP'
    assert down.trend_direction == 'DOWN'
    assert sideways.trend_direction == 'SIDEWAYS'

def test_trend_strength_is_in_zero_to_one_range() -> None:
    result = analyze_momentum_and_trend((_bar(0, 1.1, 1.101, 1.099, 1.1), _bar(1, 1.1, 1.103, 1.0995, 1.1015), _bar(2, 1.1015, 1.104, 1.1, 1.103)))
    assert 0.0 <= result.trend_strength <= 1.0

def test_momentum_analysis_does_not_generate_trade_decision() -> None:
    result = analyze_momentum_and_trend((_bar(0, 1.1, 1.101, 1.099, 1.1), _bar(1, 1.1, 1.102, 1.0995, 1.101)))
    assert not hasattr(result, 'decision')
    assert not hasattr(result, 'action')
