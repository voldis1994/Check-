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
        Recompute regime only when a new closed M15 bar is available.
        Return UNKNOWN (section 5.5) when there is insufficient history
        for EMA200 (< ema200_period bars).
        """
        bars = closed_bars(m15)
        if not bars:
            ind = IndicatorSnapshot(datetime.now(UTC))
            return RegimeSnapshot(MarketRegime.UNKNOWN, ind.time, ReasonCode.NO_CLOSED_BARS, 0.0, ind)

        # Only recompute when the last closed bar is new
        if self.last_m15_time == bars[-1].time and self.last_snapshot is not None:
            return self.last_snapshot

        self.last_m15_time = bars[-1].time
        trend_cfg = self.config.regimes.trend

        # Section 5.5: insufficient history for EMA200
        if len(bars) < trend_cfg.ema200_period:
            ind = IndicatorSnapshot(bars[-1].time)
            snap = RegimeSnapshot(MarketRegime.UNKNOWN, bars[-1].time, ReasonCode.HISTORY_INSUFFICIENT, 0.0, ind)
            self.last_snapshot = snap
            return snap

        candidate = detect_trend(bars, trend_cfg) or detect_range(bars, self.config.regimes.range)

        if candidate is None:
            # Section 5.4: enough history but neither trend nor range
            ind = latest_snapshot(
                bars,
                ema_fast_period=trend_cfg.ema20_period,
                ema_slow_period=trend_cfg.ema50_period,
                atr_period=trend_cfg.atr_period,
                adx_period=trend_cfg.adx_period,
                ema200_period=trend_cfg.ema200_period,
            )
            snap = transition_snapshot(ind, self.config.regimes.transition)
        else:
            snap = candidate

        self.last_snapshot = snap
        return snap
