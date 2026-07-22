"""Full risk limits tests — daily trades, consecutive losses, daily_loss_limit_r."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from checktrader.config.loader import load_config
from checktrader.config.models import LimitsConfig, RiskConfig
from checktrader.domain.enums import ReasonCode
from checktrader.domain.models import LimitState
from checktrader.risk.limits import (
    apply_error_cooldown,
    record_trade_close,
    record_trade_open,
    validate_limits,
)


def _state() -> LimitState:
    return LimitState(trade_date="")


def _now() -> datetime:
    return datetime(2026, 7, 1, 9, 0, 0, tzinfo=UTC)


def _initialized_state(now: datetime | None = None) -> LimitState:
    """Return a LimitState pre-initialized for today so reset_if_new_day doesn't clear it."""
    from checktrader.risk.limits import today_key

    t = now or _now()
    return LimitState(trade_date=today_key(t))


def _limits_cfg(**overrides: object) -> LimitsConfig:
    cfg = load_config()
    return cfg.limits.model_copy(update=overrides)


def _risk_cfg(**overrides: object) -> RiskConfig:
    cfg = load_config()
    return cfg.risk.model_copy(update=overrides)


# ── Daily trades limit ─────────────────────────────────────────────────────────


def test_daily_trades_allowed_below_limit() -> None:
    cfg = _limits_cfg(max_daily_trades=3)
    state = _initialized_state()
    now = _now()
    for _ in range(3):
        assert validate_limits(state, cfg, now) == ReasonCode.RISK_ACCEPTED
        record_trade_open(state, now)


def test_daily_trades_blocked_at_limit() -> None:
    cfg = _limits_cfg(max_daily_trades=3)
    state = _initialized_state()
    now = _now()
    for _ in range(3):
        record_trade_open(state, now)
    result = validate_limits(state, cfg, now)
    assert result == ReasonCode.RISK_DAILY_TRADES_LIMIT


def test_daily_trades_reset_on_new_day() -> None:
    cfg = _limits_cfg(max_daily_trades=2)
    state = _initialized_state()
    today = _now()
    record_trade_open(state, today)
    record_trade_open(state, today)
    assert validate_limits(state, cfg, today) == ReasonCode.RISK_DAILY_TRADES_LIMIT

    tomorrow = today + timedelta(days=1)
    result = validate_limits(state, cfg, tomorrow)
    assert result == ReasonCode.RISK_ACCEPTED


# ── Consecutive losses cooldown ────────────────────────────────────────────────


def test_consecutive_losses_limit_fires() -> None:
    cfg = _limits_cfg(max_consecutive_losses=2, cooldown_m1_bars=0)
    state = _initialized_state()
    now = _now()
    record_trade_close(state, cfg, now, profit=-1.0)
    assert validate_limits(state, cfg, now) == ReasonCode.RISK_ACCEPTED
    record_trade_close(state, cfg, now, profit=-1.0)
    result = validate_limits(state, cfg, now)
    assert result == ReasonCode.RISK_CONSECUTIVE_LOSSES_LIMIT


def test_win_resets_consecutive_losses() -> None:
    cfg = _limits_cfg(max_consecutive_losses=3)
    state = _initialized_state()
    now = _now()
    record_trade_close(state, cfg, now, profit=-1.0)
    record_trade_close(state, cfg, now, profit=-1.0)
    record_trade_close(state, cfg, now, profit=5.0)  # win resets counter
    assert state.consecutive_losses == 0
    assert validate_limits(state, cfg, now) == ReasonCode.RISK_ACCEPTED


def test_cooldown_blocks_trade() -> None:
    cfg = _limits_cfg(max_consecutive_losses=3, cooldown_m1_bars=5)
    state = _initialized_state()
    now = _now()
    record_trade_close(state, cfg, now, profit=-1.0)
    assert state.cooldown_until is not None
    future_just_before = state.cooldown_until - timedelta(seconds=1)
    result = validate_limits(state, cfg, future_just_before)
    assert result == ReasonCode.RISK_COOLDOWN_ACTIVE


def test_cooldown_lifts_after_expiry() -> None:
    cfg = _limits_cfg(cooldown_m1_bars=1)
    state = _initialized_state()
    now = _now()
    record_trade_close(state, cfg, now, profit=-1.0)
    after_cooldown = state.cooldown_until + timedelta(seconds=1)  # type: ignore[operator]
    result = validate_limits(state, cfg, after_cooldown)
    assert result == ReasonCode.RISK_ACCEPTED


# ── Daily loss limit R ─────────────────────────────────────────────────────────


def test_daily_loss_limit_blocks_when_exceeded() -> None:
    lim_cfg = _limits_cfg(max_daily_trades=99, max_consecutive_losses=99, cooldown_m1_bars=0)
    risk_cfg = _risk_cfg(daily_loss_limit_r=2.0)
    state = _initialized_state()
    now = _now()

    # Lose 1R twice → total 2R, should hit limit
    record_trade_close(state, lim_cfg, now, profit=-100.0, risk_amount=100.0)  # 1R
    assert validate_limits(state, lim_cfg, now, risk_cfg) == ReasonCode.RISK_ACCEPTED
    record_trade_close(state, lim_cfg, now, profit=-100.0, risk_amount=100.0)  # another 1R
    result = validate_limits(state, lim_cfg, now, risk_cfg)
    assert result == ReasonCode.RISK_DAILY_LOSS_LIMIT


def test_daily_loss_limit_resets_on_new_day() -> None:
    lim_cfg = _limits_cfg(cooldown_m1_bars=0)
    risk_cfg = _risk_cfg(daily_loss_limit_r=1.0)
    state = _initialized_state()
    today = _now()
    record_trade_close(state, lim_cfg, today, profit=-100.0, risk_amount=100.0)
    assert validate_limits(state, lim_cfg, today, risk_cfg) == ReasonCode.RISK_DAILY_LOSS_LIMIT

    tomorrow = today + timedelta(days=1)
    result = validate_limits(state, lim_cfg, tomorrow, risk_cfg)
    assert result == ReasonCode.RISK_ACCEPTED
    assert state.daily_loss_r == pytest.approx(0.0)


def test_daily_loss_limit_zero_disabled() -> None:
    """daily_loss_limit_r=0 means limit is disabled."""
    lim_cfg = _limits_cfg(max_daily_trades=99, cooldown_m1_bars=0)
    risk_cfg = _risk_cfg(daily_loss_limit_r=0.0)
    state = _initialized_state()
    now = _now()
    # Accumulate large loss
    record_trade_close(state, lim_cfg, now, profit=-10000.0, risk_amount=100.0)
    result = validate_limits(state, lim_cfg, now, risk_cfg)
    # With limit=0 it's disabled; should not block on daily_loss_r alone
    assert result != ReasonCode.RISK_DAILY_LOSS_LIMIT


def test_daily_loss_limit_without_risk_config_not_checked() -> None:
    """When risk_config=None is passed, daily_loss_r limit is not evaluated."""
    lim_cfg = _limits_cfg()
    state = _initialized_state()
    state.daily_loss_r = 999.0  # huge accumulated loss
    now = _now()
    result = validate_limits(state, lim_cfg, now, None)
    # Should not trigger RISK_DAILY_LOSS_LIMIT when risk_config is None
    assert result != ReasonCode.RISK_DAILY_LOSS_LIMIT


# ── Error cooldown ─────────────────────────────────────────────────────────────


def test_error_cooldown_blocks_immediately() -> None:
    cfg = _limits_cfg(cooldown_error_seconds=30.0)
    state = _initialized_state()
    now = _now()
    apply_error_cooldown(state, cfg, now)
    result = validate_limits(state, cfg, now + timedelta(seconds=1))
    assert result == ReasonCode.RISK_COOLDOWN_ACTIVE


def test_error_cooldown_lifts_after_seconds() -> None:
    cfg = _limits_cfg(cooldown_error_seconds=5.0)
    state = _initialized_state()
    now = _now()
    apply_error_cooldown(state, cfg, now)
    after = now + timedelta(seconds=10)
    result = validate_limits(state, cfg, after)
    assert result == ReasonCode.RISK_ACCEPTED
