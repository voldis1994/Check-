"""Breakeven — digit-aware points/pips trigger (not RR against wrong digit math)."""

from __future__ import annotations

from checktrader.config.models import ManagementConfig
from checktrader.domain.enums import Decision, OrderAction, ReasonCode, Side
from checktrader.domain.models import ManagementAction, Position, SymbolSpecs
from checktrader.management.atr_stops import atr_distance, breakeven_trigger_distance, pip_size


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
    need = breakeven_trigger_distance(specs, config, atr_value)
    if need > 0:
        if profit < need:
            return ManagementAction(Decision.HOLD, ReasonCode.MANAGEMENT_NO_ACTION)
        if atr_value is not None and atr_value > 0:
            offset = atr_distance(atr_value, config.breakeven_offset_atr)
        else:
            offset = max(pip_size(specs) * 0.5, specs.point)
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
