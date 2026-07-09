from __future__ import annotations

import pytest

from engine.protocol.constants import REASON_DATA_INVALID, REASON_MISSING_TAKE_PROFIT, Side
from engine.protocol.errors import ValidationError
from engine.risk.sl_tp import (
    SlTpValidationResult,
    calculate_take_profit,
    compute_stop_loss_distance_pips,
    validate_buy_stop_loss_placement,
    validate_sell_stop_loss_placement,
    validate_sl_tp,
    validate_stop_loss_within_max_pips,
    validate_take_profit_direction,
    validate_take_profit_present,
)


def test_compute_stop_loss_distance_pips_uses_pip_relative_to_instrument() -> None:
    eur_pips = compute_stop_loss_distance_pips(
        entry_price=1.10500,
        stop_loss=1.10000,
        pip=0.0001,
    )
    jpy_pips = compute_stop_loss_distance_pips(
        entry_price=110.500,
        stop_loss=110.000,
        pip=0.01,
    )

    assert eur_pips == pytest.approx(50.0)
    assert jpy_pips == pytest.approx(50.0)


def test_compute_stop_loss_distance_pips_rejects_non_positive_pip() -> None:
    with pytest.raises(ValidationError, match="pip must be > 0"):
        compute_stop_loss_distance_pips(entry_price=1.1, stop_loss=1.0, pip=0.0)


def test_validate_buy_stop_loss_placement_requires_sl_below_swing_low() -> None:
    assert (
        validate_buy_stop_loss_placement(
            entry_price=1.10500,
            stop_loss=1.09980,
            swing_low=1.10000,
        )
        is None
    )
    reason = validate_buy_stop_loss_placement(
        entry_price=1.10500,
        stop_loss=1.10050,
        swing_low=1.10000,
    )
    assert reason is not None
    assert REASON_DATA_INVALID in reason


def test_validate_sell_stop_loss_placement_requires_sl_above_swing_high() -> None:
    assert (
        validate_sell_stop_loss_placement(
            entry_price=1.10000,
            stop_loss=1.10520,
            swing_high=1.10500,
        )
        is None
    )
    reason = validate_sell_stop_loss_placement(
        entry_price=1.10000,
        stop_loss=1.10450,
        swing_high=1.10500,
    )
    assert reason is not None
    assert REASON_DATA_INVALID in reason


def test_calculate_take_profit_uses_reward_ratio_for_buy_and_sell() -> None:
    buy_tp = calculate_take_profit(
        side=Side.BUY.value,
        entry_price=1.10500,
        stop_loss=1.10000,
        reward_ratio=2.0,
        digits=5,
    )
    sell_tp = calculate_take_profit(
        side=Side.SELL.value,
        entry_price=1.10000,
        stop_loss=1.10500,
        reward_ratio=2.0,
        digits=5,
    )

    assert buy_tp == pytest.approx(1.11500)
    assert sell_tp == pytest.approx(1.09000)


def test_calculate_take_profit_rejects_invalid_reward_ratio() -> None:
    with pytest.raises(ValidationError, match="reward_ratio must be > 0"):
        calculate_take_profit(
            side=Side.BUY.value,
            entry_price=1.1,
            stop_loss=1.0,
            reward_ratio=0.0,
            digits=5,
        )


def test_validate_take_profit_present_blocks_missing_take_profit() -> None:
    reason = validate_take_profit_present(take_profit=None)
    assert reason is not None
    assert REASON_MISSING_TAKE_PROFIT in reason

    zero_reason = validate_take_profit_present(take_profit=0.0)
    assert zero_reason is not None
    assert REASON_MISSING_TAKE_PROFIT in zero_reason


def test_validate_take_profit_direction_enforces_side_specific_levels() -> None:
    assert (
        validate_take_profit_direction(
            side=Side.BUY.value,
            entry_price=1.10000,
            take_profit=1.11000,
        )
        is None
    )
    assert (
        validate_take_profit_direction(
            side=Side.SELL.value,
            entry_price=1.10000,
            take_profit=1.09000,
        )
        is None
    )

    buy_reason = validate_take_profit_direction(
        side=Side.BUY.value,
        entry_price=1.10000,
        take_profit=1.09000,
    )
    assert buy_reason is not None
    assert REASON_DATA_INVALID in buy_reason


def test_validate_stop_loss_within_max_pips_blocks_wide_stops() -> None:
    assert (
        validate_stop_loss_within_max_pips(
            entry_price=1.10500,
            stop_loss=1.10000,
            pip=0.0001,
            max_stop_loss_pips=50.0,
        )
        is None
    )
    reason = validate_stop_loss_within_max_pips(
        entry_price=1.10500,
        stop_loss=1.09500,
        pip=0.0001,
        max_stop_loss_pips=50.0,
    )
    assert reason is not None
    assert REASON_DATA_INVALID in reason
    assert "max_stop_loss_pips" in reason


def test_validate_sl_tp_allows_valid_buy_levels() -> None:
    result = validate_sl_tp(
        side=Side.BUY.value,
        entry_price=1.10500,
        stop_loss=1.09980,
        take_profit=1.11540,
        swing_low=1.10000,
        swing_high=1.10600,
        pip=0.0001,
        max_stop_loss_pips=60.0,
    )

    assert isinstance(result, SlTpValidationResult)
    assert result.allowed
    assert result.stop_loss == 1.09980
    assert result.take_profit == 1.11540
    assert result.reason is None


def test_validate_sl_tp_blocks_missing_take_profit() -> None:
    result = validate_sl_tp(
        side=Side.BUY.value,
        entry_price=1.10500,
        stop_loss=1.09980,
        take_profit=None,
        swing_low=1.10000,
        swing_high=1.10600,
        pip=0.0001,
        max_stop_loss_pips=60.0,
    )

    assert not result.allowed
    assert result.reason is not None
    assert REASON_MISSING_TAKE_PROFIT in result.reason
