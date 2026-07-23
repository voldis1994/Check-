from __future__ import annotations

from checktrader.config.models import ManagementConfig
from checktrader.domain.enums import Decision, OrderAction, ReasonCode, Side
from checktrader.domain.models import ManagementAction, Position, SymbolSpecs


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


def breakeven_action(
    position: Position, price: float, config: ManagementConfig, specs: SymbolSpecs, atr_value: float | None = None
) -> ManagementAction:
    rr = profit_r(position, price)
    if rr is None or rr < config.breakeven_trigger_rr:
        return ManagementAction(Decision.HOLD, ReasonCode.MANAGEMENT_NO_ACTION)
    # ATR offset (cross-market). Fallback to a tiny fraction of risk if ATR missing.
    if atr_value is not None and atr_value > 0:
        offset = config.breakeven_offset_atr * atr_value
    else:
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
