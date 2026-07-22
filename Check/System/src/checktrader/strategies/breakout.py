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

    Box defined by last box_max_m5_bars M5 bars (need >= box_min_m5_bars).
    Box width checked against M15 ATR.
    Two confirmation modes:
      - breakout_only: fire immediately on close beyond box + buffer
      - breakout_and_retest (default): ARMED state, wait for retest of broken level

    False breakout: if price closes back inside the box, cancel the ARMED setup.
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
        a = av15[-1]
        if a is None:
            return StrategyResult(Decision.HOLD, ReasonCode.BREAKOUT_FILTERS_NOT_READY)
        a = float(a)

        # Box from M5 bars
        m5_bars = closed_bars(context.m5)
        if len(m5_bars) < cfg.box_min_m5_bars:
            return StrategyResult(Decision.HOLD, ReasonCode.BREAKOUT_FILTERS_NOT_READY)

        box = m5_bars[-cfg.box_max_m5_bars :]  # at most box_max_m5_bars
        hi = max(b.high for b in box)
        lo = min(b.low for b in box)
        width = hi - lo
        width_atr = width / a

        # Check and manage any existing ARMED setups
        last_m15 = m15_bars[-1]
        tol = cfg.retest_tol_atr * a
        for setup in context.setups.active(symbol=context.specs.symbol, strategy=StrategyType.BREAKOUT):
            # False breakout: price closes back inside box
            fb_threshold = cfg.false_breakout_close_back_atr * a
            if setup.side == Side.BUY and last_m15.close < setup.trigger_price - fb_threshold:
                transition(setup, SetupState.CANCELLED)
                return StrategyResult(Decision.HOLD, ReasonCode.FALSE_BREAKOUT, setup=setup)
            if setup.side == Side.SELL and last_m15.close > setup.trigger_price + fb_threshold:
                transition(setup, SetupState.CANCELLED)
                return StrategyResult(Decision.HOLD, ReasonCode.FALSE_BREAKOUT, setup=setup)

            # Retest: price returns near the broken level
            if setup.side == Side.BUY:
                if last_m15.low <= setup.trigger_price + tol:
                    transition(setup, SetupState.TRIGGERED)
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
                    )
            else:
                if last_m15.high >= setup.trigger_price - tol:
                    transition(setup, SetupState.TRIGGERED)
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
                    )
            # Still waiting for retest
            return StrategyResult(Decision.HOLD, ReasonCode.BREAKOUT_RETEST_PENDING, setup=setup)

        # No active breakout setup; check if box is valid
        if width_atr < cfg.width_min_atr or width_atr > cfg.width_max_atr:
            return StrategyResult(
                Decision.HOLD, ReasonCode.BREAKOUT_BOX_PENDING, diagnostics={"box_width_atr": width_atr}
            )

        # Require minimum touches on each side
        touch_tol = cfg.touch_tol_atr * a
        if (
            _count_touches(box, hi, touch_tol) < cfg.min_touches_per_side
            or _count_touches(box, lo, touch_tol) < cfg.min_touches_per_side
        ):
            return StrategyResult(
                Decision.HOLD, ReasonCode.BREAKOUT_BOX_PENDING, diagnostics={"reason": "insufficient touches"}
            )

        buffer = cfg.breakout_buffer_atr * a
        expiry = last_m15.time + timedelta(
            minutes=timeframe_minutes(context.config.instrument.timeframe_execution) * cfg.expiry_m1_bars
        )

        # BUY breakout: close above box high + buffer
        if last_m15.close > hi + buffer:
            entry = context.market.ask
            stop = lo - cfg.stop_buffer_atr * a
            tp = entry + (entry - stop) * cfg.take_profit_rr
            if cfg.confirmation_mode == "breakout_and_retest":
                setup = Setup.create(
                    context.specs.symbol,
                    StrategyType.BREAKOUT,
                    Side.BUY,
                    SetupState.ARMED,
                    last_m15.time,
                    expiry,
                    hi,
                    stop,
                    tp,
                    ReasonCode.SETUP_ARMED,
                    {"box_high": hi, "box_low": lo, "box_width_atr": width_atr},
                )
                context.setups.upsert(setup)
                return StrategyResult(Decision.HOLD, ReasonCode.BREAKOUT_RETEST_PENDING, setup=setup)
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
            )

        # SELL breakout: close below box low - buffer
        if last_m15.close < lo - buffer:
            entry = context.market.bid
            stop = hi + cfg.stop_buffer_atr * a
            tp = entry - (stop - entry) * cfg.take_profit_rr
            if cfg.confirmation_mode == "breakout_and_retest":
                setup = Setup.create(
                    context.specs.symbol,
                    StrategyType.BREAKOUT,
                    Side.SELL,
                    SetupState.ARMED,
                    last_m15.time,
                    expiry,
                    lo,
                    stop,
                    tp,
                    ReasonCode.SETUP_ARMED,
                    {"box_high": hi, "box_low": lo, "box_width_atr": width_atr},
                )
                context.setups.upsert(setup)
                return StrategyResult(Decision.HOLD, ReasonCode.BREAKOUT_RETEST_PENDING, setup=setup)
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
            )

        return StrategyResult(Decision.HOLD, ReasonCode.NO_BREAKOUT_TRIGGER, diagnostics={"box_width_atr": width_atr})
