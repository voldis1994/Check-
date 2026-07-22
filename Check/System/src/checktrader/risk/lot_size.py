"""Lot sizing helpers (thin wrappers around risk.engine)."""

from __future__ import annotations

from checktrader.config.models import RiskConfig
from checktrader.domain.money import SymbolSpecs, money_per_price_unit


def normalize_lot(volume: float, specs: SymbolSpecs) -> float:
    steps = round(volume / specs.lot_step)
    return round(steps * specs.lot_step, 8)


def compute_raw_volume(
    *,
    risk: RiskConfig,
    equity: float,
    entry: float,
    stop_loss: float,
    specs: SymbolSpecs,
) -> float:
    if risk.sizing_mode == "fixed_lot":
        return float(risk.fixed_lot or 0.0)
    mppu = money_per_price_unit(tick_value=specs.tick_value, tick_size=specs.tick_size, volume=1.0)
    distance = abs(entry - stop_loss)
    risk_money = equity * float(risk.risk_percent or 0.0) / 100.0
    if distance * mppu <= 0:
        return 0.0
    return risk_money / (distance * mppu)


def maybe_normalize_lot(volume: float, specs: SymbolSpecs, *, allow: bool) -> float:
    if not allow:
        return volume
    return normalize_lot(volume, specs)


__all__ = ["normalize_lot", "compute_raw_volume", "maybe_normalize_lot"]
