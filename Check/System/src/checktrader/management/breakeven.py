from __future__ import annotations
from checktrader.config.models import ManagementConfig
from checktrader.domain.enums import Decision, OrderAction, ReasonCode, Side
from checktrader.domain.models import ManagementAction, Position, SymbolSpecs

def risk_per_unit(position: Position) -> float|None:
    if position.stop_loss is None: return None
    risk=abs(position.entry_price-position.stop_loss); return risk if risk>0.0 else None
def profit_r(position: Position, price: float) -> float|None:
    risk=risk_per_unit(position)
    if risk is None: return None
    move=price-position.entry_price if position.side==Side.LONG else position.entry_price-price
    return move/risk
def breakeven_action(position: Position, price: float, config: ManagementConfig, specs: SymbolSpecs) -> ManagementAction:
    rr=profit_r(position,price)
    if rr is None or rr<config.breakeven_trigger_rr: return ManagementAction(Decision.HOLD,ReasonCode.MANAGEMENT_NO_ACTION)
    target=position.entry_price+(config.breakeven_offset_points*specs.point if position.side==Side.LONG else -config.breakeven_offset_points*specs.point)
    if position.stop_loss is None or (position.side==Side.LONG and target>position.stop_loss) or (position.side==Side.SHORT and target<position.stop_loss): return ManagementAction(Decision.MODIFY,ReasonCode.BREAKEVEN_MOVE,OrderAction.MODIFY,stop_loss=target)
    return ManagementAction(Decision.HOLD,ReasonCode.MANAGEMENT_NO_ACTION)
