from __future__ import annotations

from datetime import datetime, timezone

from engine.decision.filters.volatility_filter import (
    calculate_relative_volatility,
    evaluate_volatility_filter,
)
from engine.normalizer.market_normalizer import NormalizedMarketBar


def _bar(
    *,
    bar_index: int,
    open_price: float,
    high: float,
    low: float,
    close: float,
) -> NormalizedMarketBar:
    return NormalizedMarketBar(
        time_utc=datetime(2026, 1, 1, 0, bar_index, tzinfo=timezone.utc),
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=1.0,
        symbol="EURUSD",
        timeframe="M1",
        digits=5,
        point=0.00001,
        bar_index=bar_index,
    )


def test_calculate_relative_volatility_uses_atr_equivalent_over_lookback() -> None:
    bars = (
        _bar(bar_index=0, open_price=1.1000, high=1.1010, low=1.0990, close=1.1005),
        _bar(bar_index=1, open_price=1.1005, high=1.1010, low=1.0995, close=1.1000),
        _bar(bar_index=2, open_price=1.1000, high=1.1010, low=1.0990, close=1.1005),
        _bar(bar_index=3, open_price=1.1005, high=1.1020, low=1.0990, close=1.1015),
    )

    relative_volatility = calculate_relative_volatility(bars, lookback_bars=3)

    assert relative_volatility > 1.0


def test_calculate_relative_volatility_is_near_one_for_uniform_bars() -> None:
    bars = tuple(
        _bar(bar_index=index, open_price=1.1000, high=1.1010, low=1.0990, close=1.1005)
        for index in range(5)
    )

    relative_volatility = calculate_relative_volatility(bars, lookback_bars=5)

    assert relative_volatility == 1.0


def test_calculate_relative_volatility_returns_zero_for_empty_bars() -> None:
    assert calculate_relative_volatility((), lookback_bars=10) == 0.0


def test_volatility_acceptable_is_based_on_relative_threshold() -> None:
    acceptable = evaluate_volatility_filter(relative_volatility=1.2, threshold=1.5)
    rejected = evaluate_volatility_filter(relative_volatility=1.7, threshold=1.5)

    assert acceptable.volatility_acceptable
    assert not rejected.volatility_acceptable


def test_no_hard_symbol_specific_thresholds_used() -> None:
    very_high_relative = evaluate_volatility_filter(relative_volatility=999.0, threshold=1000.0)

    assert very_high_relative.volatility_acceptable
    assert very_high_relative.reason is None


def test_volatility_abnormal_reason_is_generated() -> None:
    result = evaluate_volatility_filter(relative_volatility=2.2, threshold=1.8)

    assert not result.volatility_acceptable
    assert result.reason is not None
    assert "VOLATILITY_ABNORMAL" in result.reason
