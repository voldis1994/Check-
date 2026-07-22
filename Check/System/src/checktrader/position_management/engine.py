"""Select final protective SL from candidates (ATR distances, fixed-lot BE)."""

from __future__ import annotations

from dataclasses import dataclass

from checktrader.config.models import TradeManagementConfig
from checktrader.domain.enums import OrderAction, Side
from checktrader.domain.market import Candle
from checktrader.domain.money import SymbolSpecs, price_tolerance, sl_improves
from checktrader.domain.trailing import TrailingState
from checktrader.observability.reason_codes import ReasonCode
from checktrader.position_management.atr_grid_trailing import (
    atr_step_price,
    compute_grid_stop_loss,
    distance_stop_loss,
    favorable_price_move,
    snap_to_reached_grid,
)
from checktrader.position_management.breakeven import calculate_be_stop_loss
from checktrader.position_management.exit_pressure import compute_exit_pressure
from checktrader.position_management.high_lock import calculate_high_lock_sl
from checktrader.risk.stop_loss import atr_to_price_distance


@dataclass(frozen=True, slots=True)
class ProtectiveDecision:
    action: OrderAction
    stop_loss: float | None
    reason: ReasonCode
    close: bool = False
    state: TrailingState | None = None


def choose_protective_action(
    *,
    side: Side,
    open_price: float,
    volume: float,
    broker_sl: float,
    current_price: float,
    current_net_profit: float,
    swap: float,
    commission: float,
    specs: SymbolSpecs,
    config: TradeManagementConfig,
    trailing: TrailingState,
    recent_m1: list[Candle],
    current_spread_pips: float,
    median_spread_pips: float,
    bid: float,
    ask: float,
    atr: float,
) -> ProtectiveDecision:
    state = trailing
    state.broker_stop_loss = broker_sl
    state.current_bid = bid
    state.current_ask = ask
    state.current_net_profit = current_net_profit
    state.peak_net_profit = max(state.peak_net_profit, current_net_profit)
    tol = price_tolerance(point=specs.point, digits=specs.digits)
    step_price = atr_step_price(atr=atr, trailing_step_atr=config.trailing_step_atr, specs=specs)

    if state.pending_stop_loss is not None:
        if sl_improves(side=side, current_sl=broker_sl, proposed_sl=state.pending_stop_loss, tolerance=tol):
            return ProtectiveDecision(OrderAction.MODIFY, state.pending_stop_loss, ReasonCode.MODIFY_SENT, state=state)
        return ProtectiveDecision(OrderAction.NONE, None, ReasonCode.MODIFY_NOT_REQUIRED, state=state)

    pressure = compute_exit_pressure(
        side=side,
        peak_net_profit=state.peak_net_profit,
        current_net_profit=current_net_profit,
        recent_m1=recent_m1,
        current_spread_pips=current_spread_pips,
        median_spread_pips=median_spread_pips,
        trailing_step_price=step_price,
        pip_size=specs.pip_size,
        config=config.exit_pressure,
    )
    if pressure.critical_close:
        return ProtectiveDecision(OrderAction.CLOSE, None, ReasonCode.EXIT_PRESSURE_CRITICAL, close=True, state=state)

    candidates: list[float] = [broker_sl]
    reason = ReasonCode.TRAILING_WAITING_ACTIVATION
    move = favorable_price_move(side=side, open_price=open_price, current_price=current_price)
    be_activate_dist = atr_to_price_distance(atr, config.be_activation_atr, specs)
    trail_activate_dist = atr_to_price_distance(atr, config.trailing_activation_atr, specs)

    if not state.be_confirmed:
        if atr <= 0 or move + 1e-12 < be_activate_dist:
            return ProtectiveDecision(OrderAction.NONE, None, ReasonCode.TRAILING_WAITING_ACTIVATION, state=state)
        be_sl, be_reason = calculate_be_stop_loss(
            side=side,
            open_price=open_price,
            volume=volume,
            specs=specs,
            be_net_profit_money=config.be_net_profit_money,
            swap=swap,
            commission=commission,
        )
        state.calculated_be_sl = be_sl
        if be_sl is None:
            return ProtectiveDecision(OrderAction.NONE, None, be_reason, state=state)
        # Never worsen vs broker SL
        if side is Side.BUY and be_sl <= broker_sl + tol:
            return ProtectiveDecision(OrderAction.NONE, None, ReasonCode.MODIFY_NOT_REQUIRED, state=state)
        if side is Side.SELL and be_sl >= broker_sl - tol:
            return ProtectiveDecision(OrderAction.NONE, None, ReasonCode.MODIFY_NOT_REQUIRED, state=state)
        candidates.append(be_sl)
        reason = ReasonCode.BE_CALCULATED
    else:
        anchor = state.confirmed_be_sl or broker_sl
        if atr > 0 and move + 1e-12 >= trail_activate_dist:
            dist_sl = distance_stop_loss(
                side=side,
                current_price=current_price,
                atr=atr,
                trailing_distance_atr=config.trailing_distance_atr,
                specs=specs,
            )
            if dist_sl is not None:
                candidates.append(dist_sl)
                reason = ReasonCode.TRAILING_GRID_CALCULATED
        grid_sl, steps = compute_grid_stop_loss(
            side=side,
            confirmed_be_sl=anchor,
            current_price=current_price,
            atr=atr,
            trailing_step_atr=config.trailing_step_atr,
            specs=specs,
        )
        state.calculated_grid_sl = grid_sl
        state.calculated_grid_step = steps
        if grid_sl is not None:
            candidates.append(grid_sl)
            reason = ReasonCode.TRAILING_GRID_CALCULATED
        high_lock = calculate_high_lock_sl(
            side=side,
            open_price=open_price,
            volume=volume,
            specs=specs,
            peak_net_profit=state.peak_net_profit,
            swap=swap,
            commission=commission,
            config=config.high_lock,
            be_anchor=anchor,
            atr=atr,
            trailing_step_atr=config.trailing_step_atr,
            tolerance=tol,
        )
        state.calculated_high_lock_sl = high_lock
        if high_lock is not None:
            candidates.append(high_lock)
            if pressure.total >= config.exit_pressure.high_lock_threshold:
                reason = ReasonCode.HIGH_LOCK_ACTIVE
        if pressure.total >= config.exit_pressure.tighten_threshold and grid_sl is not None:
            tightened = snap_to_reached_grid(
                side=side,
                anchor_sl=anchor,
                proposed_sl=grid_sl,
                atr=atr,
                trailing_step_atr=config.trailing_step_atr,
                specs=specs,
                tolerance=tol,
            )
            if tightened is not None:
                candidates.append(tightened)
                state.calculated_pressure_sl = tightened
                reason = pressure.reason

    final = max(candidates) if side is Side.BUY else min(candidates)
    state.final_proposed_sl = final
    if not sl_improves(side=side, current_sl=broker_sl, proposed_sl=final, tolerance=tol):
        return ProtectiveDecision(OrderAction.NONE, None, ReasonCode.MODIFY_NOT_REQUIRED, state=state)
    # Explicit never-worsen rule vs broker SL
    if side is Side.BUY and final <= broker_sl:
        return ProtectiveDecision(OrderAction.NONE, None, ReasonCode.MODIFY_NOT_REQUIRED, state=state)
    if side is Side.SELL and final >= broker_sl:
        return ProtectiveDecision(OrderAction.NONE, None, ReasonCode.MODIFY_NOT_REQUIRED, state=state)
    state.pending_stop_loss = final
    state.last_reason = reason.value
    return ProtectiveDecision(OrderAction.MODIFY, final, reason, state=state)
