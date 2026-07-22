"""High-lock: protect a ratio of peak net profit (snapped to ATR grid)."""

from __future__ import annotations

from checktrader.config.models import HighLockConfig
from checktrader.domain.enums import Side
from checktrader.domain.money import SymbolSpecs, money_per_price_unit, round_price
from checktrader.position_management.atr_grid_trailing import snap_to_reached_grid
from checktrader.risk.broker_constraints import round_price_to_tick


def calculate_high_lock_sl(
    *,
    side: Side,
    open_price: float,
    volume: float,
    specs: SymbolSpecs,
    peak_net_profit: float,
    swap: float,
    commission: float,
    config: HighLockConfig,
    be_anchor: float | None,
    atr: float,
    trailing_step_atr: float,
    tolerance: float,
) -> float | None:
    if not config.enabled:
        return None
    if peak_net_profit < config.activation_peak_profit_money:
        return None
    if specs.tick_size <= 0 or specs.tick_value <= 0:
        return None
    locked = peak_net_profit * config.lock_ratio
    required_gross = locked - swap - commission
    mppu = money_per_price_unit(tick_value=specs.tick_value, tick_size=specs.tick_size, volume=volume)
    distance = required_gross / mppu
    raw = open_price + distance if side is Side.BUY else open_price - distance
    raw = round_price(round_price_to_tick(raw, float(specs.tick_size)), specs.digits)
    if be_anchor is None:
        return raw
    return snap_to_reached_grid(
        side=side,
        anchor_sl=be_anchor,
        proposed_sl=raw,
        atr=atr,
        trailing_step_atr=trailing_step_atr,
        specs=specs,
        tolerance=tolerance,
    )
