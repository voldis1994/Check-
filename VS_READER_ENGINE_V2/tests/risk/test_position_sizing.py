from __future__ import annotations

import pytest

from engine.protocol.constants import REASON_INVALID_VOLUME
from engine.protocol.errors import ValidationError
from engine.risk.position_sizing import (
    PositionSizingResult,
    calculate_position_size,
    compute_point_value_per_lot,
    compute_stop_loss_distance_points,
    normalize_volume_to_step,
)


def test_compute_stop_loss_distance_points_uses_point_dynamically() -> None:
    eur_distance = compute_stop_loss_distance_points(
        entry_price=1.10500,
        stop_loss=1.10000,
        point=0.00001,
    )
    jpy_distance = compute_stop_loss_distance_points(
        entry_price=110.500,
        stop_loss=110.000,
        point=0.001,
    )

    assert eur_distance == pytest.approx(500.0)
    assert jpy_distance == pytest.approx(500.0)


def test_compute_stop_loss_distance_points_returns_zero_when_prices_match() -> None:
    assert (
        compute_stop_loss_distance_points(
            entry_price=1.10000,
            stop_loss=1.10000,
            point=0.00001,
        )
        == 0.0
    )


def test_compute_stop_loss_distance_points_rejects_non_positive_point() -> None:
    with pytest.raises(ValidationError, match="point must be > 0"):
        compute_stop_loss_distance_points(entry_price=1.1, stop_loss=1.0, point=0.0)


def test_compute_point_value_per_lot_uses_formula_not_symbol_tables() -> None:
    five_digit = compute_point_value_per_lot(point=0.00001, units_per_lot=100_000.0)
    three_digit = compute_point_value_per_lot(point=0.001, units_per_lot=100_000.0)

    assert five_digit == pytest.approx(1.0)
    assert three_digit == pytest.approx(100.0)


def test_compute_point_value_per_lot_rejects_invalid_inputs() -> None:
    with pytest.raises(ValidationError, match="point must be > 0"):
        compute_point_value_per_lot(point=0.0, units_per_lot=100_000.0)
    with pytest.raises(ValidationError, match="units_per_lot must be > 0"):
        compute_point_value_per_lot(point=0.00001, units_per_lot=0.0)


def test_normalize_volume_to_step_rounds_down_to_step() -> None:
    assert normalize_volume_to_step(volume=0.237, volume_step=0.01) == pytest.approx(0.23)
    assert normalize_volume_to_step(volume=1.0, volume_step=0.1) == pytest.approx(1.0)


def test_normalize_volume_to_step_returns_zero_for_non_positive_volume() -> None:
    assert normalize_volume_to_step(volume=0.0, volume_step=0.01) == 0.0
    assert normalize_volume_to_step(volume=-1.0, volume_step=0.01) == 0.0


def test_normalize_volume_to_step_rejects_non_positive_step() -> None:
    with pytest.raises(ValidationError, match="volume_step must be > 0"):
        normalize_volume_to_step(volume=1.0, volume_step=0.0)


def test_calculate_position_size_returns_positive_volume_for_valid_inputs() -> None:
    result = calculate_position_size(
        equity=10_000.0,
        max_risk_per_trade_percent=1.0,
        entry_price=1.10500,
        stop_loss=1.10000,
        point=0.00001,
        pip=0.0001,
        volume_step=0.01,
    )

    assert isinstance(result, PositionSizingResult)
    assert result.allowed
    assert result.volume > 0.0
    assert result.reason is None
    assert result.volume == pytest.approx(0.20)


def test_calculate_position_size_blocks_when_volume_rounds_to_zero() -> None:
    result = calculate_position_size(
        equity=100.0,
        max_risk_per_trade_percent=0.1,
        entry_price=1.10500,
        stop_loss=1.10000,
        point=0.00001,
        pip=0.0001,
        volume_step=0.01,
    )

    assert not result.allowed
    assert result.volume == 0.0
    assert result.reason is not None
    assert REASON_INVALID_VOLUME in result.reason


def test_calculate_position_size_blocks_when_stop_loss_distance_is_zero() -> None:
    result = calculate_position_size(
        equity=10_000.0,
        max_risk_per_trade_percent=1.0,
        entry_price=1.10000,
        stop_loss=1.10000,
        point=0.00001,
        pip=0.0001,
        volume_step=0.01,
    )

    assert not result.allowed
    assert result.volume == 0.0
    assert result.reason is not None
    assert REASON_INVALID_VOLUME in result.reason


def test_calculate_position_size_blocks_for_non_positive_equity() -> None:
    result = calculate_position_size(
        equity=0.0,
        max_risk_per_trade_percent=1.0,
        entry_price=1.10500,
        stop_loss=1.10000,
        point=0.00001,
        pip=0.0001,
        volume_step=0.01,
    )

    assert not result.allowed
    assert result.volume == 0.0
    assert result.reason is not None
    assert REASON_INVALID_VOLUME in result.reason
