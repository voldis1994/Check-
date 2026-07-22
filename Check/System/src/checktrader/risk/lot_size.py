"""Fixed-lot validation — never normalize to broker min/max/step."""

from __future__ import annotations

from dataclasses import dataclass

from checktrader.domain.money import SymbolSpecs
from checktrader.observability.reason_codes import ReasonCode


@dataclass(frozen=True, slots=True)
class LotValidation:
    ok: bool
    lot: float
    reason_code: ReasonCode
    requested_lot: float
    minimum_lot: float
    maximum_lot: float
    lot_step: float
    detail: str = ""


def _step_ok(lot: float, step: float) -> bool:
    if step <= 0:
        return False
    units = round(lot / step)
    return abs(units * step - lot) <= max(1e-12, step * 1e-9)


def validate_fixed_lot(specs: SymbolSpecs, fixed_lot: float) -> LotValidation:
    """Reject if broker cannot trade exactly ``fixed_lot`` (no auto-resize)."""
    requested = float(fixed_lot)
    minimum = float(specs.minimum_lot)
    maximum = float(specs.maximum_lot)
    step = float(specs.lot_step)
    if requested <= 0:
        return LotValidation(
            False,
            0.0,
            ReasonCode.FIXED_LOT_NOT_SUPPORTED,
            requested,
            minimum,
            maximum,
            step,
            "fixed_lot must be > 0",
        )
    if requested < minimum - 1e-12:
        return LotValidation(
            False,
            requested,
            ReasonCode.FIXED_LOT_NOT_SUPPORTED,
            requested,
            minimum,
            maximum,
            step,
            "below minimum_lot",
        )
    if requested > maximum + 1e-12:
        return LotValidation(
            False,
            requested,
            ReasonCode.FIXED_LOT_NOT_SUPPORTED,
            requested,
            minimum,
            maximum,
            step,
            "above maximum_lot",
        )
    if not _step_ok(requested, step):
        return LotValidation(
            False,
            requested,
            ReasonCode.FIXED_LOT_NOT_SUPPORTED,
            requested,
            minimum,
            maximum,
            step,
            "does not match lot_step",
        )
    return LotValidation(
        True,
        requested,
        ReasonCode.NONE,
        requested,
        minimum,
        maximum,
        step,
        "ok",
    )
