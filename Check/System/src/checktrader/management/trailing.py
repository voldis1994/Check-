"""Trailing — ATR-adaptive lock/start (same on every symbol)."""

from __future__ import annotations

from checktrader.config.models import ManagementConfig
from checktrader.domain.enums import Decision, MarketRegime, OrderAction, ReasonCode, Side
from checktrader.domain.models import ManagementAction, Position, SymbolSpecs
from checktrader.management.atr_stops import trail_lock_distance, trail_start_distance


def trailing_action(
    position: Position,
    price: float,
    atr_value: float | None,
    regime: MarketRegime,
    config: ManagementConfig,
    specs: SymbolSpecs,
) -> ManagementAction:
    del regime
    if atr_value is None or atr_value <= 0:
        return ManagementAction(Decision.HOLD, ReasonCode.MANAGEMENT_NO_ACTION)
    lock = trail_lock_distance(specs, config, atr_value, mid=price)
    start = trail_start_distance(specs, config, atr_value, mid=price)
    if lock <= 0:
        return ManagementAction(Decision.HOLD, ReasonCode.MANAGEMENT_NO_ACTION)
    need = max(start, lock)
    tick = specs.point if specs.point > 0 else atr_value * 0.01

    if position.side == Side.BUY:
        profit = price - position.entry_price
        if profit + 1e-12 < need:
            return ManagementAction(Decision.HOLD, ReasonCode.MANAGEMENT_NO_ACTION)
        candidate = price - lock
        if position.stop_loss is None or candidate > position.stop_loss + tick:
            return ManagementAction(Decision.MODIFY, ReasonCode.TRAILING_MOVE, OrderAction.MODIFY, stop_loss=candidate)
        return ManagementAction(Decision.HOLD, ReasonCode.MANAGEMENT_NO_ACTION)

    profit = position.entry_price - price
    if profit + 1e-12 < need:
        return ManagementAction(Decision.HOLD, ReasonCode.MANAGEMENT_NO_ACTION)
    candidate = price + lock
    if position.stop_loss is None or candidate < position.stop_loss - tick:
        return ManagementAction(Decision.MODIFY, ReasonCode.TRAILING_MOVE, OrderAction.MODIFY, stop_loss=candidate)
    return ManagementAction(Decision.HOLD, ReasonCode.MANAGEMENT_NO_ACTION)
