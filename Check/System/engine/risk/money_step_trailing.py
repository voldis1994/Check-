"""Money-step trailing: lock progressive account-currency profit without fixed TP."""
from __future__ import annotations
import math
from dataclasses import dataclass
from engine.protocol.constants import OrderAction, Side
from engine.protocol.errors import ValidationError
from engine.risk.trade_management import TradeManagementResult

MODULE_NAME = 'risk.money_step_trailing'
MONEY_TRAILING_STATE_MISSING = 'money_trailing_state_missing'


def _validation_error(message: str, **context: object) -> ValidationError:
    return ValidationError(message, module=MODULE_NAME, context=dict(context))


@dataclass(frozen=True)
class MoneyStepTrailingParams:
    enabled: bool
    activation_profit_money: float
    profit_step_money: float
    initial_locked_profit_money: float
    lock_increment_money: float

    def is_runnable(self) -> bool:
        """True only when enabled and all production constraints are satisfied."""
        if not self.enabled:
            return False
        if self.activation_profit_money <= 0:
            return False
        if self.profit_step_money <= 0:
            return False
        if self.initial_locked_profit_money < 0:
            return False
        if self.lock_increment_money <= 0:
            return False
        if self.initial_locked_profit_money >= self.activation_profit_money:
            return False
        return True


@dataclass(frozen=True)
class MoneyStepTrailingState:
    peak_net_profit_money: float = 0.0
    money_trailing_step_index: int = -1
    locked_profit_money: float = 0.0
    last_money_trailing_sl: float | None = None


@dataclass(frozen=True)
class MoneyStepTrailingEval:
    activated: bool
    completed_steps: int
    locked_profit_money: float
    peak_net_profit_money: float
    money_step_sl: float | None
    reason: str


@dataclass(frozen=True)
class MoneyStepMergeResult:
    management_result: TradeManagementResult
    state: MoneyStepTrailingState
    skip_reason: str = ''
    state_missing: bool = False


def compute_net_profit_money(*, profit: float, swap: float, commission: float) -> float:
    return float(profit) + float(swap) + float(commission)


def compute_completed_steps(*, peak_net_profit_money: float, params: MoneyStepTrailingParams) -> int:
    if peak_net_profit_money < params.activation_profit_money:
        return -1
    return int(math.floor((peak_net_profit_money - params.activation_profit_money) / params.profit_step_money))


def compute_locked_profit_money(*, completed_steps: int, params: MoneyStepTrailingParams) -> float:
    if completed_steps < 0:
        return 0.0
    return params.initial_locked_profit_money + completed_steps * params.lock_increment_money


def money_per_price_unit(*, tick_value: float, tick_size: float, volume: float) -> float:
    if tick_value <= 0 or tick_size <= 0 or volume <= 0:
        raise _validation_error('tick_value, tick_size and volume must be > 0', tick_value=tick_value, tick_size=tick_size, volume=volume)
    return (tick_value / tick_size) * volume


def compute_money_step_sl(
    *,
    side: str,
    open_price: float,
    locked_profit_money: float,
    current_swap: float,
    current_commission: float,
    tick_value: float,
    tick_size: float,
    volume: float,
    digits: int,
) -> float:
    required_gross = locked_profit_money - current_swap - current_commission
    mppu = money_per_price_unit(tick_value=tick_value, tick_size=tick_size, volume=volume)
    price_distance = required_gross / mppu
    if side == Side.BUY.value:
        return round(open_price + price_distance, digits)
    if side == Side.SELL.value:
        return round(open_price - price_distance, digits)
    raise _validation_error('side must be BUY or SELL', side=side)


def choose_protective_sl(*, side: str, current_sl: float, technical_sl: float | None, money_sl: float | None) -> float:
    candidates = [current_sl]
    if technical_sl is not None:
        candidates.append(technical_sl)
    if money_sl is not None:
        candidates.append(money_sl)
    if side == Side.BUY.value:
        return max(candidates)
    if side == Side.SELL.value:
        return min(candidates)
    raise _validation_error('side must be BUY or SELL', side=side)


def sl_improves(*, side: str, current_sl: float, proposed_sl: float, tolerance: float) -> bool:
    if side == Side.BUY.value:
        return proposed_sl > current_sl + tolerance
    if side == Side.SELL.value:
        return proposed_sl < current_sl - tolerance
    raise _validation_error('side must be BUY or SELL', side=side)


def respects_stop_freeze_levels(
    *,
    side: str,
    proposed_sl: float,
    current_price: float,
    point: float,
    stop_level: int,
    freeze_level: int,
) -> bool:
    if point <= 0:
        return False
    min_distance = max(stop_level, freeze_level) * point
    if min_distance < 0:
        return False
    if side == Side.BUY.value:
        return proposed_sl <= current_price - min_distance
    if side == Side.SELL.value:
        return proposed_sl >= current_price + min_distance
    return False


def evaluate_money_step_trailing(
    *,
    params: MoneyStepTrailingParams,
    state: MoneyStepTrailingState,
    side: str,
    open_price: float,
    current_sl: float,
    net_profit_money: float,
    current_swap: float,
    current_commission: float,
    tick_value: float,
    tick_size: float,
    volume: float,
    digits: int,
) -> tuple[MoneyStepTrailingEval, MoneyStepTrailingState]:
    if not params.is_runnable():
        return (
            MoneyStepTrailingEval(activated=False, completed_steps=-1, locked_profit_money=state.locked_profit_money, peak_net_profit_money=state.peak_net_profit_money, money_step_sl=None, reason='money_step_trailing_inactive_invalid_config'),
            state,
        )
    peak = max(state.peak_net_profit_money, net_profit_money)
    completed = compute_completed_steps(peak_net_profit_money=peak, params=params)
    if completed < 0:
        new_state = MoneyStepTrailingState(peak_net_profit_money=peak, money_trailing_step_index=state.money_trailing_step_index, locked_profit_money=state.locked_profit_money, last_money_trailing_sl=state.last_money_trailing_sl)
        return (
            MoneyStepTrailingEval(activated=False, completed_steps=-1, locked_profit_money=new_state.locked_profit_money, peak_net_profit_money=peak, money_step_sl=None, reason='money_step_trailing_not_activated'),
            new_state,
        )
    locked = compute_locked_profit_money(completed_steps=completed, params=params)
    # Never reduce locked profit on peak retreat.
    locked = max(locked, state.locked_profit_money)
    money_sl = compute_money_step_sl(
        side=side,
        open_price=open_price,
        locked_profit_money=locked,
        current_swap=current_swap,
        current_commission=current_commission,
        tick_value=tick_value,
        tick_size=tick_size,
        volume=volume,
        digits=digits,
    )
    new_state = MoneyStepTrailingState(peak_net_profit_money=peak, money_trailing_step_index=completed, locked_profit_money=locked, last_money_trailing_sl=money_sl)
    return (
        MoneyStepTrailingEval(activated=True, completed_steps=completed, locked_profit_money=locked, peak_net_profit_money=peak, money_step_sl=money_sl, reason='money_step_trailing_active'),
        new_state,
    )


def merge_technical_and_money_step_trailing(
    *,
    technical_result: TradeManagementResult,
    params: MoneyStepTrailingParams,
    state: MoneyStepTrailingState,
    side: str,
    open_price: float,
    current_sl: float,
    current_price: float,
    net_profit_money: float,
    current_swap: float,
    current_commission: float,
    tick_value: float | None,
    tick_size: float | None,
    volume: float,
    digits: int,
    point: float,
    stop_level: int | None,
    freeze_level: int | None,
    price_tolerance: float,
    modify_take_profit: float,
    sensor_fresh: bool,
    pending_modify_sl: float | None = None,
    state_missing: bool = False,
) -> MoneyStepMergeResult:
    """Combine technical trailing with money-step; never weaken either protective SL."""
    if technical_result.action == OrderAction.CLOSE.value:
        return MoneyStepMergeResult(management_result=technical_result, state=state)

    if state_missing:
        # Do not invent peak/locked; keep broker SL as the floor and only apply technical if protective.
        technical_sl = technical_result.stop_loss if technical_result.action == OrderAction.MODIFY.value else None
        final_sl = choose_protective_sl(side=side, current_sl=current_sl, technical_sl=technical_sl, money_sl=None)
        if technical_result.action == OrderAction.MODIFY.value and sl_improves(side=side, current_sl=current_sl, proposed_sl=final_sl, tolerance=price_tolerance):
            return MoneyStepMergeResult(
                management_result=TradeManagementResult(
                    action=OrderAction.MODIFY.value,
                    reason=f'{MONEY_TRAILING_STATE_MISSING};{technical_result.reason}',
                    stop_loss=final_sl,
                    take_profit=modify_take_profit,
                ),
                state=state,
                skip_reason=MONEY_TRAILING_STATE_MISSING,
                state_missing=True,
            )
        return MoneyStepMergeResult(
            management_result=TradeManagementResult(action=OrderAction.NONE.value, reason=MONEY_TRAILING_STATE_MISSING),
            state=state,
            skip_reason=MONEY_TRAILING_STATE_MISSING,
            state_missing=True,
        )

    if not params.is_runnable():
        return MoneyStepMergeResult(management_result=technical_result, state=state, skip_reason='money_step_trailing_inactive_invalid_config')

    if not sensor_fresh:
        # Still ratchet peak from fresh status profit when available, but never money-MODIFY on stale Bid/Ask.
        # Keep technical trailing — do not suppress pip/structure SL moves.
        peak_only = MoneyStepTrailingState(
            peak_net_profit_money=max(state.peak_net_profit_money, net_profit_money),
            money_trailing_step_index=state.money_trailing_step_index,
            locked_profit_money=state.locked_profit_money,
            last_money_trailing_sl=state.last_money_trailing_sl,
        )
        return MoneyStepMergeResult(
            management_result=technical_result,
            state=peak_only,
            skip_reason='money_step_trailing_blocked_stale_sensor',
        )

    if tick_value is None or tick_size is None or tick_value <= 0 or tick_size <= 0 or volume <= 0:
        peak_only = MoneyStepTrailingState(
            peak_net_profit_money=max(state.peak_net_profit_money, net_profit_money),
            money_trailing_step_index=state.money_trailing_step_index,
            locked_profit_money=state.locked_profit_money,
            last_money_trailing_sl=state.last_money_trailing_sl,
        )
        # Missing broker tick metadata must not kill technical trailing / lockpoint fallback.
        return MoneyStepMergeResult(
            management_result=technical_result,
            state=peak_only,
            skip_reason='money_step_trailing_blocked_invalid_tick',
        )

    try:
        money_eval, new_state = evaluate_money_step_trailing(
            params=params,
            state=state,
            side=side,
            open_price=open_price,
            current_sl=current_sl,
            net_profit_money=net_profit_money,
            current_swap=current_swap,
            current_commission=current_commission,
            tick_value=float(tick_value),
            tick_size=float(tick_size),
            volume=volume,
            digits=digits,
        )
    except ValidationError:
        peak_only = MoneyStepTrailingState(
            peak_net_profit_money=max(state.peak_net_profit_money, net_profit_money),
            money_trailing_step_index=state.money_trailing_step_index,
            locked_profit_money=state.locked_profit_money,
            last_money_trailing_sl=state.last_money_trailing_sl,
        )
        return MoneyStepMergeResult(
            management_result=technical_result,
            state=peak_only,
            skip_reason='money_step_trailing_blocked_invalid_tick',
        )

    technical_sl = technical_result.stop_loss if technical_result.action == OrderAction.MODIFY.value else None
    money_sl = money_eval.money_step_sl
    final_sl = choose_protective_sl(side=side, current_sl=current_sl, technical_sl=technical_sl, money_sl=money_sl)

    new_money_step = money_eval.activated and money_eval.completed_steps > state.money_trailing_step_index
    technical_wants_modify = technical_result.action == OrderAction.MODIFY.value
    # Money-step MODIFY only on a new profit step; technical can still improve protection.
    should_consider_modify = technical_wants_modify or new_money_step
    if not should_consider_modify:
        return MoneyStepMergeResult(management_result=TradeManagementResult(action=OrderAction.NONE.value, reason=money_eval.reason), state=new_state)

    if not sl_improves(side=side, current_sl=current_sl, proposed_sl=final_sl, tolerance=price_tolerance):
        return MoneyStepMergeResult(
            management_result=TradeManagementResult(action=OrderAction.NONE.value, reason='money_step_trailing_no_sl_improvement'),
            state=new_state,
            skip_reason='money_step_trailing_no_sl_improvement',
        )

    if pending_modify_sl is not None and abs(pending_modify_sl - final_sl) <= price_tolerance:
        return MoneyStepMergeResult(
            management_result=TradeManagementResult(action=OrderAction.NONE.value, reason='money_step_trailing_identical_modify_pending'),
            state=new_state,
            skip_reason='money_step_trailing_identical_modify_pending',
        )

    previous_sent_sl = state.last_money_trailing_sl
    if (
        previous_sent_sl is not None
        and abs(previous_sent_sl - final_sl) <= price_tolerance
        and not technical_wants_modify
        and not new_money_step
    ):
        return MoneyStepMergeResult(
            management_result=TradeManagementResult(action=OrderAction.NONE.value, reason='money_step_trailing_identical_sl'),
            state=new_state,
            skip_reason='money_step_trailing_identical_sl',
        )

    resolved_stop = 0 if stop_level is None else int(stop_level)
    resolved_freeze = 0 if freeze_level is None else int(freeze_level)
    if not respects_stop_freeze_levels(
        side=side,
        proposed_sl=final_sl,
        current_price=current_price,
        point=point,
        stop_level=resolved_stop,
        freeze_level=resolved_freeze,
    ):
        return MoneyStepMergeResult(
            management_result=TradeManagementResult(action=OrderAction.NONE.value, reason='money_step_trailing_blocked_stop_freeze'),
            state=new_state,
            skip_reason='money_step_trailing_blocked_stop_freeze',
        )

    reason_parts = []
    if technical_wants_modify:
        reason_parts.append(technical_result.reason)
    if money_eval.activated:
        reason_parts.append(f'MONEY_STEP_TRAILING: locked={money_eval.locked_profit_money:.2f} steps={money_eval.completed_steps}')
    persisted = MoneyStepTrailingState(
        peak_net_profit_money=new_state.peak_net_profit_money,
        money_trailing_step_index=new_state.money_trailing_step_index,
        locked_profit_money=new_state.locked_profit_money,
        last_money_trailing_sl=final_sl,
    )
    return MoneyStepMergeResult(
        management_result=TradeManagementResult(
            action=OrderAction.MODIFY.value,
            reason='; '.join(reason_parts) if reason_parts else 'MONEY_STEP_TRAILING',
            stop_loss=final_sl,
            take_profit=modify_take_profit,
        ),
        state=persisted,
    )
