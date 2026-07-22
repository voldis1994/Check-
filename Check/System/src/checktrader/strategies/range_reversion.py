from __future__ import annotations

from checktrader.domain.enums import Decision, MarketRegime, ReasonCode, Side, StrategyType
from checktrader.domain.models import StrategyResult, StrategySignal
from checktrader.market_data.bars import closed_bars, lower_wick, upper_wick
from checktrader.market_data.indicators import adx, atr
from checktrader.strategies.base import StrategyContext


class RangeReversionStrategy:
    """
    Section 9: Range Reversion (boundary rejection).

    BUY at range bottom:
      - Close is within zone_pct of range bottom: close <= lo + zone_pct * width
      - Lower wick / candle range >= wick_pct  (wick toward boundary)
      - Close in upper half of bar: close > (high + low) / 2
      - Entry at current ask; stop below lo - stop_buffer_atr*ATR
      - TP: entry + (entry - stop) * take_profit_rr

    SELL at range top: mirror image.

    No-trade zone: if close is in the middle (neither zone), skip.
    """

    def evaluate(self, context: StrategyContext) -> StrategyResult:
        cfg = context.config.strategies.range_reversion
        if not cfg.enabled:
            return StrategyResult(Decision.SKIP, ReasonCode.NO_STRATEGY_FOR_REGIME)
        if context.regime.regime != MarketRegime.RANGE:
            return StrategyResult(Decision.SKIP, ReasonCode.NO_STRATEGY_FOR_REGIME)

        bars = closed_bars(context.m15)
        range_lb = context.config.regimes.range.range_lookback
        if len(bars) < range_lb:
            return StrategyResult(Decision.HOLD, ReasonCode.RANGE_FILTERS_NOT_READY)

        av = atr(bars, cfg.atr_period)
        ax, _, _ = adx(bars, cfg.adx_period)
        a = av[-1]
        x = ax[-1]
        if a is None or x is None:
            return StrategyResult(Decision.HOLD, ReasonCode.RANGE_FILTERS_NOT_READY)
        a = float(a)
        x = float(x)

        # Use range boundaries that the regime detector already established
        window = bars[-range_lb:]
        hi = max(b.high for b in window)
        lo = min(b.low for b in window)
        width = hi - lo
        if width <= 0:
            return StrategyResult(Decision.HOLD, ReasonCode.RANGE_FILTERS_NOT_READY)

        last = bars[-1]
        candle_range = last.high - last.low
        mid = (last.high + last.low) / 2.0

        buy_zone_hi = lo + cfg.zone_pct * width
        sell_zone_lo = hi - cfg.zone_pct * width

        # Price in neither zone → no trade
        if last.close > buy_zone_hi and last.close < sell_zone_lo:
            return StrategyResult(Decision.HOLD, ReasonCode.RANGE_MIDDLE_NO_TRADE)

        if last.close <= buy_zone_hi:
            # BUY signal: need lower wick and close in upper half of candle
            lw = lower_wick(last)
            lw_ratio = lw / candle_range if candle_range > 0 else 0.0
            if lw_ratio < cfg.wick_pct:
                return StrategyResult(
                    Decision.HOLD,
                    ReasonCode.NO_RANGE_BOUNDARY_REJECTION,
                    diagnostics={"wick_ratio": lw_ratio, "side": "BUY"},
                )
            if last.close <= mid:
                return StrategyResult(
                    Decision.HOLD, ReasonCode.NO_RANGE_BOUNDARY_REJECTION, diagnostics={"reason": "close below mid"}
                )
            entry = context.market.ask
            stop = lo - cfg.stop_buffer_atr * a
            tp = entry + (entry - stop) * cfg.take_profit_rr
            return StrategyResult(
                Decision.OPEN,
                ReasonCode.RANGE_BUY_SIGNAL,
                StrategySignal(
                    StrategyType.RANGE_REVERSION,
                    Side.BUY,
                    context.specs.symbol,
                    entry,
                    stop,
                    tp,
                    ReasonCode.RANGE_BUY_SIGNAL,
                ),
            )

        # SELL signal: need upper wick and close in lower half of candle
        uw = upper_wick(last)
        uw_ratio = uw / candle_range if candle_range > 0 else 0.0
        if uw_ratio < cfg.wick_pct:
            return StrategyResult(
                Decision.HOLD,
                ReasonCode.NO_RANGE_BOUNDARY_REJECTION,
                diagnostics={"wick_ratio": uw_ratio, "side": "SELL"},
            )
        if last.close >= mid:
            return StrategyResult(
                Decision.HOLD, ReasonCode.NO_RANGE_BOUNDARY_REJECTION, diagnostics={"reason": "close above mid"}
            )
        entry = context.market.bid
        stop = hi + cfg.stop_buffer_atr * a
        tp = entry - (stop - entry) * cfg.take_profit_rr
        return StrategyResult(
            Decision.OPEN,
            ReasonCode.RANGE_SELL_SIGNAL,
            StrategySignal(
                StrategyType.RANGE_REVERSION,
                Side.SELL,
                context.specs.symbol,
                entry,
                stop,
                tp,
                ReasonCode.RANGE_SELL_SIGNAL,
            ),
        )
