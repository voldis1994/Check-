from __future__ import annotations

from datetime import UTC, datetime, timedelta

from checktrader.config.models import LimitsConfig, RiskConfig
from checktrader.domain.enums import ReasonCode
from checktrader.domain.models import LimitState


def today_key(now: datetime) -> str:
    return now.astimezone(UTC).date().isoformat()


def reset_if_new_day(state: LimitState, now: datetime) -> LimitState:
    if state.trade_date != today_key(now):
        state.trade_date = today_key(now)
        state.daily_trades = 0
        state.consecutive_losses = 0
        state.cooldown_until = None
        state.last_trade_at = None
        state.daily_loss_r = 0.0
    return state


def validate_limits(
    state: LimitState,
    config: LimitsConfig,
    now: datetime,
    risk_config: RiskConfig | None = None,
) -> ReasonCode:
    reset_if_new_day(state, now)
    if config.max_daily_trades and state.daily_trades >= config.max_daily_trades:
        return ReasonCode.RISK_DAILY_TRADES_LIMIT
    if config.max_consecutive_losses and state.consecutive_losses >= config.max_consecutive_losses:
        return ReasonCode.RISK_CONSECUTIVE_LOSSES_LIMIT
    if state.cooldown_until is not None and now < state.cooldown_until:
        return ReasonCode.RISK_COOLDOWN_ACTIVE
    if (
        risk_config is not None
        and risk_config.daily_loss_limit_r > 0
        and state.daily_loss_r >= risk_config.daily_loss_limit_r
    ):
        return ReasonCode.RISK_DAILY_LOSS_LIMIT
    return ReasonCode.RISK_ACCEPTED


def record_trade_open(state: LimitState, now: datetime) -> None:
    reset_if_new_day(state, now)
    state.daily_trades += 1
    state.last_trade_at = now


def record_trade_close(
    state: LimitState,
    config: LimitsConfig,
    now: datetime,
    profit: float,
    risk_amount: float | None = None,
) -> None:
    """
    Record a closed trade.

    profit: raw P&L (negative = loss).
    risk_amount: the planned 1R risk in account currency; used to update daily_loss_r.
    When risk_amount is provided and the trade lost, the R-multiple loss is accumulated.
    """
    if profit < 0.0:
        state.consecutive_losses += 1
        state.cooldown_until = now + timedelta(minutes=config.cooldown_m1_bars)
        if risk_amount is not None and risk_amount > 0:
            r_loss = abs(profit) / risk_amount
            state.daily_loss_r += r_loss
    else:
        state.consecutive_losses = 0
        state.cooldown_until = None


def apply_error_cooldown(state: LimitState, config: LimitsConfig, now: datetime) -> None:
    """Apply short cooldown after a bridge/execution error."""
    state.cooldown_until = now + timedelta(seconds=config.cooldown_error_seconds)
