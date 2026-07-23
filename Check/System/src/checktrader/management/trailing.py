"""ATR trailing stop — lock and start gates are ATR-only.

Points/pips are just ATR·mult / point (see atr_stops.py). Example:
  trailing_lock_atr=1.0, ATR=0.04, point=0.001 → lock = 40 NATURALGAS points
  trailing_lock_atr=1.0, ATR=0.0008, point=0.00001 → lock ≈ 8 pips
"""

from __future__ import annotations

from checktrader.config.models import ManagementConfig
from checktrader.domain.enums import Decision, MarketRegime, OrderAction, ReasonCode, Side
from checktrader.domain.models import ManagementAction, Position
from checktrader.management.atr_stops import atr_distance


def trail_lock_distance(atr_value: float, config: ManagementConfig) -> float:
    return atr_distance(atr_value, config.trailing_lock_atr)


def trail_start_distance(atr_value: float, config: ManagementConfig) -> float:
    """Profit needed before trailing begins (ATR), never RR-on-tiny-SL."""
    return atr_distance(atr_value, config.trailing_start_atr)


def trailing_action(
    position: Position, price: float, atr_value: float | None, regime: MarketRegime, config: ManagementConfig
) -> ManagementAction:
    del regime
    if atr_value is None or atr_value <= 0:
        return ManagementAction(Decision.HOLD, ReasonCode.MANAGEMENT_NO_ACTION)

    lock = trail_lock_distance(atr_value, config)
    start = trail_start_distance(atr_value, config)
    # Need enough room that candidate sits past entry (or at least past current SL).
    need = max(start, lock)

    if position.side == Side.BUY:
        profit = price - position.entry_price
        if profit < need:
            return ManagementAction(Decision.HOLD, ReasonCode.MANAGEMENT_NO_ACTION)
        candidate = price - lock
        if position.stop_loss is None or candidate > position.stop_loss + (atr_value * 0.01):
            return ManagementAction(Decision.MODIFY, ReasonCode.TRAILING_MOVE, OrderAction.MODIFY, stop_loss=candidate)
        return ManagementAction(Decision.HOLD, ReasonCode.MANAGEMENT_NO_ACTION)

    profit = position.entry_price - price
    if profit < need:
        return ManagementAction(Decision.HOLD, ReasonCode.MANAGEMENT_NO_ACTION)
    candidate = price + lock
    if position.stop_loss is None or candidate < position.stop_loss - (atr_value * 0.01):
        return ManagementAction(Decision.MODIFY, ReasonCode.TRAILING_MOVE, OrderAction.MODIFY, stop_loss=candidate)
    return ManagementAction(Decision.HOLD, ReasonCode.MANAGEMENT_NO_ACTION)
