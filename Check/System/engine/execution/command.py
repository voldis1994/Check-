from __future__ import annotations
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import uuid4
from engine.protocol.constants import Decision, OrderAction, RiskResult, Side
from engine.protocol.errors import ValidationError
from engine.risk.trade_management import TradeManagementResult
if TYPE_CHECKING:
    from engine.decision.engine import DecisionResult
    from engine.risk.engine import RiskEngineResult
MODULE_NAME = 'execution.command'

def _validation_error(message: str, **context: object) -> ValidationError:
    return ValidationError(message, module=MODULE_NAME, context=dict(context))

@dataclass(frozen=True)
class OrderCommand:
    command_id: str
    action: str
    reason: str
    decision_id: str
    side: str | None = None
    volume: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    ticket: int | None = None
    order_comment: str | None = None

def _none_command(*, command_id: str, reason: str, decision_id: str) -> OrderCommand:
    return OrderCommand(command_id=command_id, action=OrderAction.NONE.value, reason=reason, decision_id=decision_id)

def _modify_command(*, command_id: str, ticket: int, side: str, stop_loss: float, take_profit: float, reason: str, decision_id: str) -> OrderCommand:
    if ticket < 0:
        raise _validation_error('modify command ticket must be >= 0', ticket=ticket)
    if side not in {Side.BUY.value, Side.SELL.value}:
        raise _validation_error('modify command side must be BUY or SELL', side=side)
    return OrderCommand(command_id=command_id, action=OrderAction.MODIFY.value, side=side, stop_loss=stop_loss, take_profit=take_profit, ticket=ticket, reason=reason, decision_id=decision_id)

def _close_command(*, command_id: str, ticket: int, side: str, volume: float, reason: str, decision_id: str) -> OrderCommand:
    if ticket < 0:
        raise _validation_error('close command ticket must be >= 0', ticket=ticket)
    if side not in {Side.BUY.value, Side.SELL.value}:
        raise _validation_error('close command side must be BUY or SELL', side=side)
    if volume <= 0:
        raise _validation_error('close command volume must be > 0', volume=volume)
    return OrderCommand(command_id=command_id, action=OrderAction.CLOSE.value, side=side, volume=volume, ticket=ticket, reason=reason, decision_id=decision_id)

def _open_command(*, command_id: str, side: str, volume: float, stop_loss: float, take_profit: float, reason: str, decision_id: str) -> OrderCommand:
    if side not in {Side.BUY.value, Side.SELL.value}:
        raise _validation_error('open command side must be BUY or SELL', side=side)
    if volume <= 0:
        raise _validation_error('open command volume must be > 0', volume=volume)
    from engine.execution.order_comment import build_open_order_comment
    return OrderCommand(command_id=command_id, action=OrderAction.OPEN.value, side=side, volume=volume, stop_loss=stop_loss, take_profit=take_profit, reason=reason, decision_id=decision_id, order_comment=build_open_order_comment(command_id))

def build_modify_order_command(*, ticket: int, side: str, stop_loss: float, take_profit: float, reason: str, decision_id: str, command_id: str | None=None) -> OrderCommand:
    return _modify_command(command_id=command_id or str(uuid4()), ticket=ticket, side=side, stop_loss=stop_loss, take_profit=take_profit, reason=reason, decision_id=decision_id)

def build_close_order_command(*, ticket: int, side: str, volume: float, reason: str, decision_id: str, command_id: str | None=None) -> OrderCommand:
    return _close_command(command_id=command_id or str(uuid4()), ticket=ticket, side=side, volume=volume, reason=reason, decision_id=decision_id)

def build_management_order_command(management_result: TradeManagementResult, *, ticket: int, side: str, decision_id: str, command_id: str | None=None) -> OrderCommand | None:
    if management_result.action == OrderAction.NONE.value:
        return None
    resolved_command_id = command_id or str(uuid4())
    if management_result.action == OrderAction.MODIFY.value:
        if management_result.stop_loss is None or management_result.take_profit is None:
            raise _validation_error('modify management result requires stop_loss and take_profit', action=management_result.action)
        return _modify_command(command_id=resolved_command_id, ticket=ticket, side=side, stop_loss=management_result.stop_loss, take_profit=management_result.take_profit, reason=management_result.reason, decision_id=decision_id)
    if management_result.action == OrderAction.CLOSE.value:
        if management_result.volume is None:
            raise _validation_error('close management result requires volume', action=management_result.action)
        return _close_command(command_id=resolved_command_id, ticket=ticket, side=side, volume=management_result.volume, reason=management_result.reason, decision_id=decision_id)
    raise _validation_error('unsupported trade management action for order command', action=management_result.action)

def resolve_order_command(decision_result: DecisionResult, risk_engine_result: RiskEngineResult, management_result: TradeManagementResult | None=None, *, ticket: int | None=None, side: str | None=None, command_id: str | None=None) -> OrderCommand:
    if management_result is not None and ticket is not None and (side is not None) and (management_result.action != OrderAction.NONE.value):
        management_command = build_management_order_command(management_result, ticket=ticket, side=side, decision_id=decision_result.decision_id, command_id=command_id)
        if management_command is not None:
            return management_command
    return build_order_command(decision_result, risk_engine_result, command_id=command_id)

def build_order_command(decision_result: DecisionResult, risk_engine_result: RiskEngineResult, *, command_id: str | None=None) -> OrderCommand:
    resolved_command_id = command_id or str(uuid4())
    if decision_result.decision in {Decision.WAIT.value, Decision.BLOCK.value}:
        return _none_command(command_id=resolved_command_id, reason=decision_result.reason, decision_id=decision_result.decision_id)
    if risk_engine_result.result != RiskResult.ALLOW.value:
        return _none_command(command_id=resolved_command_id, reason=risk_engine_result.reason or decision_result.reason, decision_id=decision_result.decision_id)
    if decision_result.decision not in {Decision.BUY.value, Decision.SELL.value}:
        return _none_command(command_id=resolved_command_id, reason=decision_result.reason, decision_id=decision_result.decision_id)
    if risk_engine_result.position_size is None or risk_engine_result.stop_loss is None or risk_engine_result.take_profit is None:
        return _none_command(command_id=resolved_command_id, reason=risk_engine_result.reason or 'risk allow missing trade levels', decision_id=decision_result.decision_id)
    side = decision_result.preferred_side
    if side not in {Side.BUY.value, Side.SELL.value}:
        return _none_command(command_id=resolved_command_id, reason=decision_result.reason, decision_id=decision_result.decision_id)
    return _open_command(command_id=resolved_command_id, side=side, volume=risk_engine_result.position_size, stop_loss=risk_engine_result.stop_loss, take_profit=risk_engine_result.take_profit, reason=decision_result.reason, decision_id=decision_result.decision_id)
