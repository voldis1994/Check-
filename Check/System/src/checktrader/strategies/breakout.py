"""Section 10: Breakout (M5 box + retest, plus M1 impulse range-break)."""

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

    Primary path — M5 consolidation box (trigger candle excluded) + optional retest.

    Fallback — M1 impulse break: last closed M1 closes beyond the prior N-bar
    high/low with a real body. This catches staircase NATURALGAS moves that never
    print a clean M5 box break + retest (common cause of NO_BREAKOUT_TRIGGER).
    M1 impulse always enters immediately (no retest wait).
    """

    def evaluate(self, context: StrategyContext) -> StrategyResult:
        cfg = context.config.strategies.breakout
        if not cfg.enabled:
            return StrategyResult(Decision.SKIP, ReasonCode.NO_STRATEGY_FOR_REGIME)

        m15_bars = closed_bars(context.m15)
        a: float | None = None
        if len(m15_bars) >= cfg.atr_period:
            av15 = atr(m15_bars, cfg.atr_period)
            a_raw = av15[-1]
            if a_raw is not None:
                a = float(a_raw)

        m5_bars = closed_bars(context.m5)
        tol = (cfg.retest_tol_atr * a) if a is not None else 0.0

        # ── Phase 1: manage existing ARMED breakout setups ──────────────────────
        if m5_bars and a is not None:
            last_m5_for_mgmt = m5_bars[-1]
            for setup in context.setups.active(symbol=context.specs.symbol, strategy=StrategyType.BREAKOUT):
                fb_threshold = cfg.false_breakout_close_back_atr * a

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

                if setup.side == Side.BUY:
                    retesting = last_m5_for_mgmt.low <= setup.trigger_level + tol
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
                return StrategyResult(
                    Decision.HOLD,
                    ReasonCode.BREAKOUT_RETEST_PENDING,
                    setup=setup,
                    diagnostics={"trigger": setup.trigger_level},
                )

        # ── Phase 2: M5 box break (classic) ─────────────────────────────────────
        if a is None:
            impulse = self._m1_impulse(context, atr_value=None)
            return impulse or StrategyResult(Decision.HOLD, ReasonCode.BREAKOUT_FILTERS_NOT_READY)

        if len(m5_bars) < cfg.box_min_m5_bars + 1:
            impulse = self._m1_impulse(context, atr_value=a)
            return impulse or StrategyResult(Decision.HOLD, ReasonCode.BREAKOUT_FILTERS_NOT_READY)

        box_source = m5_bars[:-1]
        box = box_source[-cfg.box_max_m5_bars :]
        hi = max(b.high for b in box)
        lo = min(b.low for b in box)
        width = hi - lo
        width_atr = width / a if a > 0 else 0.0
        last_m5 = m5_bars[-1]

        if width_atr < cfg.width_min_atr or width_atr > cfg.width_max_atr:
            impulse = self._m1_impulse(context, atr_value=a)
            return impulse or StrategyResult(
                Decision.HOLD,
                ReasonCode.BREAKOUT_BOX_PENDING,
                diagnostics={"box_width_atr": width_atr, "reason": "width_out_of_range"},
            )

        touch_tol = cfg.touch_tol_atr * a
        hi_touches = _count_touches(box, hi, touch_tol)
        lo_touches = _count_touches(box, lo, touch_tol)
        if hi_touches < cfg.min_touches_per_side or lo_touches < cfg.min_touches_per_side:
            impulse = self._m1_impulse(context, atr_value=a)
            return impulse or StrategyResult(
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
                    hi,
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
                    lo,
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

        impulse = self._m1_impulse(context, atr_value=a)
        return impulse or StrategyResult(
            Decision.HOLD,
            ReasonCode.NO_BREAKOUT_TRIGGER,
            diagnostics={"box_width_atr": width_atr, "last_m5_close": last_m5.close, "box_hi": hi, "box_lo": lo},
        )

    def _m1_impulse(self, context: StrategyContext, *, atr_value: float | None) -> StrategyResult | None:
        """Immediate OPEN when last M1 closes beyond the prior lookback range."""
        cfg = context.config.strategies.breakout
        if not cfg.m1_impulse_enabled:
            return None

        m1 = closed_bars(context.m1)
        need = cfg.m1_impulse_lookback + 1
        if len(m1) < need:
            return None

        a = atr_value
        if a is None or a <= 0:
            window = m1[-(cfg.atr_period + 1) :]
            spans = [b.high - b.low for b in window]
            a = sum(spans) / max(len(spans), 1)
        if a <= 0:
            return None

        prior = m1[-(cfg.m1_impulse_lookback + 1) : -1]
        last = m1[-1]
        hi = max(b.high for b in prior)
        lo = min(b.low for b in prior)
        buffer = cfg.breakout_buffer_atr * a
        body = abs(last.close - last.open)
        if body < cfg.m1_impulse_min_body_atr * a:
            return None

        if last.close > hi + buffer and last.close > last.open:
            entry = context.market.ask
            stop = min(lo, last.low) - cfg.stop_buffer_atr * a
            risk = entry - stop
            if risk <= 0:
                return None
            tp = entry + risk * cfg.take_profit_rr
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
                diagnostics={
                    "mode": "m1_impulse",
                    "lookback": cfg.m1_impulse_lookback,
                    "prior_high": hi,
                    "m1_close": last.close,
                    "atr": a,
                },
            )

        if last.close < lo - buffer and last.close < last.open:
            entry = context.market.bid
            stop = max(hi, last.high) + cfg.stop_buffer_atr * a
            risk = stop - entry
            if risk <= 0:
                return None
            tp = entry - risk * cfg.take_profit_rr
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
                diagnostics={
                    "mode": "m1_impulse",
                    "lookback": cfg.m1_impulse_lookback,
                    "prior_low": lo,
                    "m1_close": last.close,
                    "atr": a,
                },
            )
        return None
