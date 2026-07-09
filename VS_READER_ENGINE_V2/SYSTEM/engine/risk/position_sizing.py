from __future__ import annotations

import math
from dataclasses import dataclass

from engine.reason import build_reason
from engine.protocol.constants import REASON_INVALID_VOLUME
from engine.protocol.errors import ValidationError

MODULE_NAME = "risk.position_sizing"


def _validation_error(message: str, **context: object) -> ValidationError:
    return ValidationError(message, module=MODULE_NAME, context=dict(context))


@dataclass(frozen=True)
class PositionSizingResult:
    allowed: bool
    volume: float
    reason: str | None


def compute_stop_loss_distance_points(
    *,
    entry_price: float,
    stop_loss: float,
    point: float,
) -> float:
    if point <= 0:
        raise _validation_error("point must be > 0", point=point)
    distance = abs(entry_price - stop_loss)
    if distance == 0:
        return 0.0
    return distance / point


def compute_point_value_per_lot(
    *,
    point: float,
    units_per_lot: float,
) -> float:
    if point <= 0:
        raise _validation_error("point must be > 0", point=point)
    if units_per_lot <= 0:
        raise _validation_error("units_per_lot must be > 0", units_per_lot=units_per_lot)
    return units_per_lot * point


def normalize_volume_to_step(*, volume: float, volume_step: float) -> float:
    if volume_step <= 0:
        raise _validation_error("volume_step must be > 0", volume_step=volume_step)
    if volume <= 0:
        return 0.0
    steps = math.floor(volume / volume_step + 1e-12)
    normalized = steps * volume_step
    return round(normalized, 10)


def calculate_position_size(
    *,
    equity: float,
    max_risk_per_trade_percent: float,
    entry_price: float,
    stop_loss: float,
    point: float,
    pip: float,
    volume_step: float,
    units_per_lot: float = 100_000.0,
) -> PositionSizingResult:
    if pip <= 0:
        raise _validation_error("pip must be > 0", pip=pip)
    if equity <= 0:
        return PositionSizingResult(
            allowed=False,
            volume=0.0,
            reason=build_reason(REASON_INVALID_VOLUME, "equity must be positive", equity=equity),
        )
    if max_risk_per_trade_percent <= 0:
        return PositionSizingResult(
            allowed=False,
            volume=0.0,
            reason=build_reason(
                REASON_INVALID_VOLUME,
                "max_risk_per_trade_percent must be positive",
                max_risk_per_trade_percent=max_risk_per_trade_percent,
            ),
        )

    stop_loss_distance_points = compute_stop_loss_distance_points(
        entry_price=entry_price,
        stop_loss=stop_loss,
        point=point,
    )
    if stop_loss_distance_points <= 0:
        return PositionSizingResult(
            allowed=False,
            volume=0.0,
            reason=build_reason(
                REASON_INVALID_VOLUME,
                "stop loss distance must be positive",
                entry_price=entry_price,
                stop_loss=stop_loss,
                point=point,
                pip=pip,
            ),
        )

    point_value_per_lot = compute_point_value_per_lot(point=point, units_per_lot=units_per_lot)
    risk_amount = equity * (max_risk_per_trade_percent / 100.0)
    raw_volume = risk_amount / (stop_loss_distance_points * point_value_per_lot)
    volume = normalize_volume_to_step(volume=raw_volume, volume_step=volume_step)
    if volume <= 0:
        return PositionSizingResult(
            allowed=False,
            volume=0.0,
            reason=build_reason(
                REASON_INVALID_VOLUME,
                "position volume rounded to zero",
                raw_volume=raw_volume,
                volume_step=volume_step,
            ),
        )

    return PositionSizingResult(allowed=True, volume=volume, reason=None)
