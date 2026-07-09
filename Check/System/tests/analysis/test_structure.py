from __future__ import annotations
from datetime import datetime, timezone
from engine.analysis.structure import analyze_structure
from engine.normalizer.market_normalizer import NormalizedMarketBar

def _bar(index: int, open_: float, high: float, low: float, close: float) -> NormalizedMarketBar:
    return NormalizedMarketBar(time_utc=datetime(2026, 7, 7, 6, index, tzinfo=timezone.utc), open=open_, high=high, low=low, close=close, volume=100.0, symbol='EURUSD', timeframe='M1', digits=5, point=1e-05, bar_index=index)

def test_structure_identifies_swing_high_and_low() -> None:
    bars = (_bar(0, 1.1, 1.101, 1.099, 1.1005), _bar(1, 1.1005, 1.1025, 1.1, 1.102), _bar(2, 1.102, 1.103, 1.0985, 1.0995))
    result = analyze_structure(bars)
    assert result.swing_high == 1.103
    assert result.swing_low == 1.0985
    assert result.support_level == 1.0985
    assert result.resistance_level == 1.103

def test_structure_bias_values() -> None:
    bullish = analyze_structure((_bar(0, 1.0, 1.1, 0.9, 1.0), _bar(1, 1.0, 1.2, 0.95, 1.15)))
    bearish = analyze_structure((_bar(0, 1.0, 1.1, 0.9, 1.0), _bar(1, 1.0, 1.05, 0.8, 0.85)))
    neutral = analyze_structure((_bar(0, 1.0, 1.1, 0.9, 1.0), _bar(1, 1.0, 1.1, 0.9, 1.0)))
    assert bullish.structure_bias == 'BULLISH'
    assert bearish.structure_bias == 'BEARISH'
    assert neutral.structure_bias == 'NEUTRAL'

def test_structure_break_of_structure_detection() -> None:
    break_up = analyze_structure((_bar(0, 1.1, 1.101, 1.099, 1.1), _bar(1, 1.1, 1.102, 1.0995, 1.101), _bar(2, 1.101, 1.103, 1.1, 1.104)))
    no_break = analyze_structure((_bar(0, 1.1, 1.101, 1.099, 1.1), _bar(1, 1.1, 1.102, 1.0995, 1.101), _bar(2, 1.101, 1.1015, 1.1002, 1.1012)))
    assert break_up.break_of_structure
    assert not no_break.break_of_structure
