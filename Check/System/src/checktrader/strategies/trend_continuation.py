"""Section 8: Trend Continuation (pullback-to-EMA20, M5 context + M1 trigger)."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from checktrader.domain.enums import Decision, MarketRegime, ReasonCode, SetupState, Side, StrategyType
from checktrader.domain.models import Setup, StrategyResult, StrategySignal
from checktrader.market_data.bars import closed_bars
from checktrader.market_data.indicators import atr, ema
from checktrader.market_data.swings import last_swing_high, last_swing_low
from checktrader.setups.state_machine import transition
from checktrader.strategies.base import StrategyContext


def _slope(vals: list[float | None], lookback: int) -> float | None:
    """Slope of EMA over lookback bars normalized by nothing (caller divides by ATR)."""
    if len(vals) < lookback + 1:
        return None
    v_now = vals[-1]
    v_prev = vals[-1 - lookback]
    if v_now is None or v_prev is None:
        return None
    return float(v_now) - float(v_prev)


def _check_trigger(
    setup: Setup,
    context: StrategyContext,
    a: float,
    cfg: Any,
) -> tuple[list[str], list[str]]:
    """Return (passed_conditions, failed_conditions) for the M1 trigger check."""
    m1_bars = closed_bars(context.m1)
    if not m1_bars:
        return [], ["no_closed_m1"]
    last = m1_bars[-1]

    trigger_buf = max(cfg.trigger_buffer_atr * a, cfg.trigger_buffer_ticks * context.specs.tick_size)
    candle_range = last.high - last.low
    m1_body = abs(last.close - last.open)
    body_ratio = m1_body / candle_range if candle_range > 0 else 0.0
    entry_dist = abs(last.close - setup.trigger_level)

    passed: list[str] = []
    failed: list[str] = []

    if setup.side == Side.BUY:
        if last.close > setup.trigger_level + trigger_buf:
            passed.append("close_beyond_trigger")
        else:
            failed.append("close_beyond_trigger")
        if last.close > last.open:
            passed.append("bullish_candle")
        else:
            failed.append("bullish_candle")
    else:
        if last.close < setup.trigger_level - trigger_buf:
            passed.append("close_beyond_trigger")
        else:
            failed.append("close_beyond_trigger")
        if last.close < last.open:
            passed.append("bearish_candle")
        else:
            failed.append("bearish_candle")

    if body_ratio >= cfg.body_ratio_min:
        passed.append("body_ratio")
    else:
        failed.append("body_ratio")

    if a > 0 and candle_range <= cfg.max_candle_atr * a:
        passed.append("range_not_overextended")
    else:
        failed.append("range_not_overextended")

    if a > 0 and entry_dist <= cfg.entry_distance_atr * a:
        passed.append("entry_distance")
    else:
        failed.append("entry_distance")

    return passed, failed


class TrendContinuationStrategy:
    """
    Section 8: Trend Continuation (pullback-to-EMA20).

    M5 context evaluation creates an ARMED setup when:
      - Regime is TREND_UP (BUY) or TREND_DOWN (SELL)
      - M5 EMA20 > EMA50 (TREND_UP) / EMA20 < EMA50 (TREND_DOWN)
      - M5 close > EMA50 (TREND_UP) / close < EMA50 (TREND_DOWN)
      - EMA20 slope is positive (TREND_UP) / negative (TREND_DOWN)
      - M5 bar low in pullback zone [EMA20 - zone_low*ATR, EMA20 + zone_high*ATR] (BUY)
      - M5 close not below EMA50 - invalidation_atr*ATR (invalidation)

    ARMED setup persists in SetupRepository and is triggered by closed M1:
      - close beyond trigger_price ± buffer
      - body/range >= body_ratio_min
      - range <= max_candle_atr * ATR
      - |close - trigger_price| <= entry_distance_atr * ATR
      - close > open (BUY) / close < open (SELL)

    On TRIGGERED → Decision.OPEN with StrategySignal.
    Diagnostics include passed_conditions / failed_conditions lists.
    """

    def evaluate(self, context: StrategyContext) -> StrategyResult:
        cfg = context.config.strategies.trend_continuation
        if not cfg.enabled:
            return StrategyResult(Decision.SKIP, ReasonCode.NO_STRATEGY_FOR_REGIME)

        regime = context.regime.regime
        # TRANSITION often wraps a real impulse (EMA/ADX not fully stacked yet).
        # Still allow pullback continuation when M5 filters below pass.
        if regime not in {MarketRegime.TREND_UP, MarketRegime.TREND_DOWN, MarketRegime.TRANSITION}:
            return StrategyResult(Decision.SKIP, ReasonCode.NO_STRATEGY_FOR_REGIME)

        # M5 context indicators
        trend_cfg = context.config.regimes.trend
        m5_bars = closed_bars(context.m5)
        min_bars = max(cfg.atr_period, trend_cfg.ema50_period, trend_cfg.ema20_period) + trend_cfg.slope_lookback + 1
        if len(m5_bars) < min_bars:
            return StrategyResult(
                Decision.HOLD, ReasonCode.TREND_FILTERS_NOT_READY, diagnostics={"m5_bars": len(m5_bars)}
            )

        e20 = ema(m5_bars, trend_cfg.ema20_period)
        e50 = ema(m5_bars, trend_cfg.ema50_period)
        av = atr(m5_bars, cfg.atr_period)

        ema20_raw = e20[-1]
        ema50_raw = e50[-1]
        a_raw = av[-1]
        if any(v is None for v in (ema20_raw, ema50_raw, a_raw)):
            return StrategyResult(Decision.HOLD, ReasonCode.TREND_FILTERS_NOT_READY)

        ema20 = float(ema20_raw)  # type: ignore[arg-type]
        ema50 = float(ema50_raw)  # type: ignore[arg-type]
        a = float(a_raw)  # type: ignore[arg-type]
        if a <= 0:
            return StrategyResult(Decision.HOLD, ReasonCode.TREND_FILTERS_NOT_READY)

        last_m5 = m5_bars[-1]

        # EMA20 slope (raw price delta; normalize by ATR at caller site)
        slope_delta = _slope(e20, trend_cfg.slope_lookback)
        slope_atr = (slope_delta / a) if slope_delta is not None and a > 0 else None

        # ── Phase 1: manage existing ARMED setups ─────────────────────────────
        active = context.setups.active(symbol=context.specs.symbol, strategy=StrategyType.TREND_CONTINUATION)

        for setup in list(active):
            # Invalidation: M5 close crosses EMA50 in wrong direction
            if setup.side == Side.BUY:
                invalidation_level = ema50 - cfg.invalidation_atr * a
                if last_m5.close < invalidation_level:
                    transition(setup, SetupState.CANCELLED)
                    context.setups.upsert(setup)
                    continue
            else:
                invalidation_level = ema50 + cfg.invalidation_atr * a
                if last_m5.close > invalidation_level:
                    transition(setup, SetupState.CANCELLED)
                    context.setups.upsert(setup)
                    continue

            # M1 trigger check
            passed, failed = _check_trigger(setup, context, a, cfg)
            m1_bars = closed_bars(context.m1)
            last_m1 = m1_bars[-1] if m1_bars else None
            diag: dict[str, object] = {
                "passed_conditions": passed,
                "failed_conditions": failed,
                "trigger_level": setup.trigger_level,
                "ema20": ema20,
                "ema50": ema50,
            }
            if last_m1 is not None:
                candle_range = last_m1.high - last_m1.low
                diag["body_ratio"] = abs(last_m1.close - last_m1.open) / candle_range if candle_range > 0 else 0.0
                diag["candle_range_atr"] = candle_range / a
                diag["entry_dist_atr"] = abs(last_m1.close - setup.trigger_level) / a

            if not failed:
                transition(setup, SetupState.TRIGGERED)
                context.setups.upsert(setup)
                entry = context.market.ask if setup.side == Side.BUY else context.market.bid
                tp = (
                    entry + (entry - setup.stop_loss) * cfg.take_profit_rr
                    if setup.side == Side.BUY
                    else entry - (setup.stop_loss - entry) * cfg.take_profit_rr
                )
                reason = ReasonCode.TREND_BUY_SIGNAL if setup.side == Side.BUY else ReasonCode.TREND_SELL_SIGNAL
                return StrategyResult(
                    Decision.OPEN,
                    reason,
                    StrategySignal(
                        StrategyType.TREND_CONTINUATION,
                        setup.side,
                        context.specs.symbol,
                        entry,
                        setup.stop_loss,
                        tp,
                        reason,
                        setup.setup_id,
                    ),
                    setup,
                    diag,
                )
            # Still ARMED — return HOLD with diagnostics, stop looking for new setup
            return StrategyResult(Decision.HOLD, ReasonCode.TRIGGER_NOT_CONFIRMED, setup=setup, diagnostics=diag)

        # ── Phase 2: M5 context → create new ARMED setup ──────────────────────
        if regime == MarketRegime.TRANSITION:
            if ema20 > ema50 and last_m5.close > ema50:
                is_up = True
            elif ema20 < ema50 and last_m5.close < ema50:
                is_up = False
            else:
                return StrategyResult(
                    Decision.HOLD,
                    ReasonCode.REGIME_TRANSITION,
                    diagnostics={"ema20": ema20, "ema50": ema50, "close": last_m5.close},
                )
        else:
            is_up = regime == MarketRegime.TREND_UP

        # EMA alignment
        passed_arm: list[str] = []
        failed_arm: list[str] = []

        if is_up:
            if ema20 > ema50:
                passed_arm.append("ema_alignment")
            else:
                failed_arm.append("ema_alignment")
            if last_m5.close > ema50:
                passed_arm.append("close_above_ema50")
            else:
                failed_arm.append("close_above_ema50")
        else:
            if ema20 < ema50:
                passed_arm.append("ema_alignment")
            else:
                failed_arm.append("ema_alignment")
            if last_m5.close < ema50:
                passed_arm.append("close_below_ema50")
            else:
                failed_arm.append("close_below_ema50")

        # EMA20 slope
        if slope_atr is not None:
            slope_ok = (is_up and slope_atr >= trend_cfg.ema20_slope_atr) or (
                not is_up and slope_atr <= -trend_cfg.ema20_slope_atr
            )
            if slope_ok:
                passed_arm.append("ema20_slope")
            else:
                failed_arm.append("ema20_slope")
        else:
            failed_arm.append("ema20_slope")

        # Pullback zone
        zone_lo = ema20 - cfg.pullback_zone_low_atr * a
        zone_hi = ema20 + cfg.pullback_zone_high_atr * a

        if is_up:
            # BUY: bar low should dip into zone (touched pullback area)
            if last_m5.low <= zone_hi and last_m5.high >= zone_lo:
                passed_arm.append("pullback_zone")
            else:
                failed_arm.append("pullback_zone")
            # Invalidation: M5 close must not be below EMA50 - invalidation_atr*ATR
            if last_m5.close >= ema50 - cfg.invalidation_atr * a:
                passed_arm.append("not_invalidated")
            else:
                failed_arm.append("not_invalidated")
        else:
            # SELL: bar high should spike into zone (touched pullback area above)
            sell_zone_lo = ema20 - cfg.pullback_zone_high_atr * a
            sell_zone_hi = ema20 + cfg.pullback_zone_low_atr * a
            if last_m5.high >= sell_zone_lo and last_m5.low <= sell_zone_hi:
                passed_arm.append("pullback_zone")
            else:
                failed_arm.append("pullback_zone")
            if last_m5.close <= ema50 + cfg.invalidation_atr * a:
                passed_arm.append("not_invalidated")
            else:
                failed_arm.append("not_invalidated")

        arm_diag: dict[str, object] = {
            "passed_conditions": passed_arm,
            "failed_conditions": failed_arm,
            "ema20": ema20,
            "ema50": ema50,
            "zone_lo": zone_lo,
            "zone_hi": zone_hi,
            "slope_atr": slope_atr,
        }

        if failed_arm:
            return StrategyResult(Decision.HOLD, ReasonCode.PULLBACK_NOT_FOUND, diagnostics=arm_diag)

        # Compute stop from M5 swing
        side = Side.BUY if is_up else Side.SELL
        if is_up:
            swing = last_swing_low(m5_bars, cfg.swing_lookback)
            raw_stop = (swing.price - cfg.stop_buffer_atr * a) if swing else (last_m5.low - cfg.stop_buffer_atr * a)
            min_stop = ema20 - cfg.stop_max_atr * a
            stop = max(raw_stop, min_stop)
            trigger_price = ema20
            if stop >= trigger_price:
                return StrategyResult(Decision.HOLD, ReasonCode.TREND_STRUCTURE_INVALID, diagnostics=arm_diag)
            rough_entry = trigger_price + cfg.entry_distance_atr * a
            tp = rough_entry + (rough_entry - stop) * cfg.take_profit_rr
        else:
            swing = last_swing_high(m5_bars, cfg.swing_lookback)
            raw_stop = (swing.price + cfg.stop_buffer_atr * a) if swing else (last_m5.high + cfg.stop_buffer_atr * a)
            max_stop = ema20 + cfg.stop_max_atr * a
            stop = min(raw_stop, max_stop)
            trigger_price = ema20
            if stop <= trigger_price:
                return StrategyResult(Decision.HOLD, ReasonCode.TREND_STRUCTURE_INVALID, diagnostics=arm_diag)
            rough_entry = trigger_price - cfg.entry_distance_atr * a
            tp = rough_entry - (stop - rough_entry) * cfg.take_profit_rr

        expiry = last_m5.time + timedelta(minutes=cfg.expiry_m1_bars)
        setup = Setup.create(
            context.specs.symbol,
            StrategyType.TREND_CONTINUATION,
            side,
            SetupState.ARMED,
            last_m5.time,
            trigger_price,
            stop,
            take_profit=tp,
            expires_at_bar=expiry,
            reason=ReasonCode.SETUP_ARMED,
            metadata={
                "ema20": ema20,
                "ema50": ema50,
                "atr": a,
                "regime": regime.value,
                "passed_conditions": passed_arm,
            },
        )
        context.setups.upsert(setup)
        arm_diag["setup_id"] = setup.setup_id
        return StrategyResult(
            Decision.HOLD,
            ReasonCode.SETUP_ARMED,
            setup=setup,
            diagnostics=arm_diag,
        )
