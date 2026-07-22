from __future__ import annotations
from checktrader.domain.enums import Decision, OrderAction, ReasonCode, Side
from checktrader.domain.models import ManagementAction, Position

def take_profit_action(position: Position, bid: float, ask: float) -> ManagementAction:
    if position.take_profit is None: return ManagementAction(Decision.HOLD,ReasonCode.MANAGEMENT_NO_ACTION)
    if position.side==Side.LONG and bid>=position.take_profit: return ManagementAction(Decision.CLOSE,ReasonCode.TAKE_PROFIT_HIT,OrderAction.CLOSE,close_fraction=1.0)
    if position.side==Side.SHORT and ask<=position.take_profit: return ManagementAction(Decision.CLOSE,ReasonCode.TAKE_PROFIT_HIT,OrderAction.CLOSE,close_fraction=1.0)
    return ManagementAction(Decision.HOLD,ReasonCode.MANAGEMENT_NO_ACTION)
