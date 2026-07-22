from __future__ import annotations

from checktrader.domain.enums import Decision, MarketRegime, ReasonCode, Side, StrategyType
from checktrader.domain.models import StrategyResult, StrategySignal
from checktrader.market_data.bars import body, closed_bars
from checktrader.market_data.indicators import adx, atr, ema
from checktrader.market_data.swings import last_swing_high, last_swing_low
from checktrader.strategies.base import StrategyContext


class TrendContinuationStrategy:
    """
    Section 8: Trend Continuation (pullback-to-EMA20).

    BUY  (TREND_UP):
      - Bar low enters pullback zone [EMA20 - zone_low_atr*ATR, EMA20 + zone_high_atr*ATR]
      - Bar close does NOT fall below EMA50 - invalidation_atr*ATR
      - Confirmation: body/range >= body_ratio_min AND range <= max_candle_atr*ATR
      - Entry: EMA20 + entry_distance_atr*ATR (stop order, filled at ask on next bar)
      - Stop: below swing low (- stop_buffer_atr*ATR), capped at stop_max_atr*ATR from entry
      - TP: entry + (entry - stop) * take_profit_rr

    SELL (TREND_DOWN): mirror image.
    """

    def evaluate(self, context: StrategyContext) -> StrategyResult:
        cfg = context.config.strategies.trend_continuation
        if not cfg.enabled:
            return StrategyResult(Decision.SKIP, ReasonCode.NO_STRATEGY_FOR_REGIME)

        regime = context.regime.regime
        if regime not in {MarketRegime.TREND_UP, MarketRegime.TREND_DOWN}:
            return StrategyResult(Decision.SKIP, ReasonCode.NO_STRATEGY_FOR_REGIME)

        bars = closed_bars(context.m15)
        min_bars = max(cfg.atr_period, cfg.adx_period, context.config.regimes.trend.ema50_period) + cfg.atr_period
        if len(bars) < min_bars:
            return StrategyResult(Decision.HOLD, ReasonCode.TREND_FILTERS_NOT_READY)

        e20 = ema(bars, context.config.regimes.trend.ema20_period)
        e50 = ema(bars, context.config.regimes.trend.ema50_period)
        av = atr(bars, cfg.atr_period)
        ax, _, _ = adx(bars, cfg.adx_period)

        ema20 = e20[-1]
        ema50 = e50[-1]
        a = av[-1]
        x = ax[-1]

        if any(v is None for v in (ema20, ema50, a, x)):
            return StrategyResult(Decision.HOLD, ReasonCode.TREND_FILTERS_NOT_READY)

        ema20 = float(ema20)  # type: ignore[arg-type]
        ema50 = float(ema50)  # type: ignore[arg-type]
        a = float(a)  # type: ignore[arg-type]
        x = float(x)  # type: ignore[arg-type]

        last = bars[-1]
        candle_range = last.high - last.low
        body_ratio = body(last) / candle_range if candle_range > 0 else 0.0

        # Candle quality filters
        if body_ratio < cfg.body_ratio_min:
            return StrategyResult(
                Decision.HOLD, ReasonCode.TRIGGER_NOT_CONFIRMED, diagnostics={"body_ratio": body_ratio}
            )
        if candle_range > cfg.max_candle_atr * a:
            return StrategyResult(
                Decision.HOLD, ReasonCode.PRICE_OVEREXTENDED, diagnostics={"candle_range_atr": candle_range / a}
            )

        trigger_buf = max(cfg.trigger_buffer_atr * a, cfg.trigger_buffer_ticks * context.specs.tick_size)

        if regime == MarketRegime.TREND_UP:
            zone_lo = ema20 - cfg.pullback_zone_low_atr * a
            zone_hi = ema20 + cfg.pullback_zone_high_atr * a
            invalidation = ema50 - cfg.invalidation_atr * a

            # Bar must touch the pullback zone
            if not (last.low <= zone_hi and last.high >= zone_lo):
                return StrategyResult(Decision.HOLD, ReasonCode.PULLBACK_NOT_FOUND)

            # Close must not breach invalidation
            if last.close < invalidation:
                return StrategyResult(Decision.HOLD, ReasonCode.PULLBACK_INVALIDATED)

            # Bullish close: candle must close above zone mid or above trigger
            if last.close < ema20 - trigger_buf:
                return StrategyResult(Decision.HOLD, ReasonCode.TRIGGER_NOT_CONFIRMED)

            # Entry above EMA20
            entry = ema20 + cfg.entry_distance_atr * a
            # Stop below recent swing low
            swing = last_swing_low(context.m15, context.config.strategies.trend_continuation.swing_lookback)
            raw_stop = (swing.price - cfg.stop_buffer_atr * a) if swing else (last.low - cfg.stop_buffer_atr * a)
            # Cap stop to stop_max_atr from entry
            min_stop = entry - cfg.stop_max_atr * a
            stop = max(raw_stop, min_stop)
            if stop >= entry:
                return StrategyResult(Decision.HOLD, ReasonCode.TREND_STRUCTURE_INVALID)

            tp = entry + (entry - stop) * cfg.take_profit_rr
            return StrategyResult(
                Decision.OPEN,
                ReasonCode.TREND_BUY_SIGNAL,
                StrategySignal(
                    StrategyType.TREND_CONTINUATION,
                    Side.BUY,
                    context.specs.symbol,
                    entry,
                    stop,
                    tp,
                    ReasonCode.TREND_BUY_SIGNAL,
                ),
            )

        # TREND_DOWN — mirror
        zone_lo = ema20 - cfg.pullback_zone_high_atr * a
        zone_hi = ema20 + cfg.pullback_zone_low_atr * a
        invalidation = ema50 + cfg.invalidation_atr * a

        if not (last.high >= zone_lo and last.low <= zone_hi):
            return StrategyResult(Decision.HOLD, ReasonCode.PULLBACK_NOT_FOUND)

        if last.close > invalidation:
            return StrategyResult(Decision.HOLD, ReasonCode.PULLBACK_INVALIDATED)

        if last.close > ema20 + trigger_buf:
            return StrategyResult(Decision.HOLD, ReasonCode.TRIGGER_NOT_CONFIRMED)

        entry = ema20 - cfg.entry_distance_atr * a
        swing = last_swing_high(context.m15, context.config.strategies.trend_continuation.swing_lookback)
        raw_stop = (swing.price + cfg.stop_buffer_atr * a) if swing else (last.high + cfg.stop_buffer_atr * a)
        max_stop = entry + cfg.stop_max_atr * a
        stop = min(raw_stop, max_stop)
        if stop <= entry:
            return StrategyResult(Decision.HOLD, ReasonCode.TREND_STRUCTURE_INVALID)

        tp = entry - (stop - entry) * cfg.take_profit_rr
        return StrategyResult(
            Decision.OPEN,
            ReasonCode.TREND_SELL_SIGNAL,
            StrategySignal(
                StrategyType.TREND_CONTINUATION,
                Side.SELL,
                context.specs.symbol,
                entry,
                stop,
                tp,
                ReasonCode.TREND_SELL_SIGNAL,
            ),
        )
