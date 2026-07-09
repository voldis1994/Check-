from __future__ import annotations
from datetime import datetime, timezone
from engine.analysis.pressure import analyze_pressure
from engine.normalizer.market_normalizer import NormalizedMarketBar

def _bar(index: int, open_: float, high: float, low: float, close: float) -> NormalizedMarketBar:
    return NormalizedMarketBar(time_utc=datetime(2026, 7, 7, 6, index, tzinfo=timezone.utc), open=open_, high=high, low=low, close=close, volume=100.0, symbol='EURUSD', timeframe='M1', digits=5, point=1e-05, bar_index=index)

def test_pressure_values_are_in_zero_to_one_range() -> None:
    result = analyze_pressure((_bar(0, 1.1, 1.101, 1.099, 1.1008), _bar(1, 1.1008, 1.102, 1.1, 1.1017), _bar(2, 1.1017, 1.1025, 1.101, 1.1011)))
    assert 0.0 <= result.buy_pressure <= 1.0
    assert 0.0 <= result.sell_pressure <= 1.0

def test_pressure_delta_is_buy_minus_sell() -> None:
    result = analyze_pressure((_bar(0, 1.1, 1.102, 1.099, 1.1015), _bar(1, 1.1015, 1.103, 1.1005, 1.1025)))
    assert result.pressure_delta == result.buy_pressure - result.sell_pressure

def test_absorption_detected_is_boolean() -> None:
    result = analyze_pressure((_bar(0, 1.1, 1.104, 1.096, 1.1002), _bar(1, 1.1002, 1.1035, 1.097, 1.1001)))
    assert isinstance(result.absorption_detected, bool)
