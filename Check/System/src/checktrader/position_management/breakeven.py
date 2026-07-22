"""Breakeven +0.20 net lock using tick_value / tick_size and fixed lot."""

from __future__ import annotations

from checktrader.domain.enums import Side
from checktrader.domain.money import SymbolSpecs, money_per_price_unit, round_price
from checktrader.observability.reason_codes import ReasonCode
from checktrader.risk.broker_constraints import round_price_to_tick


def calculate_be_stop_loss(
    *,
    side: Side,
    open_price: float,
    volume: float,
    specs: SymbolSpecs,
    be_net_profit_money: float,
    swap: float,
    commission: float,
) -> tuple[float | None, ReasonCode]:
    if specs.tick_size <= 0 or specs.tick_value <= 0 or volume <= 0:
        return None, ReasonCode.BE_PRICE_METADATA_MISSING
    required_gross = be_net_profit_money - swap - commission
    mppu = money_per_price_unit(tick_value=specs.tick_value, tick_size=specs.tick_size, volume=volume)
    distance = required_gross / mppu
    raw = open_price + distance if side is Side.BUY else open_price - distance
    return round_price(round_price_to_tick(raw, float(specs.tick_size)), specs.digits), ReasonCode.BE_CALCULATED
