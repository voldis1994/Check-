"""Section 9: Range Reversion (boundary rejection, M1 trigger)."""

from __future__ import annotations

from datetime import timedelta

from checktrader.domain.enums import Decision, MarketRegime, ReasonCode, SetupState, Side, StrategyType
from checktrader.domain.models import Setup, StrategyResult, StrategySignal
from checktrader.market_data.bars import closed_bars, lower_wick, upper_wick
from checktrader.market_data.indicators import atr
from checktrader.setups.state_machine import transition
from checktrader.strategies.base import StrategyContext
from checktrader.strategies.exits import hard_take_profit_price


class RangeReversionStrategy:
    """
    Section 9: Range Reversion (boundary rejection).

    Uses regime.metadata range_high/range_low when present; otherwise computes
    from the last range_lookback M15 bars.

    Middle zone → RANGE_MIDDLE_NO_TRADE (no setup created).

    BUY at range bottom:
      - Close is in the lower zone_pct fraction of the range
      - Lower wick / candle range >= wick_pct  (rejection wick toward boundary)
      - Close in upper half of candle
      ARMED setup created; expires after expiry_m1_bars minutes.

    M1 trigger:
      - Close above trigger_price (range low + stop_buffer / midpoint as reference)
      - RR >= take_profit_rr
      → Decision.OPEN

    Cancel if regime leaves RANGE.
    """

    def evaluate(self, context: StrategyContext) -> StrategyResult:
        cfg = context.config.strategies.range_reversion
        if not cfg.enabled:
            return StrategyResult(Decision.SKIP, ReasonCode.NO_STRATEGY_FOR_REGIME)
        if context.regime.regime != MarketRegime.RANGE:
            # Cancel any active range setups if regime flipped
            for setup in context.setups.active(symbol=context.specs.symbol, strategy=StrategyType.RANGE_REVERSION):
                transition(setup, SetupState.CANCELLED)
                context.setups.upsert(setup)
            return StrategyResult(Decision.SKIP, ReasonCode.NO_STRATEGY_FOR_REGIME)

        # ── Determine range boundaries ─────────────────────────────────────────
        regime_meta = context.regime.metadata if hasattr(context.regime, "metadata") else {}
        # Prefer boundaries from regime metadata (set by detect_range)
        rhi = regime_meta.get("range_high") if isinstance(regime_meta, dict) else None
        rlo = regime_meta.get("range_low") if isinstance(regime_meta, dict) else None

        if rhi is None or rlo is None:
            # Also check indicators metadata
            ind_meta = context.regime.indicators.metadata
            rhi = ind_meta.get("range_high")
            rlo = ind_meta.get("range_low")

        if rhi is None or rlo is None:
            # Fallback: compute from M15 bars
            m15_bars = closed_bars(context.m15)
            range_lb = context.config.regimes.range.range_lookback
            if len(m15_bars) < range_lb:
                return StrategyResult(Decision.HOLD, ReasonCode.RANGE_FILTERS_NOT_READY)
            window = m15_bars[-range_lb:]
            rhi = float(max(b.high for b in window))
            rlo = float(min(b.low for b in window))

        hi = float(rhi)
        lo = float(rlo)
        width = hi - lo
        if width <= 0:
            return StrategyResult(Decision.HOLD, ReasonCode.RANGE_FILTERS_NOT_READY)

        # ATR for stop computation
        m15_bars = closed_bars(context.m15)
        if len(m15_bars) < cfg.atr_period:
            return StrategyResult(Decision.HOLD, ReasonCode.RANGE_FILTERS_NOT_READY)
        av = atr(m15_bars, cfg.atr_period)
        a_raw = av[-1]
        if a_raw is None:
            return StrategyResult(Decision.HOLD, ReasonCode.RANGE_FILTERS_NOT_READY)
        a = float(a_raw)

        last_m15 = m15_bars[-1]

        # ── Phase 1: Check existing ARMED setups for M1 trigger ────────────────
        active = context.setups.active(symbol=context.specs.symbol, strategy=StrategyType.RANGE_REVERSION)

        for setup in list(active):
            # M1 trigger: last closed M1 bar
            m1_bars = closed_bars(context.m1)
            if not m1_bars:
                return StrategyResult(
                    Decision.HOLD, ReasonCode.TRIGGER_NOT_CONFIRMED, setup=setup, diagnostics={"reason": "no_closed_m1"}
                )
            last_m1 = m1_bars[-1]

            # Directional trigger: for BUY close must move up from low zone;
            # we use trigger_price stored in setup as the reference breakout level.
            if setup.side == Side.BUY:
                # M1 close must be above trigger level
                if last_m1.close <= setup.trigger_level:
                    return StrategyResult(
                        Decision.HOLD,
                        ReasonCode.TRIGGER_NOT_CONFIRMED,
                        setup=setup,
                        diagnostics={"m1_close": last_m1.close, "trigger": setup.trigger_level},
                    )
            else:
                if last_m1.close >= setup.trigger_level:
                    return StrategyResult(
                        Decision.HOLD,
                        ReasonCode.TRIGGER_NOT_CONFIRMED,
                        setup=setup,
                        diagnostics={"m1_close": last_m1.close, "trigger": setup.trigger_level},
                    )

            # Verify RR still holds at current entry price (only when hard TP is used)
            entry = context.market.ask if setup.side == Side.BUY else context.market.bid
            risk = abs(entry - setup.stop_loss)
            if risk <= 0:
                return StrategyResult(
                    Decision.HOLD,
                    ReasonCode.REWARD_RISK_TOO_LOW,
                    setup=setup,
                    diagnostics={"rr": 0.0},
                )
            if context.config.management.hard_take_profit:
                reward = abs(setup.take_profit - entry) if setup.take_profit else 0.0
                if reward / risk < cfg.take_profit_rr:
                    return StrategyResult(
                        Decision.HOLD,
                        ReasonCode.REWARD_RISK_TOO_LOW,
                        setup=setup,
                        diagnostics={"rr": reward / risk},
                    )

            transition(setup, SetupState.TRIGGERED)
            context.setups.upsert(setup)
            tp = hard_take_profit_price(
                entry=entry,
                stop=setup.stop_loss,
                side=setup.side,
                rr=cfg.take_profit_rr,
                enabled=context.config.management.hard_take_profit,
            )
            reason = ReasonCode.RANGE_BUY_SIGNAL if setup.side == Side.BUY else ReasonCode.RANGE_SELL_SIGNAL
            return StrategyResult(
                Decision.OPEN,
                reason,
                StrategySignal(
                    StrategyType.RANGE_REVERSION,
                    setup.side,
                    context.specs.symbol,
                    entry,
                    setup.stop_loss,
                    tp,
                    reason,
                    setup.setup_id,
                ),
                setup,
            )

        # ── Phase 2: M15 context → check for new rejection and create ARMED setup ──
        candle_range = last_m15.high - last_m15.low
        mid = (last_m15.high + last_m15.low) / 2.0

        buy_zone_hi = lo + cfg.zone_pct * width
        sell_zone_lo = hi - cfg.zone_pct * width

        # Middle zone — no trade
        if last_m15.close > buy_zone_hi and last_m15.close < sell_zone_lo:
            return StrategyResult(Decision.HOLD, ReasonCode.RANGE_MIDDLE_NO_TRADE)

        expiry = last_m15.time + timedelta(minutes=cfg.expiry_m1_bars)

        if last_m15.close <= buy_zone_hi:
            # Potential BUY: need lower wick rejection and close in upper half of candle
            lw = lower_wick(last_m15)
            lw_ratio = lw / candle_range if candle_range > 0 else 0.0
            if lw_ratio < cfg.wick_pct:
                return StrategyResult(
                    Decision.HOLD,
                    ReasonCode.NO_RANGE_BOUNDARY_REJECTION,
                    diagnostics={"wick_ratio": lw_ratio, "side": "BUY", "wick_pct": cfg.wick_pct},
                )
            if last_m15.close <= mid:
                return StrategyResult(
                    Decision.HOLD,
                    ReasonCode.NO_RANGE_BOUNDARY_REJECTION,
                    diagnostics={"reason": "close_below_mid", "side": "BUY"},
                )
            # Arm setup
            stop = lo - cfg.stop_buffer_atr * a
            tp_level = hard_take_profit_price(
                entry=context.market.ask,
                stop=stop,
                side=Side.BUY,
                rr=cfg.take_profit_rr,
                enabled=context.config.management.hard_take_profit,
            )
            # trigger_price: M15 close (any M1 close above confirms continuation)
            trigger = last_m15.close
            setup = Setup.create(
                context.specs.symbol,
                StrategyType.RANGE_REVERSION,
                Side.BUY,
                SetupState.ARMED,
                last_m15.time,
                trigger,
                stop,
                take_profit=tp_level,
                expires_at_bar=expiry,
                reason=ReasonCode.SETUP_ARMED,
                metadata={"range_high": hi, "range_low": lo, "wick_ratio": lw_ratio},
            )
            context.setups.upsert(setup)
            return StrategyResult(
                Decision.HOLD,
                ReasonCode.SETUP_ARMED,
                setup=setup,
                diagnostics={"wick_ratio": lw_ratio, "side": "BUY", "trigger": trigger},
            )

        # Potential SELL: need upper wick rejection and close in lower half of candle
        uw = upper_wick(last_m15)
        uw_ratio = uw / candle_range if candle_range > 0 else 0.0
        if uw_ratio < cfg.wick_pct:
            return StrategyResult(
                Decision.HOLD,
                ReasonCode.NO_RANGE_BOUNDARY_REJECTION,
                diagnostics={"wick_ratio": uw_ratio, "side": "SELL", "wick_pct": cfg.wick_pct},
            )
        if last_m15.close >= mid:
            return StrategyResult(
                Decision.HOLD,
                ReasonCode.NO_RANGE_BOUNDARY_REJECTION,
                diagnostics={"reason": "close_above_mid", "side": "SELL"},
            )
        stop = hi + cfg.stop_buffer_atr * a
        tp_level = hard_take_profit_price(
            entry=context.market.bid,
            stop=stop,
            side=Side.SELL,
            rr=cfg.take_profit_rr,
            enabled=context.config.management.hard_take_profit,
        )
        trigger = last_m15.close
        setup = Setup.create(
            context.specs.symbol,
            StrategyType.RANGE_REVERSION,
            Side.SELL,
            SetupState.ARMED,
            last_m15.time,
            trigger,
            stop,
            take_profit=tp_level,
            expires_at_bar=expiry,
            reason=ReasonCode.SETUP_ARMED,
            metadata={"range_high": hi, "range_low": lo, "wick_ratio": uw_ratio},
        )
        context.setups.upsert(setup)
        return StrategyResult(
            Decision.HOLD,
            ReasonCode.SETUP_ARMED,
            setup=setup,
            diagnostics={"wick_ratio": uw_ratio, "side": "SELL", "trigger": trigger},
        )
