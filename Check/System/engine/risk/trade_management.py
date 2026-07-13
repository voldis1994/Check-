from __future__ import annotations
from dataclasses import dataclass
from engine.protocol.constants import OrderAction, Side
from engine.protocol.errors import ValidationError
from engine.risk.position_sizing import normalize_volume_to_step
MODULE_NAME = 'risk.trade_management'

def _validation_error(message: str, **context: object) -> ValidationError:
    return ValidationError(message, module=MODULE_NAME, context=dict(context))

def _round_price(price: float, digits: int) -> float:
    return round(price, digits)

@dataclass(frozen=True)
class TradeManagementConfig:
    breakeven_progress_ratio: float
    trailing_buffer: float
    partial_close_progress_ratio: float
    partial_close_volume_ratio: float
    time_stop_max_bars: int
    volume_step: float

@dataclass(frozen=True)
class OpenPosition:
    ticket: int
    side: str
    entry_price: float
    stop_loss: float
    take_profit: float
    volume: float
    bars_open: int
    partial_close_applied: bool = False

@dataclass(frozen=True)
class TradeManagementResult:
    action: str
    reason: str
    stop_loss: float | None = None
    take_profit: float | None = None
    volume: float | None = None

def _no_action() -> TradeManagementResult:
    return TradeManagementResult(action=OrderAction.NONE.value, reason='')

def _gate_close_action(result: TradeManagementResult, *, allow_close: bool) -> TradeManagementResult:
    if result.action == OrderAction.CLOSE.value and (not allow_close):
        return TradeManagementResult(action=OrderAction.NONE.value, reason='trade_management_close_disabled: exit only via SL/TP')
    return result

def compute_progress_to_take_profit(*, side: str, entry_price: float, take_profit: float, current_price: float) -> float:
    if side == Side.BUY.value:
        distance = take_profit - entry_price
        if distance <= 0:
            return 0.0
        progress = (current_price - entry_price) / distance
    elif side == Side.SELL.value:
        distance = entry_price - take_profit
        if distance <= 0:
            return 0.0
        progress = (entry_price - current_price) / distance
    else:
        raise _validation_error('side must be BUY or SELL', side=side)
    return max(0.0, min(progress, 1.0))

def evaluate_breakeven(*, position: OpenPosition, current_price: float, breakeven_progress_ratio: float, digits: int) -> TradeManagementResult | None:
    if breakeven_progress_ratio <= 0:
        return None
    progress = compute_progress_to_take_profit(side=position.side, entry_price=position.entry_price, take_profit=position.take_profit, current_price=current_price)
    if progress < breakeven_progress_ratio:
        return None
    if position.side == Side.BUY.value:
        if position.stop_loss >= position.entry_price:
            return None
        new_stop_loss = _round_price(position.entry_price, digits)
        if new_stop_loss >= current_price:
            return None
        return TradeManagementResult(action=OrderAction.MODIFY.value, reason='TRADE_MANAGEMENT_BREAKEVEN: stop loss moved to entry', stop_loss=new_stop_loss, take_profit=position.take_profit)
    if position.side == Side.SELL.value:
        if position.stop_loss <= position.entry_price:
            return None
        new_stop_loss = _round_price(position.entry_price, digits)
        if new_stop_loss <= current_price:
            return None
        return TradeManagementResult(action=OrderAction.MODIFY.value, reason='TRADE_MANAGEMENT_BREAKEVEN: stop loss moved to entry', stop_loss=new_stop_loss, take_profit=position.take_profit)
    raise _validation_error('side must be BUY or SELL', side=position.side)

def evaluate_trailing_stop(*, position: OpenPosition, current_price: float, swing_low: float, swing_high: float, trailing_buffer: float, digits: int) -> TradeManagementResult | None:
    if trailing_buffer < 0:
        raise _validation_error('trailing_buffer must be >= 0', trailing_buffer=trailing_buffer)
    if position.side == Side.BUY.value:
        if swing_low <= 0:
            return None
        candidate_stop_loss = _round_price(swing_low - trailing_buffer, digits)
        if candidate_stop_loss <= position.stop_loss:
            return None
        if candidate_stop_loss >= current_price:
            return None
        return TradeManagementResult(action=OrderAction.MODIFY.value, reason='TRADE_MANAGEMENT_TRAILING: stop loss raised to follow structure', stop_loss=candidate_stop_loss, take_profit=position.take_profit)
    if position.side == Side.SELL.value:
        if swing_high <= 0:
            return None
        candidate_stop_loss = _round_price(swing_high + trailing_buffer, digits)
        if candidate_stop_loss >= position.stop_loss:
            return None
        if candidate_stop_loss <= current_price:
            return None
        return TradeManagementResult(action=OrderAction.MODIFY.value, reason='TRADE_MANAGEMENT_TRAILING: stop loss lowered to follow structure', stop_loss=candidate_stop_loss, take_profit=position.take_profit)
    raise _validation_error('side must be BUY or SELL', side=position.side)

def evaluate_partial_close(*, position: OpenPosition, current_price: float, partial_close_progress_ratio: float, partial_close_volume_ratio: float, volume_step: float) -> TradeManagementResult | None:
    if position.partial_close_applied:
        return None
    if partial_close_progress_ratio <= 0 or partial_close_volume_ratio <= 0:
        return None
    if volume_step <= 0:
        raise _validation_error('volume_step must be > 0', volume_step=volume_step)
    progress = compute_progress_to_take_profit(side=position.side, entry_price=position.entry_price, take_profit=position.take_profit, current_price=current_price)
    if progress < partial_close_progress_ratio:
        return None
    close_volume = normalize_volume_to_step(volume=position.volume * partial_close_volume_ratio, volume_step=volume_step)
    if close_volume <= 0 or close_volume >= position.volume:
        return None
    return TradeManagementResult(action=OrderAction.CLOSE.value, reason='TRADE_MANAGEMENT_PARTIAL_CLOSE: partial volume close triggered', volume=close_volume)

def evaluate_time_stop(*, position: OpenPosition, time_stop_max_bars: int) -> TradeManagementResult | None:
    if time_stop_max_bars <= 0:
        return None
    if position.bars_open < time_stop_max_bars:
        return None
    return TradeManagementResult(action=OrderAction.CLOSE.value, reason='TRADE_MANAGEMENT_TIME_STOP: maximum bars in trade reached', volume=position.volume)

def evaluate_trade_management(*, position: OpenPosition | None, current_price: float, swing_low: float, swing_high: float, config: TradeManagementConfig, digits: int, allow_close: bool=True) -> TradeManagementResult:
    if position is None:
        return _no_action()
    time_stop_result = evaluate_time_stop(position=position, time_stop_max_bars=config.time_stop_max_bars)
    if time_stop_result is not None:
        return _gate_close_action(time_stop_result, allow_close=allow_close)
    partial_close_result = evaluate_partial_close(position=position, current_price=current_price, partial_close_progress_ratio=config.partial_close_progress_ratio, partial_close_volume_ratio=config.partial_close_volume_ratio, volume_step=config.volume_step)
    if partial_close_result is not None:
        return _gate_close_action(partial_close_result, allow_close=allow_close)
    trailing_result = evaluate_trailing_stop(position=position, current_price=current_price, swing_low=swing_low, swing_high=swing_high, trailing_buffer=config.trailing_buffer, digits=digits)
    if trailing_result is not None:
        return trailing_result
    breakeven_result = evaluate_breakeven(position=position, current_price=current_price, breakeven_progress_ratio=config.breakeven_progress_ratio, digits=digits)
    if breakeven_result is not None:
        return breakeven_result
    return _no_action()
