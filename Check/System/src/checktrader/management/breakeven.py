"""Breakeven — ATR profit gate (not RR against a tiny structural stop)."""

from __future__ import annotations

from checktrader.config.models import ManagementConfig
from checktrader.domain.enums import Decision, OrderAction, ReasonCode, Side
from checktrader.domain.models import ManagementAction, Position, SymbolSpecs
from checktrader.management.atr_stops import atr_distance


def risk_per_unit(position: Position) -> float | None:
    if position.stop_loss is None:
        return None
    risk = abs(position.entry_price - position.stop_loss)
    return risk if risk > 0.0 else None


def profit_r(position: Position, price: float) -> float | None:
    risk = risk_per_unit(position)
    if risk is None:
        return None
    move = price - position.entry_price if position.side == Side.BUY else position.entry_price - price
    return move / risk


def _side_profit(position: Position, price: float) -> float:
    if position.side == Side.BUY:
        return price - position.entry_price
    return position.entry_price - price


def breakeven_action(
    position: Position, price: float, config: ManagementConfig, specs: SymbolSpecs, atr_value: float | None = None
) -> ManagementAction:
    profit = _side_profit(position, price)

    # Prefer ATR trigger so a 100-point SL does not wait forever, and a tight SL
    # does not snap to BE after 2 points.
    if atr_value is not None and atr_value > 0 and config.breakeven_trigger_atr > 0:
        if profit < atr_distance(atr_value, config.breakeven_trigger_atr):
            return ManagementAction(Decision.HOLD, ReasonCode.MANAGEMENT_NO_ACTION)
        offset = atr_distance(atr_value, config.breakeven_offset_atr)
    else:
        rr = profit_r(position, price)
        if rr is None or rr < config.breakeven_trigger_rr:
            return ManagementAction(Decision.HOLD, ReasonCode.MANAGEMENT_NO_ACTION)
        risk = risk_per_unit(position) or (specs.point * 10.0)
        offset = max(risk * 0.05, specs.point)

    target = position.entry_price + offset if position.side == Side.BUY else position.entry_price - offset
    if position.stop_loss is None:
        return ManagementAction(Decision.MODIFY, ReasonCode.BREAKEVEN_MOVE, OrderAction.MODIFY, stop_loss=target)
    if position.side == Side.BUY and target > position.stop_loss:
        return ManagementAction(Decision.MODIFY, ReasonCode.BREAKEVEN_MOVE, OrderAction.MODIFY, stop_loss=target)
    if position.side == Side.SELL and target < position.stop_loss:
        return ManagementAction(Decision.MODIFY, ReasonCode.BREAKEVEN_MOVE, OrderAction.MODIFY, stop_loss=target)
    return ManagementAction(Decision.HOLD, ReasonCode.MANAGEMENT_NO_ACTION)
