from __future__ import annotations
from dataclasses import dataclass
from engine.protocol.constants import REASON_DATA_INVALID, REASON_MISSING_TAKE_PROFIT, Side
from engine.protocol.errors import ValidationError
from engine.reason import build_reason
MODULE_NAME = 'risk.sl_tp'

def _validation_error(message: str, **context: object) -> ValidationError:
    return ValidationError(message, module=MODULE_NAME, context=dict(context))

def _round_price(price: float, digits: int) -> float:
    return round(price, digits)

@dataclass(frozen=True)
class SlTpValidationResult:
    allowed: bool
    stop_loss: float
    take_profit: float
    reason: str | None

def compute_stop_loss_distance_pips(*, entry_price: float, stop_loss: float, pip: float) -> float:
    if pip <= 0:
        raise _validation_error('pip must be > 0', pip=pip)
    return abs(entry_price - stop_loss) / pip

def calculate_take_profit(*, side: str, entry_price: float, stop_loss: float, reward_ratio: float, digits: int) -> float:
    if reward_ratio <= 0:
        raise _validation_error('reward_ratio must be > 0', reward_ratio=reward_ratio)
    if side == Side.BUY.value:
        stop_loss_distance = entry_price - stop_loss
        return _round_price(entry_price + stop_loss_distance * reward_ratio, digits)
    if side == Side.SELL.value:
        stop_loss_distance = stop_loss - entry_price
        return _round_price(entry_price - stop_loss_distance * reward_ratio, digits)
    raise _validation_error('side must be BUY or SELL', side=side)

def validate_buy_stop_loss_placement(*, entry_price: float, stop_loss: float, swing_low: float) -> str | None:
    if stop_loss >= entry_price:
        return build_reason(REASON_DATA_INVALID, 'buy stop loss must be below entry price', entry_price=entry_price, stop_loss=stop_loss)
    if swing_low > 0 and stop_loss >= swing_low:
        return build_reason(REASON_DATA_INVALID, 'buy stop loss must be below swing low', stop_loss=stop_loss, swing_low=swing_low)
    return None

def validate_sell_stop_loss_placement(*, entry_price: float, stop_loss: float, swing_high: float) -> str | None:
    if stop_loss <= entry_price:
        return build_reason(REASON_DATA_INVALID, 'sell stop loss must be above entry price', entry_price=entry_price, stop_loss=stop_loss)
    if swing_high > 0 and stop_loss <= swing_high:
        return build_reason(REASON_DATA_INVALID, 'sell stop loss must be above swing high', stop_loss=stop_loss, swing_high=swing_high)
    return None

def validate_stop_loss_within_max_pips(*, entry_price: float, stop_loss: float, pip: float, max_stop_loss_pips: float) -> str | None:
    if max_stop_loss_pips <= 0:
        raise _validation_error('max_stop_loss_pips must be > 0', max_stop_loss_pips=max_stop_loss_pips)
    distance_pips = compute_stop_loss_distance_pips(entry_price=entry_price, stop_loss=stop_loss, pip=pip)
    if distance_pips > max_stop_loss_pips:
        return build_reason(REASON_DATA_INVALID, 'stop loss exceeds max_stop_loss_pips', distance_pips=distance_pips, max_stop_loss_pips=max_stop_loss_pips, pip=pip)
    return None

def validate_take_profit_present(*, take_profit: float | None) -> str | None:
    if take_profit is None or take_profit <= 0:
        return build_reason(REASON_MISSING_TAKE_PROFIT, 'take profit is required before risk allow')
    return None

def validate_take_profit_direction(*, side: str, entry_price: float, take_profit: float) -> str | None:
    if side == Side.BUY.value and take_profit <= entry_price:
        return build_reason(REASON_DATA_INVALID, 'buy take profit must be above entry price', entry_price=entry_price, take_profit=take_profit)
    if side == Side.SELL.value and take_profit >= entry_price:
        return build_reason(REASON_DATA_INVALID, 'sell take profit must be below entry price', entry_price=entry_price, take_profit=take_profit)
    return None

def validate_sl_tp(*, side: str, entry_price: float, stop_loss: float, take_profit: float | None, swing_low: float, swing_high: float, pip: float, max_stop_loss_pips: float) -> SlTpValidationResult:
    if side == Side.BUY.value:
        placement_reason = validate_buy_stop_loss_placement(entry_price=entry_price, stop_loss=stop_loss, swing_low=swing_low)
    elif side == Side.SELL.value:
        placement_reason = validate_sell_stop_loss_placement(entry_price=entry_price, stop_loss=stop_loss, swing_high=swing_high)
    else:
        return SlTpValidationResult(allowed=False, stop_loss=stop_loss, take_profit=take_profit or 0.0, reason=build_reason(REASON_DATA_INVALID, 'side must be BUY or SELL', side=side))
    if placement_reason is not None:
        return SlTpValidationResult(allowed=False, stop_loss=stop_loss, take_profit=take_profit or 0.0, reason=placement_reason)
    max_pips_reason = validate_stop_loss_within_max_pips(entry_price=entry_price, stop_loss=stop_loss, pip=pip, max_stop_loss_pips=max_stop_loss_pips)
    if max_pips_reason is not None:
        return SlTpValidationResult(allowed=False, stop_loss=stop_loss, take_profit=take_profit or 0.0, reason=max_pips_reason)
    tp_reason = validate_take_profit_present(take_profit=take_profit)
    if tp_reason is not None:
        return SlTpValidationResult(allowed=False, stop_loss=stop_loss, take_profit=0.0, reason=tp_reason)
    direction_reason = validate_take_profit_direction(side=side, entry_price=entry_price, take_profit=take_profit)
    if direction_reason is not None:
        return SlTpValidationResult(allowed=False, stop_loss=stop_loss, take_profit=take_profit, reason=direction_reason)
    return SlTpValidationResult(allowed=True, stop_loss=stop_loss, take_profit=take_profit, reason=None)
