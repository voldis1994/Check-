from __future__ import annotations
import math
import pytest
from engine.normalizer.spread_model import update_spread_model, update_spread_model_from_sensor
from engine.protocol.models import SensorReading

def test_update_spread_model_computes_relative_spread() -> None:
    snapshot = update_spread_model((0.0001, 0.0002, 0.0003), current_spread=0.0004, lookback_bars=10)
    assert snapshot.sample_count == 4
    assert snapshot.mean_spread == pytest.approx(0.00025)
    assert snapshot.std_spread == pytest.approx(math.sqrt(1.25e-08))
    assert snapshot.median_spread == pytest.approx(0.00025)
    expected_relative = (0.0004 - snapshot.mean_spread) / snapshot.std_spread
    assert snapshot.relative_spread == pytest.approx(expected_relative)

def test_update_spread_model_has_no_hard_limits() -> None:
    snapshot = update_spread_model((0.0001, 0.00011, 0.00012), current_spread=0.01, lookback_bars=10)
    assert snapshot.current_spread == pytest.approx(0.01)
    assert snapshot.relative_spread > 0

def test_update_spread_model_limits_history_by_lookback_bars() -> None:
    snapshot = update_spread_model((0.0001, 0.0002, 0.0003, 0.0004), current_spread=0.0005, lookback_bars=3)
    assert snapshot.history == pytest.approx((0.0003, 0.0004, 0.0005))
    assert snapshot.sample_count == 3

def test_update_spread_model_from_sensor_updates_model() -> None:
    sensor = SensorReading(time_utc='2026-07-07T06:00:00.000Z', bid=1.1, ask=1.1002, spread=0.0002, spread_points=20.0, symbol='EURUSD', digits=5, point=1e-05)
    snapshot = update_spread_model_from_sensor((0.0001, 0.00015), sensor, lookback_bars=5)
    assert snapshot.history == pytest.approx((0.0001, 0.00015, 0.0002))
    assert snapshot.current_spread == pytest.approx(sensor.spread)
