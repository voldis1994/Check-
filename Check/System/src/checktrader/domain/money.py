"""Money and price helpers — instrument-agnostic (tick/point/digits)."""

from __future__ import annotations

from dataclasses import dataclass

from checktrader.domain.enums import Side


@dataclass(frozen=True, slots=True)
class SymbolSpecs:
    """Broker symbol contract. Canonical distance unit is tick_size, not pip."""

    symbol: str
    digits: int
    point: float
    tick_size: float
    tick_value: float
    minimum_lot: float
    maximum_lot: float
    lot_step: float
    stop_level_points: int
    freeze_level_points: int
    # Legacy display field only — never use for strategy/risk distances.
    # Defaults to tick_size when broker does not define a Forex-style pip.
    pip_size: float = 0.0

    def __post_init__(self) -> None:
        if self.pip_size <= 0 and self.tick_size > 0:
            object.__setattr__(self, "pip_size", float(self.tick_size))


def price_tolerance(*, point: float, digits: int, points: int = 2) -> float:
    digit_eps = 10 ** (-digits) if digits > 0 else 0.0
    return max(point * max(points, 1), digit_eps, 1e-12)


def round_price(price: float, digits: int) -> float:
    return round(float(price), int(digits))


def money_per_price_unit(*, tick_value: float, tick_size: float, volume: float) -> float:
    if tick_value <= 0 or tick_size <= 0 or volume <= 0:
        raise ValueError("tick_value, tick_size and volume must be > 0")
    return (tick_value / tick_size) * volume


def compute_net_profit(*, profit: float, swap: float, commission: float) -> float:
    return float(profit) + float(swap) + float(commission)


def sl_improves(*, side: Side, current_sl: float, proposed_sl: float, tolerance: float) -> bool:
    if current_sl <= 0 and proposed_sl > 0:
        return True
    if side is Side.BUY:
        return proposed_sl > current_sl + tolerance
    return proposed_sl < current_sl - tolerance


def spread_price(*, bid: float, ask: float) -> float:
    if bid <= 0 or ask <= 0 or ask < bid:
        return 0.0
    return float(ask) - float(bid)


def spread_ticks(*, bid: float, ask: float, tick_size: float) -> float:
    price = spread_price(bid=bid, ask=ask)
    if tick_size <= 0 or price <= 0:
        return 0.0
    return price / tick_size


def spread_points(*, bid: float, ask: float, point: float) -> float:
    price = spread_price(bid=bid, ask=ask)
    if point <= 0 or price <= 0:
        return 0.0
    return price / point
