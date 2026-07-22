from __future__ import annotations
from datetime import UTC, datetime
from uuid import uuid4
from checktrader import protocol_version
from checktrader.config.models import ExecutionConfig
from checktrader.domain.enums import OrderAction, ReasonCode
from checktrader.domain.models import Command, ManagementAction, Position, StrategySignal

def _command(action: OrderAction, symbol: str, payload: dict[str, object]) -> Command: return Command(uuid4().hex,action,symbol,protocol_version,datetime.now(UTC),payload)
def build_open(signal: StrategySignal, lot: float, config: ExecutionConfig) -> Command:
    return _command(OrderAction.OPEN,signal.symbol,{'action':'OPEN','side':signal.side.value,'lot':lot,'entry_price':signal.entry_price,'stop_loss':signal.stop_loss,'take_profit':signal.take_profit,'strategy':signal.strategy.value,'setup_id':signal.setup_id,'magic_number':config.magic_number,'reason':ReasonCode.ORDER_OPEN_BUILT.value})
def build_modify(position: Position, action: ManagementAction) -> Command:
    return _command(OrderAction.MODIFY,position.symbol,{'action':'MODIFY','position_id':position.position_id,'stop_loss':action.stop_loss,'take_profit':action.take_profit,'reason':ReasonCode.ORDER_MODIFY_BUILT.value})
def build_close(position: Position, action: ManagementAction) -> Command:
    return _command(OrderAction.CLOSE,position.symbol,{'action':'CLOSE','position_id':position.position_id,'close_fraction':action.close_fraction,'reason':ReasonCode.ORDER_CLOSE_BUILT.value})
