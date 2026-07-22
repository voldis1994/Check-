"""Money-step BE+net then discrete pip trailing (never weaken SL).

Flow:
1. When peak net profit reaches activation, propose BE SL that locks
   ``initial_locked_profit_money`` (e.g. +0.20 account currency) after
   commission/swap via tick_value/tick_size.
2. Mark BE confirmed only after successful MODIFY ACK / broker SL match.
3. After BE is confirmed, trail SL in discrete ``trailing_step_pips`` steps
   from the last confirmed protective SL (BUY up / SELL down only).
"""
from __future__ import annotations
import math
from dataclasses import dataclass
from engine.protocol.constants import OrderAction, Side
from engine.protocol.errors import ValidationError
from engine.risk.trade_management import TradeManagementResult

MODULE_NAME = 'risk.money_step_trailing'
MONEY_TRAILING_STATE_MISSING = 'money_trailing_state_missing'
REASON_BE_PLUS_NET_PROFIT = 'BE_PLUS_NET_PROFIT'
REASON_PIP_TRAIL_STEP = 'PIP_TRAIL_STEP'
REASON_MISSING_TICK = 'BE_PLUS_MISSING_TICK_DATA'


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
    be_plus_confirmed: bool = False
    confirmed_protective_sl: float | None = None
    pending_protective_sl: float | None = None
    pending_trailing_reason: str | None = None
    pip_trail_confirmed_steps: int = 0
    computed_be_plus_sl: float | None = None
    next_pip_trail_sl: float | None = None
    last_trailing_modify_status: str | None = None
    last_trailing_broker_error: str | None = None
    trailing_reason_code: str | None = None


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
    """SL such that fill yields approximately ``locked_profit_money`` net of swap/commission."""
    required_gross = locked_profit_money - current_swap - current_commission
    mppu = money_per_price_unit(tick_value=tick_value, tick_size=tick_size, volume=volume)
    price_distance = required_gross / mppu
    if side == Side.BUY.value:
        return round(open_price + price_distance, digits)
    if side == Side.SELL.value:
        return round(open_price - price_distance, digits)
    raise _validation_error('side must be BUY or SELL', side=side)


def pip_step_price(*, trailing_step_pips: float, pip: float) -> float:
    if trailing_step_pips < 0 or pip <= 0:
        raise _validation_error('trailing_step_pips must be >= 0 and pip > 0', trailing_step_pips=trailing_step_pips, pip=pip)
    return float(trailing_step_pips) * float(pip)


def compute_discrete_pip_trail_sl(
    *,
    side: str,
    confirmed_sl: float,
    current_price: float,
    trailing_step_pips: float,
    pip: float,
    digits: int,
    point: float,
    stop_level: int,
    freeze_level: int,
) -> float | None:
    """Latest discrete N×pip step from confirmed SL that still respects stop/freeze.

    Skipped intermediate steps are allowed — only the newest valid level is returned.
    """
    if trailing_step_pips <= 0 or pip <= 0 or point <= 0:
        return None
    step = pip_step_price(trailing_step_pips=trailing_step_pips, pip=pip)
    if step <= 0:
        return None
    min_distance = max(int(stop_level), int(freeze_level)) * point
    if side == Side.BUY.value:
        max_allowed = current_price - min_distance
        if max_allowed <= confirmed_sl:
            return None
        steps = int(math.floor((max_allowed - confirmed_sl) / step + 1e-12))
        while steps >= 1:
            candidate = round(confirmed_sl + steps * step, digits)
            if candidate <= confirmed_sl:
                return None
            if candidate <= max_allowed and respects_stop_freeze_levels(
                side=side,
                proposed_sl=candidate,
                current_price=current_price,
                point=point,
                stop_level=stop_level,
                freeze_level=freeze_level,
            ):
                return candidate
            steps -= 1
        return None
    if side == Side.SELL.value:
        min_allowed = current_price + min_distance
        if min_allowed >= confirmed_sl:
            return None
        steps = int(math.floor((confirmed_sl - min_allowed) / step + 1e-12))
        while steps >= 1:
            candidate = round(confirmed_sl - steps * step, digits)
            if candidate >= confirmed_sl:
                return None
            if candidate >= min_allowed and respects_stop_freeze_levels(
                side=side,
                proposed_sl=candidate,
                current_price=current_price,
                point=point,
                stop_level=stop_level,
                freeze_level=freeze_level,
            ):
                return candidate
            steps -= 1
        return None
    raise _validation_error('side must be BUY or SELL', side=side)


def next_pip_trail_target(*, side: str, confirmed_sl: float, trailing_step_pips: float, pip: float, digits: int) -> float | None:
    if trailing_step_pips <= 0 or pip <= 0:
        return None
    step = pip_step_price(trailing_step_pips=trailing_step_pips, pip=pip)
    if side == Side.BUY.value:
        return round(confirmed_sl + step, digits)
    if side == Side.SELL.value:
        return round(confirmed_sl - step, digits)
    return None


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
    del current_sl  # used by callers for improvement checks
    if not params.is_runnable():
        return (
            MoneyStepTrailingEval(activated=False, completed_steps=-1, locked_profit_money=state.locked_profit_money, peak_net_profit_money=state.peak_net_profit_money, money_step_sl=None, reason='money_step_trailing_inactive_invalid_config'),
            state,
        )
    peak = max(state.peak_net_profit_money, net_profit_money)
    completed = compute_completed_steps(peak_net_profit_money=peak, params=params)
    if completed < 0:
        new_state = MoneyStepTrailingState(
            peak_net_profit_money=peak,
            money_trailing_step_index=state.money_trailing_step_index,
            locked_profit_money=state.locked_profit_money,
            last_money_trailing_sl=state.last_money_trailing_sl,
            be_plus_confirmed=state.be_plus_confirmed,
            confirmed_protective_sl=state.confirmed_protective_sl,
            pending_protective_sl=state.pending_protective_sl,
            pending_trailing_reason=state.pending_trailing_reason,
            pip_trail_confirmed_steps=state.pip_trail_confirmed_steps,
            computed_be_plus_sl=state.computed_be_plus_sl,
            next_pip_trail_sl=state.next_pip_trail_sl,
            last_trailing_modify_status=state.last_trailing_modify_status,
            last_trailing_broker_error=state.last_trailing_broker_error,
            trailing_reason_code=state.trailing_reason_code,
        )
        return (
            MoneyStepTrailingEval(activated=False, completed_steps=-1, locked_profit_money=new_state.locked_profit_money, peak_net_profit_money=peak, money_step_sl=None, reason='money_step_trailing_not_activated'),
            new_state,
        )
    # BE+net uses initial_locked_profit_money; further money locks remain available
    # but post-BE protection primarily advances via discrete pip steps.
    locked = compute_locked_profit_money(completed_steps=completed, params=params)
    locked = max(locked, state.locked_profit_money, params.initial_locked_profit_money if completed >= 0 else 0.0)
    # For the first BE step, lock exactly initial_locked_profit_money until confirmed.
    be_lock = params.initial_locked_profit_money if not state.be_plus_confirmed else locked
    money_sl = compute_money_step_sl(
        side=side,
        open_price=open_price,
        locked_profit_money=be_lock if not state.be_plus_confirmed else locked,
        current_swap=current_swap,
        current_commission=current_commission,
        tick_value=tick_value,
        tick_size=tick_size,
        volume=volume,
        digits=digits,
    )
    new_state = MoneyStepTrailingState(
        peak_net_profit_money=peak,
        money_trailing_step_index=completed,
        locked_profit_money=locked if state.be_plus_confirmed else max(state.locked_profit_money, params.initial_locked_profit_money),
        last_money_trailing_sl=state.last_money_trailing_sl,
        be_plus_confirmed=state.be_plus_confirmed,
        confirmed_protective_sl=state.confirmed_protective_sl,
        pending_protective_sl=state.pending_protective_sl,
        pending_trailing_reason=state.pending_trailing_reason,
        pip_trail_confirmed_steps=state.pip_trail_confirmed_steps,
        computed_be_plus_sl=money_sl if not state.be_plus_confirmed else state.computed_be_plus_sl,
        next_pip_trail_sl=state.next_pip_trail_sl,
        last_trailing_modify_status=state.last_trailing_modify_status,
        last_trailing_broker_error=state.last_trailing_broker_error,
        trailing_reason_code=REASON_BE_PLUS_NET_PROFIT if not state.be_plus_confirmed else state.trailing_reason_code,
    )
    return (
        MoneyStepTrailingEval(activated=True, completed_steps=completed, locked_profit_money=new_state.locked_profit_money, peak_net_profit_money=peak, money_step_sl=money_sl, reason='money_step_trailing_active'),
        new_state,
    )


def confirm_protective_sl(
    state: MoneyStepTrailingState,
    *,
    broker_sl: float,
    price_tolerance: float,
    trailing_step_pips: float = 0.0,
    pip: float = 0.0,
    digits: int = 5,
    side: str = Side.BUY.value,
) -> MoneyStepTrailingState:
    """Confirm pending SL when broker matches requested level within tolerance."""
    pending = state.pending_protective_sl
    if pending is None:
        return state
    if abs(float(broker_sl) - float(pending)) > price_tolerance:
        return state
    be_confirmed = state.be_plus_confirmed or (state.pending_trailing_reason == REASON_BE_PLUS_NET_PROFIT)
    pip_steps = state.pip_trail_confirmed_steps
    if state.pending_trailing_reason == REASON_PIP_TRAIL_STEP:
        pip_steps += 1
    next_target = None
    if be_confirmed and trailing_step_pips > 0 and pip > 0:
        next_target = next_pip_trail_target(side=side, confirmed_sl=pending, trailing_step_pips=trailing_step_pips, pip=pip, digits=digits)
    locked = state.locked_profit_money
    if be_confirmed and locked <= 0:
        locked = state.locked_profit_money
    return MoneyStepTrailingState(
        peak_net_profit_money=state.peak_net_profit_money,
        money_trailing_step_index=max(state.money_trailing_step_index, 0),
        locked_profit_money=locked,
        last_money_trailing_sl=pending,
        be_plus_confirmed=be_confirmed,
        confirmed_protective_sl=pending,
        pending_protective_sl=None,
        pending_trailing_reason=None,
        pip_trail_confirmed_steps=pip_steps,
        computed_be_plus_sl=state.computed_be_plus_sl,
        next_pip_trail_sl=next_target,
        last_trailing_modify_status='SUCCESS',
        last_trailing_broker_error=None,
        trailing_reason_code=state.pending_trailing_reason or state.trailing_reason_code,
    )


def mark_protective_modify_rejected(
    state: MoneyStepTrailingState,
    *,
    status: str,
    error_code: str | None,
) -> MoneyStepTrailingState:
    """Keep pending target for retry; do not treat as confirmed."""
    return MoneyStepTrailingState(
        peak_net_profit_money=state.peak_net_profit_money,
        money_trailing_step_index=state.money_trailing_step_index,
        locked_profit_money=state.locked_profit_money,
        last_money_trailing_sl=state.last_money_trailing_sl,
        be_plus_confirmed=state.be_plus_confirmed,
        confirmed_protective_sl=state.confirmed_protective_sl,
        pending_protective_sl=state.pending_protective_sl,
        pending_trailing_reason=state.pending_trailing_reason,
        pip_trail_confirmed_steps=state.pip_trail_confirmed_steps,
        computed_be_plus_sl=state.computed_be_plus_sl,
        next_pip_trail_sl=state.next_pip_trail_sl,
        last_trailing_modify_status=status,
        last_trailing_broker_error=error_code,
        trailing_reason_code=state.trailing_reason_code,
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
    trailing_step_pips: float = 0.0,
    pip: float = 0.0,
) -> MoneyStepMergeResult:
    """Combine BE+net, discrete pip trail, and technical trailing; never weaken SL."""
    if technical_result.action == OrderAction.CLOSE.value:
        return MoneyStepMergeResult(management_result=technical_result, state=state)

    if state_missing:
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
        peak_only = MoneyStepTrailingState(
            peak_net_profit_money=max(state.peak_net_profit_money, net_profit_money),
            money_trailing_step_index=state.money_trailing_step_index,
            locked_profit_money=state.locked_profit_money,
            last_money_trailing_sl=state.last_money_trailing_sl,
            be_plus_confirmed=state.be_plus_confirmed,
            confirmed_protective_sl=state.confirmed_protective_sl,
            pending_protective_sl=state.pending_protective_sl,
            pending_trailing_reason=state.pending_trailing_reason,
            pip_trail_confirmed_steps=state.pip_trail_confirmed_steps,
            computed_be_plus_sl=state.computed_be_plus_sl,
            next_pip_trail_sl=state.next_pip_trail_sl,
            last_trailing_modify_status=state.last_trailing_modify_status,
            last_trailing_broker_error=state.last_trailing_broker_error,
            trailing_reason_code=state.trailing_reason_code,
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
            be_plus_confirmed=state.be_plus_confirmed,
            confirmed_protective_sl=state.confirmed_protective_sl,
            pending_protective_sl=state.pending_protective_sl,
            pending_trailing_reason=state.pending_trailing_reason,
            pip_trail_confirmed_steps=state.pip_trail_confirmed_steps,
            computed_be_plus_sl=state.computed_be_plus_sl,
            next_pip_trail_sl=state.next_pip_trail_sl,
            last_trailing_modify_status=state.last_trailing_modify_status,
            last_trailing_broker_error=state.last_trailing_broker_error,
            trailing_reason_code=REASON_MISSING_TICK,
        )
        # Missing tick must not invent BE; technical trailing may still run.
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
            be_plus_confirmed=state.be_plus_confirmed,
            confirmed_protective_sl=state.confirmed_protective_sl,
            pending_protective_sl=state.pending_protective_sl,
            pending_trailing_reason=state.pending_trailing_reason,
            pip_trail_confirmed_steps=state.pip_trail_confirmed_steps,
            computed_be_plus_sl=state.computed_be_plus_sl,
            next_pip_trail_sl=state.next_pip_trail_sl,
            last_trailing_modify_status=state.last_trailing_modify_status,
            last_trailing_broker_error=state.last_trailing_broker_error,
            trailing_reason_code=REASON_MISSING_TICK,
        )
        return MoneyStepMergeResult(
            management_result=technical_result,
            state=peak_only,
            skip_reason='money_step_trailing_blocked_invalid_tick',
        )

    resolved_stop = 0 if stop_level is None else int(stop_level)
    resolved_freeze = 0 if freeze_level is None else int(freeze_level)
    technical_sl = technical_result.stop_loss if technical_result.action == OrderAction.MODIFY.value else None

    money_sl = money_eval.money_step_sl
    pip_sl: float | None = None
    reason_code = REASON_BE_PLUS_NET_PROFIT
    confirmed_base = new_state.confirmed_protective_sl
    if new_state.be_plus_confirmed and confirmed_base is not None and trailing_step_pips > 0 and pip > 0:
        pip_sl = compute_discrete_pip_trail_sl(
            side=side,
            confirmed_sl=float(confirmed_base),
            current_price=current_price,
            trailing_step_pips=trailing_step_pips,
            pip=pip,
            digits=digits,
            point=point,
            stop_level=resolved_stop,
            freeze_level=resolved_freeze,
        )
        next_target = next_pip_trail_target(side=side, confirmed_sl=float(confirmed_base), trailing_step_pips=trailing_step_pips, pip=pip, digits=digits)
        new_state = MoneyStepTrailingState(
            peak_net_profit_money=new_state.peak_net_profit_money,
            money_trailing_step_index=new_state.money_trailing_step_index,
            locked_profit_money=new_state.locked_profit_money,
            last_money_trailing_sl=new_state.last_money_trailing_sl,
            be_plus_confirmed=new_state.be_plus_confirmed,
            confirmed_protective_sl=new_state.confirmed_protective_sl,
            pending_protective_sl=new_state.pending_protective_sl,
            pending_trailing_reason=new_state.pending_trailing_reason,
            pip_trail_confirmed_steps=new_state.pip_trail_confirmed_steps,
            computed_be_plus_sl=new_state.computed_be_plus_sl,
            next_pip_trail_sl=next_target,
            last_trailing_modify_status=new_state.last_trailing_modify_status,
            last_trailing_broker_error=new_state.last_trailing_broker_error,
            trailing_reason_code=REASON_PIP_TRAIL_STEP if pip_sl is not None else new_state.trailing_reason_code,
        )
        if pip_sl is not None:
            reason_code = REASON_PIP_TRAIL_STEP

    # Prefer BE until confirmed; after that prefer pip trail over further money-only moves.
    protective_candidate = money_sl
    if new_state.be_plus_confirmed:
        protective_candidate = pip_sl if pip_sl is not None else money_sl
    elif money_eval.activated and money_sl is not None:
        protective_candidate = money_sl
        reason_code = REASON_BE_PLUS_NET_PROFIT
        new_state = MoneyStepTrailingState(
            peak_net_profit_money=new_state.peak_net_profit_money,
            money_trailing_step_index=new_state.money_trailing_step_index,
            locked_profit_money=new_state.locked_profit_money,
            last_money_trailing_sl=new_state.last_money_trailing_sl,
            be_plus_confirmed=False,
            confirmed_protective_sl=new_state.confirmed_protective_sl,
            pending_protective_sl=new_state.pending_protective_sl,
            pending_trailing_reason=new_state.pending_trailing_reason,
            pip_trail_confirmed_steps=new_state.pip_trail_confirmed_steps,
            computed_be_plus_sl=money_sl,
            next_pip_trail_sl=new_state.next_pip_trail_sl,
            last_trailing_modify_status=new_state.last_trailing_modify_status,
            last_trailing_broker_error=new_state.last_trailing_broker_error,
            trailing_reason_code=REASON_BE_PLUS_NET_PROFIT,
        )

    final_sl = choose_protective_sl(side=side, current_sl=current_sl, technical_sl=technical_sl, money_sl=protective_candidate)

    # Retry pending target if not confirmed yet.
    effective_pending = pending_modify_sl if pending_modify_sl is not None else new_state.pending_protective_sl
    if effective_pending is not None and abs(effective_pending - final_sl) <= price_tolerance:
        # Still propose the same pending level for retry unless already matching broker current_sl.
        if not sl_improves(side=side, current_sl=current_sl, proposed_sl=final_sl, tolerance=price_tolerance):
            return MoneyStepMergeResult(
                management_result=TradeManagementResult(action=OrderAction.NONE.value, reason='money_step_trailing_identical_modify_pending'),
                state=new_state,
                skip_reason='money_step_trailing_identical_modify_pending',
            )

    technical_wants_modify = technical_result.action == OrderAction.MODIFY.value
    protective_wants = protective_candidate is not None and sl_improves(side=side, current_sl=current_sl, proposed_sl=float(protective_candidate), tolerance=price_tolerance)
    should_consider_modify = technical_wants_modify or protective_wants or (
        effective_pending is not None and sl_improves(side=side, current_sl=current_sl, proposed_sl=float(effective_pending), tolerance=price_tolerance)
    )
    if not should_consider_modify:
        return MoneyStepMergeResult(management_result=TradeManagementResult(action=OrderAction.NONE.value, reason=money_eval.reason), state=new_state)

    if not sl_improves(side=side, current_sl=current_sl, proposed_sl=final_sl, tolerance=price_tolerance):
        return MoneyStepMergeResult(
            management_result=TradeManagementResult(action=OrderAction.NONE.value, reason='money_step_trailing_no_sl_improvement'),
            state=new_state,
            skip_reason='money_step_trailing_no_sl_improvement',
        )

    confirmed = new_state.confirmed_protective_sl
    if confirmed is not None and abs(confirmed - final_sl) <= price_tolerance and not technical_wants_modify:
        return MoneyStepMergeResult(
            management_result=TradeManagementResult(action=OrderAction.NONE.value, reason='money_step_trailing_identical_sl'),
            state=new_state,
            skip_reason='money_step_trailing_identical_sl',
        )

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

    if reason_code == REASON_PIP_TRAIL_STEP or (new_state.be_plus_confirmed and pip_sl is not None and abs(final_sl - float(pip_sl)) <= price_tolerance):
        reason_code = REASON_PIP_TRAIL_STEP
    elif not new_state.be_plus_confirmed and money_eval.activated:
        reason_code = REASON_BE_PLUS_NET_PROFIT
    elif technical_wants_modify:
        reason_code = 'TECHNICAL_TRAILING'

    reason_parts = []
    if technical_wants_modify:
        reason_parts.append(technical_result.reason)
    if reason_code == REASON_BE_PLUS_NET_PROFIT:
        reason_parts.append(f'{REASON_BE_PLUS_NET_PROFIT}: locked={params.initial_locked_profit_money:.2f}')
    elif reason_code == REASON_PIP_TRAIL_STEP:
        reason_parts.append(f'{REASON_PIP_TRAIL_STEP}: step_pips={trailing_step_pips}')
    elif money_eval.activated:
        reason_parts.append(f'MONEY_STEP_TRAILING: locked={money_eval.locked_profit_money:.2f} steps={money_eval.completed_steps}')

    # Pending until ACK — do not mark confirmed here.
    pending_state = MoneyStepTrailingState(
        peak_net_profit_money=new_state.peak_net_profit_money,
        money_trailing_step_index=new_state.money_trailing_step_index,
        locked_profit_money=new_state.locked_profit_money,
        last_money_trailing_sl=new_state.last_money_trailing_sl,
        be_plus_confirmed=new_state.be_plus_confirmed,
        confirmed_protective_sl=new_state.confirmed_protective_sl,
        pending_protective_sl=final_sl,
        pending_trailing_reason=reason_code,
        pip_trail_confirmed_steps=new_state.pip_trail_confirmed_steps,
        computed_be_plus_sl=new_state.computed_be_plus_sl if new_state.computed_be_plus_sl is not None else money_sl,
        next_pip_trail_sl=new_state.next_pip_trail_sl,
        last_trailing_modify_status='PENDING',
        last_trailing_broker_error=None,
        trailing_reason_code=reason_code,
    )
    return MoneyStepMergeResult(
        management_result=TradeManagementResult(
            action=OrderAction.MODIFY.value,
            reason='; '.join(reason_parts) if reason_parts else reason_code,
            stop_loss=final_sl,
            take_profit=modify_take_profit,
        ),
        state=pending_state,
    )
