from __future__ import annotations

import pytest

from engine.normalizer.instrument_params import (
    InstrumentParams,
    calculate_pip,
    derive_instrument_params,
    detect_params_change,
)
from engine.normalizer.market_normalizer import normalize_market_csv
from engine.protocol.errors import ValidationError


def test_calculate_pip_for_five_digits_uses_point_times_ten() -> None:
    assert calculate_pip(point=0.00001, digits=5) == 0.0001


def test_calculate_pip_for_four_digits_uses_point() -> None:
    assert calculate_pip(point=0.0001, digits=4) == 0.0001


def test_derive_instrument_params_from_first_valid_market_row() -> None:
    raw_text = """time_utc,open,high,low,close,volume,symbol,timeframe,digits,point
2026-07-07T06:00:00.000Z,1.10000,1.10100,1.09900,1.10050,100,EURUSD,M1,5,0.00001
2026-07-07T06:01:00.000Z,1.10050,1.10150,1.10000,1.10100,120,EURUSD,M1,5,0.00001
"""
    bars = normalize_market_csv(raw_text)
    params = derive_instrument_params(bars)

    assert params == InstrumentParams(symbol="EURUSD", digits=5, point=0.00001, pip=0.0001)


def test_derive_instrument_params_raises_when_bars_are_empty() -> None:
    with pytest.raises(ValidationError, match="market bars are required"):
        derive_instrument_params(())


def test_detect_params_change_when_digits_or_point_changed() -> None:
    current = InstrumentParams(symbol="EURUSD", digits=5, point=0.00001, pip=0.0001)
    incoming_changed_digits = InstrumentParams(symbol="EURUSD", digits=4, point=0.0001, pip=0.0001)
    incoming_changed_point = InstrumentParams(symbol="EURUSD", digits=5, point=0.0001, pip=0.001)
    incoming_same = InstrumentParams(symbol="EURUSD", digits=5, point=0.00001, pip=0.0001)

    assert detect_params_change(current, incoming_changed_digits)
    assert detect_params_change(current, incoming_changed_point)
    assert not detect_params_change(current, incoming_same)
