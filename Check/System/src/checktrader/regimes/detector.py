from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from checktrader.config.models import SystemConfig
from checktrader.domain.enums import MarketRegime, ReasonCode
from checktrader.domain.models import Candle, IndicatorSnapshot, RegimeSnapshot
from checktrader.market_data.bars import closed_bars
from checktrader.market_data.indicators import latest_snapshot
from checktrader.regimes.range import detect_range
from checktrader.regimes.transition import transition_snapshot
from checktrader.regimes.trend import detect_trend


@dataclass(slots=True)
class RegimeDetector:
    config: SystemConfig
    last_m15_time: datetime | None = None
    last_snapshot: RegimeSnapshot | None = None

    def update(self, m15: list[Candle]) -> RegimeSnapshot:
        """
        Recompute regime when a new closed M15 bar arrives.

        Do NOT freeze the whole system waiting for EMA200 history. Once we have
        enough bars for EMA50/ATR/ADX, detect with ema200 clamped to available
        length so live accounts can open/manage trades while history builds.
        """
        bars = closed_bars(m15)
        if not bars:
            ind = IndicatorSnapshot(datetime.now(UTC))
            return RegimeSnapshot(MarketRegime.UNKNOWN, ind.time, ReasonCode.NO_CLOSED_BARS, 0.0, ind)

        if self.last_m15_time == bars[-1].time and self.last_snapshot is not None:
            return self.last_snapshot

        self.last_m15_time = bars[-1].time
        trend_cfg = self.config.regimes.trend
        min_needed = max(
            trend_cfg.ema50_period + trend_cfg.slope_lookback + 2,
            trend_cfg.adx_period * 2,
            trend_cfg.atr_period + 2,
            trend_cfg.ema20_period + 2,
        )
        if len(bars) < min_needed:
            ind = IndicatorSnapshot(bars[-1].time)
            snap = RegimeSnapshot(
                MarketRegime.UNKNOWN,
                bars[-1].time,
                ReasonCode.HISTORY_INSUFFICIENT,
                0.0,
                ind,
                metadata={"m15": len(bars), "need": min_needed},
            )
            self.last_snapshot = snap
            return snap

        ema200_eff = min(trend_cfg.ema200_period, len(bars))
        trend_eff = trend_cfg.model_copy(update={"ema200_period": ema200_eff})
        warming = len(bars) < trend_cfg.ema200_period

        candidate = detect_trend(bars, trend_eff) or detect_range(bars, self.config.regimes.range)

        if candidate is None:
            ind = latest_snapshot(
                bars,
                ema_fast_period=trend_eff.ema20_period,
                ema_slow_period=trend_eff.ema50_period,
                atr_period=trend_eff.atr_period,
                adx_period=trend_eff.adx_period,
                ema200_period=ema200_eff,
            )
            snap = transition_snapshot(ind, self.config.regimes.transition)
        else:
            snap = candidate

        if warming:
            snap.metadata = {
                **dict(snap.metadata or {}),
                "warming_up": True,
                "m15": len(bars),
                "ema200_target": trend_cfg.ema200_period,
                "ema200_effective": ema200_eff,
            }

        self.last_snapshot = snap
        return snap
