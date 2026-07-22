"""Broker stop/freeze and tick rounding helpers."""

from __future__ import annotations

from checktrader.domain.money import SymbolSpecs


def round_price_to_tick(price: float, tick_size: float) -> float:
    if tick_size <= 0:
        return float(price)
    units = round(float(price) / tick_size)
    return units * tick_size


def stop_level_price(specs: SymbolSpecs) -> float:
    return float(specs.stop_level_points) * float(specs.point)


def freeze_level_price(specs: SymbolSpecs) -> float:
    return float(specs.freeze_level_points) * float(specs.point)


def min_stop_distance(specs: SymbolSpecs) -> float:
    return max(stop_level_price(specs), freeze_level_price(specs))
