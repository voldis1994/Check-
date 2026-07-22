"""Exit pressure scoring for open positions — spread in absolute price."""

from __future__ import annotations

from dataclasses import dataclass

from checktrader.config.models import ExitPressureConfig
from checktrader.domain.enums import Side
from checktrader.domain.market import Candle
from checktrader.market_data.aggregator import hma
from checktrader.observability.reason_codes import ReasonCode


@dataclass(frozen=True, slots=True)
class ExitPressureResult:
    total: float
    pullback: float
    speed: float
    trend: float
    rejection: float
    spread: float
    reason: ReasonCode
    critical_close: bool


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def compute_exit_pressure(
    *,
    side: Side,
    peak_net_profit: float,
    current_net_profit: float,
    recent_m1: list[Candle],
    current_spread_price: float,
    median_spread_price: float,
    trailing_step_price: float,
    config: ExitPressureConfig,
) -> ExitPressureResult:
    if not config.enabled:
        return ExitPressureResult(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, ReasonCode.TRAILING_WAITING_ACTIVATION, False)
    eps = 1e-9
    giveback = (peak_net_profit - current_net_profit) / max(abs(peak_net_profit), eps)
    pullback = _clamp(giveback)

    speed = 0.0
    if len(recent_m1) >= 4:
        bodies = [abs(c.close - c.open) for c in recent_m1[-4:]]
        progress = 0.0
        for c in recent_m1[-4:]:
            if side is Side.BUY:
                progress += c.close - c.open
            else:
                progress += c.open - c.close
        shrinking = bodies[0] > bodies[-1]
        adverse = progress < 0
        speed = _clamp((0.5 if shrinking else 0.0) + (0.5 if adverse else 0.0))

    trend = 0.0
    if len(recent_m1) >= 25:
        closes = [c.close for c in recent_m1]
        now = hma(closes, 21)
        prev = hma(closes[:-1], 21)
        if now is not None and prev is not None:
            if side is Side.BUY and now < prev:
                trend = _clamp((prev - now) / max(abs(prev), eps) * 50)
            if side is Side.SELL and now > prev:
                trend = _clamp((now - prev) / max(abs(prev), eps) * 50)

    rejection = 0.0
    if recent_m1:
        c = recent_m1[-1]
        rng = max(c.high - c.low, eps)
        if side is Side.BUY:
            upper = c.high - max(c.open, c.close)
            rejection = _clamp(upper / rng)
        else:
            lower = min(c.open, c.close) - c.low
            rejection = _clamp(lower / rng)

    spread_ratio = 0.0
    if median_spread_price > 0 and current_spread_price > 0:
        spread_ratio = current_spread_price / median_spread_price
    if trailing_step_price > 0 and current_spread_price > 0:
        spread_ratio = max(spread_ratio, current_spread_price / trailing_step_price)
    spread = _clamp((spread_ratio - 1.0) / 2.0)

    total = (
        pullback * config.pullback_weight
        + speed * config.speed_weight
        + trend * config.trend_weight
        + rejection * config.rejection_weight
        + spread * config.spread_weight
    )
    reason = ReasonCode.TRAILING_WAITING_ACTIVATION
    critical = False
    if total >= config.critical_threshold:
        non_spread = sum(1 for v in (pullback, speed, trend, rejection) if v >= 0.45)
        if config.critical_close_enabled and non_spread >= config.minimum_non_spread_confirmations_for_close:
            reason = ReasonCode.EXIT_PRESSURE_CRITICAL
            critical = True
        else:
            reason = ReasonCode.EXIT_PRESSURE_HIGH_LOCK
    elif total >= config.high_lock_threshold:
        reason = ReasonCode.EXIT_PRESSURE_HIGH_LOCK
    elif total >= config.tighten_threshold:
        reason = ReasonCode.EXIT_PRESSURE_TIGHTEN
    return ExitPressureResult(total, pullback, speed, trend, rejection, spread, reason, critical)
