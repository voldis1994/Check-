from __future__ import annotations

from pathlib import Path

from engine.validator.sensor_validator import validate_sensor_csv


FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_sensor_validator_fixture_sensor_valid_csv_is_valid() -> None:
    raw_text = (FIXTURES_DIR / "sensor_valid.csv").read_text(encoding="utf-8")
    result = validate_sensor_csv(raw_text)
    assert result.is_valid
    assert result.row_count == 3
    assert result.errors == ()


def test_sensor_validator_ask_greater_or_equal_bid_valid() -> None:
    raw_text = """time_utc,bid,ask,spread,spread_points,symbol,digits,point
2026-07-07T06:00:00.000Z,1.08500,1.08520,0.00020,20,EURUSD,5,0.00001
"""
    result = validate_sensor_csv(raw_text)
    assert result.is_valid
    assert result.row_count == 1


def test_sensor_validator_spread_equals_ask_minus_bid_valid() -> None:
    raw_text = """time_utc,bid,ask,spread,spread_points,symbol,digits,point
2026-07-07T06:00:00.000Z,1.10000,1.10030,0.00030,30,EURUSD,5,0.00001
"""
    result = validate_sensor_csv(raw_text)
    assert result.is_valid
    assert result.errors == ()


def test_sensor_validator_negative_spread_invalid() -> None:
    raw_text = """time_utc,bid,ask,spread,spread_points,symbol,digits,point
2026-07-07T06:00:00.000Z,1.10020,1.10010,-0.00010,-10,EURUSD,5,0.00001
"""
    result = validate_sensor_csv(raw_text)
    assert not result.is_valid
    assert any("ask must be >= bid" in error for error in result.errors)


def test_sensor_validator_spread_points_mismatch_invalid() -> None:
    raw_text = """time_utc,bid,ask,spread,spread_points,symbol,digits,point
2026-07-07T06:00:00.000Z,1.10000,1.10020,0.00020,99,EURUSD,5,0.00001
"""
    result = validate_sensor_csv(raw_text)
    assert not result.is_valid
    assert any("spread_points must equal spread / point" in error for error in result.errors)
