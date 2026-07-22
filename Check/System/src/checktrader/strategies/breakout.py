"""Section 10: Breakout (box excludes trigger candle, M1 retest trigger)."""

from __future__ import annotations

from datetime import timedelta

from checktrader.domain.enums import Decision, ReasonCode, SetupState, Side, StrategyType
from checktrader.domain.models import Candle, Setup, StrategyResult, StrategySignal
from checktrader.market_data.aggregation import timeframe_minutes
from checktrader.market_data.bars import closed_bars
from checktrader.market_data.indicators import atr
from checktrader.setups.state_machine import transition
from checktrader.strategies.base import StrategyContext


def _count_touches(bars: list[Candle], level: float, tol: float) -> int:
    """Count bars whose high or low is within `tol` of `level`."""
    return sum(1 for b in bars if abs(b.high - level) <= tol or abs(b.low - level) <= tol)


class BreakoutStrategy:
    """
    Section 10: Breakout.

    Box is defined from M5 bars BEFORE the last M5 bar (trigger candle excluded).
    Need >= box_min_m5_bars bars (after excluding last).

    Box width checked against M15 ATR.
    Both box sides require >= min_touches_per_side touches with touch_tol_atr tolerance.

    Default confirmation_mode=breakout_and_retest:
      - BUY: M5 close above box high + buffer → ARMED setup, wait for retest close ≤ hi + tol
      - SELL: mirror image
      - Retest candle must STILL close beyond boundary (not closed back inside)
      - False breakout: price closes back inside the box → cancel ARMED

    Confirmed breakout → OPEN.
    On confirmed OPEN, cancel any RANGE_REVERSION ARMED setups (handled by router).
    """

    def evaluate(self, context: StrategyContext) -> StrategyResult:
        cfg = context.config.strategies.breakout
        if not cfg.enabled:
            return StrategyResult(Decision.SKIP, ReasonCode.NO_STRATEGY_FOR_REGIME)

        # ATR from M15 bars (reference for width measurement)
        m15_bars = closed_bars(context.m15)
        if len(m15_bars) < cfg.atr_period:
            return StrategyResult(Decision.HOLD, ReasonCode.BREAKOUT_FILTERS_NOT_READY)
        av15 = atr(m15_bars, cfg.atr_period)
        a_raw = av15[-1]
        if a_raw is None:
            return StrategyResult(Decision.HOLD, ReasonCode.BREAKOUT_FILTERS_NOT_READY)
        a = float(a_raw)

        # Box from M5 bars BEFORE the last bar (exclude trigger/current candle)
        m5_bars = closed_bars(context.m5)

        # Last M15 bar for false-breakout and retest checks
        last_m15 = m15_bars[-1]  # noqa: F841

        tol = cfg.retest_tol_atr * a

        # ── Phase 1: manage existing ARMED breakout setups ──────────────────────
        # This must happen BEFORE any early-exit on insufficient box bars so that
        # false-breakout cancellation and retest triggering always run for live setups.
        if m5_bars:
            last_m5_for_mgmt = m5_bars[-1]
            for setup in context.setups.active(symbol=context.specs.symbol, strategy=StrategyType.BREAKOUT):
                fb_threshold = cfg.false_breakout_close_back_atr * a

                # False breakout: M5 or M15 close returns inside box
                if setup.side == Side.BUY and last_m5_for_mgmt.close < setup.trigger_level - fb_threshold:
                    transition(setup, SetupState.CANCELLED)
                    context.setups.upsert(setup)
                    return StrategyResult(
                        Decision.HOLD,
                        ReasonCode.FALSE_BREAKOUT,
                        setup=setup,
                        diagnostics={"trigger": setup.trigger_level, "close": last_m5_for_mgmt.close},
                    )
                if setup.side == Side.SELL and last_m5_for_mgmt.close > setup.trigger_level + fb_threshold:
                    transition(setup, SetupState.CANCELLED)
                    context.setups.upsert(setup)
                    return StrategyResult(
                        Decision.HOLD,
                        ReasonCode.FALSE_BREAKOUT,
                        setup=setup,
                        diagnostics={"trigger": setup.trigger_level, "close": last_m5_for_mgmt.close},
                    )

                # Retest: M5 (or M1) price returns near the broken level AND still closes beyond it
                if setup.side == Side.BUY:
                    retesting = last_m5_for_mgmt.low <= setup.trigger_level + tol
                    # Retest bar must still close above broken level (not closed back inside)
                    still_beyond = last_m5_for_mgmt.close > setup.trigger_level
                    if retesting and still_beyond:
                        transition(setup, SetupState.TRIGGERED)
                        context.setups.upsert(setup)
                        return StrategyResult(
                            Decision.OPEN,
                            ReasonCode.BREAKOUT_BUY_SIGNAL,
                            StrategySignal(
                                StrategyType.BREAKOUT,
                                Side.BUY,
                                context.specs.symbol,
                                context.market.ask,
                                setup.stop_loss,
                                setup.take_profit,
                                ReasonCode.BREAKOUT_BUY_SIGNAL,
                                setup.setup_id,
                            ),
                            setup,
                            {"retest_level": setup.trigger_level},
                        )
                else:
                    retesting = last_m5_for_mgmt.high >= setup.trigger_level - tol
                    still_beyond = last_m5_for_mgmt.close < setup.trigger_level
                    if retesting and still_beyond:
                        transition(setup, SetupState.TRIGGERED)
                        context.setups.upsert(setup)
                        return StrategyResult(
                            Decision.OPEN,
                            ReasonCode.BREAKOUT_SELL_SIGNAL,
                            StrategySignal(
                                StrategyType.BREAKOUT,
                                Side.SELL,
                                context.specs.symbol,
                                context.market.bid,
                                setup.stop_loss,
                                setup.take_profit,
                                ReasonCode.BREAKOUT_SELL_SIGNAL,
                                setup.setup_id,
                            ),
                            setup,
                            {"retest_level": setup.trigger_level},
                        )
                # Still waiting for retest
                return StrategyResult(
                    Decision.HOLD,
                    ReasonCode.BREAKOUT_RETEST_PENDING,
                    setup=setup,
                    diagnostics={"trigger": setup.trigger_level},
                )

        # ── Phase 2: no active setup — check if enough M5 bars for a box ────────
        # Need at least box_min_m5_bars + 1 (the +1 is the trigger candle being excluded)
        if len(m5_bars) < cfg.box_min_m5_bars + 1:
            return StrategyResult(Decision.HOLD, ReasonCode.BREAKOUT_FILTERS_NOT_READY)

        # Exclude the last M5 bar (trigger candle)
        box_source = m5_bars[:-1]
        box = box_source[-cfg.box_max_m5_bars :]
        hi = max(b.high for b in box)
        lo = min(b.low for b in box)
        width = hi - lo
        width_atr = width / a if a > 0 else 0.0

        # Last M5 bar (the trigger candle) for breakout direction check
        last_m5 = m5_bars[-1]

        # Box validity check
        if width_atr < cfg.width_min_atr or width_atr > cfg.width_max_atr:
            return StrategyResult(
                Decision.HOLD,
                ReasonCode.BREAKOUT_BOX_PENDING,
                diagnostics={"box_width_atr": width_atr, "reason": "width_out_of_range"},
            )

        touch_tol = cfg.touch_tol_atr * a
        hi_touches = _count_touches(box, hi, touch_tol)
        lo_touches = _count_touches(box, lo, touch_tol)
        if hi_touches < cfg.min_touches_per_side or lo_touches < cfg.min_touches_per_side:
            return StrategyResult(
                Decision.HOLD,
                ReasonCode.BREAKOUT_BOX_PENDING,
                diagnostics={
                    "reason": "insufficient_touches",
                    "hi_touches": hi_touches,
                    "lo_touches": lo_touches,
                    "min_required": cfg.min_touches_per_side,
                },
            )

        buffer = cfg.breakout_buffer_atr * a
        expiry = last_m5.time + timedelta(
            minutes=timeframe_minutes(context.config.instrument.timeframe_execution) * cfg.expiry_m1_bars
        )

        # Use the TRIGGER candle (last_m5) for breakout direction check
        if last_m5.close > hi + buffer:
            entry = context.market.ask
            stop = lo - cfg.stop_buffer_atr * a
            tp = entry + (entry - stop) * cfg.take_profit_rr
            if cfg.confirmation_mode == "breakout_and_retest":
                setup = Setup.create(
                    context.specs.symbol,
                    StrategyType.BREAKOUT,
                    Side.BUY,
                    SetupState.ARMED,
                    last_m5.time,
                    hi,  # trigger_level = box high (retest level)
                    stop,
                    take_profit=tp,
                    expires_at_bar=expiry,
                    reason=ReasonCode.SETUP_ARMED,
                    metadata={"box_high": hi, "box_low": lo, "box_width_atr": width_atr},
                )
                context.setups.upsert(setup)
                return StrategyResult(
                    Decision.HOLD,
                    ReasonCode.BREAKOUT_RETEST_PENDING,
                    setup=setup,
                    diagnostics={"box_high": hi, "box_low": lo, "box_width_atr": width_atr},
                )
            # breakout_only mode
            return StrategyResult(
                Decision.OPEN,
                ReasonCode.BREAKOUT_BUY_SIGNAL,
                StrategySignal(
                    StrategyType.BREAKOUT,
                    Side.BUY,
                    context.specs.symbol,
                    entry,
                    stop,
                    tp,
                    ReasonCode.BREAKOUT_BUY_SIGNAL,
                ),
                diagnostics={"box_high": hi, "box_low": lo, "box_width_atr": width_atr},
            )

        if last_m5.close < lo - buffer:
            entry = context.market.bid
            stop = hi + cfg.stop_buffer_atr * a
            tp = entry - (stop - entry) * cfg.take_profit_rr
            if cfg.confirmation_mode == "breakout_and_retest":
                setup = Setup.create(
                    context.specs.symbol,
                    StrategyType.BREAKOUT,
                    Side.SELL,
                    SetupState.ARMED,
                    last_m5.time,
                    lo,  # trigger_level = box low (retest level)
                    stop,
                    take_profit=tp,
                    expires_at_bar=expiry,
                    reason=ReasonCode.SETUP_ARMED,
                    metadata={"box_high": hi, "box_low": lo, "box_width_atr": width_atr},
                )
                context.setups.upsert(setup)
                return StrategyResult(
                    Decision.HOLD,
                    ReasonCode.BREAKOUT_RETEST_PENDING,
                    setup=setup,
                    diagnostics={"box_high": hi, "box_low": lo, "box_width_atr": width_atr},
                )
            return StrategyResult(
                Decision.OPEN,
                ReasonCode.BREAKOUT_SELL_SIGNAL,
                StrategySignal(
                    StrategyType.BREAKOUT,
                    Side.SELL,
                    context.specs.symbol,
                    entry,
                    stop,
                    tp,
                    ReasonCode.BREAKOUT_SELL_SIGNAL,
                ),
                diagnostics={"box_high": hi, "box_low": lo, "box_width_atr": width_atr},
            )

        return StrategyResult(
            Decision.HOLD,
            ReasonCode.NO_BREAKOUT_TRIGGER,
            diagnostics={"box_width_atr": width_atr, "last_m5_close": last_m5.close, "box_hi": hi, "box_lo": lo},
        )
