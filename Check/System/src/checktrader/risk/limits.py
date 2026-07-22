from __future__ import annotations

from datetime import UTC, datetime, timedelta

from checktrader.config.models import LimitsConfig
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
    return state


def validate_limits(state: LimitState, config: LimitsConfig, now: datetime) -> ReasonCode:
    reset_if_new_day(state, now)
    if config.max_daily_trades and state.daily_trades >= config.max_daily_trades:
        return ReasonCode.RISK_DAILY_TRADES_LIMIT
    if config.max_consecutive_losses and state.consecutive_losses >= config.max_consecutive_losses:
        return ReasonCode.RISK_CONSECUTIVE_LOSSES_LIMIT
    if state.cooldown_until is not None and now < state.cooldown_until:
        return ReasonCode.RISK_COOLDOWN_ACTIVE
    return ReasonCode.RISK_ACCEPTED


def record_trade_open(state: LimitState, now: datetime) -> None:
    reset_if_new_day(state, now)
    state.daily_trades += 1
    state.last_trade_at = now


def record_trade_close(state: LimitState, config: LimitsConfig, now: datetime, profit: float) -> None:
    if profit < 0.0:
        state.consecutive_losses += 1
        # Cooldown expressed as M1 bars (1 M1 bar == 1 minute)
        state.cooldown_until = now + timedelta(minutes=config.cooldown_m1_bars)
    else:
        state.consecutive_losses = 0
        state.cooldown_until = None


def apply_error_cooldown(state: LimitState, config: LimitsConfig, now: datetime) -> None:
    """Apply short cooldown after a bridge/execution error."""
    state.cooldown_until = now + timedelta(seconds=config.cooldown_error_seconds)
