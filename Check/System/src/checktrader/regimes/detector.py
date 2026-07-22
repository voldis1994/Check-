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
    config: SystemConfig; last_m15_time: datetime|None=None; last_snapshot: RegimeSnapshot|None=None
    def update(self, m15: list[Candle]) -> RegimeSnapshot:
        bars=closed_bars(m15)
        if not bars:
            ind=IndicatorSnapshot(datetime.now(UTC)); return RegimeSnapshot(MarketRegime.UNKNOWN, ind.time, ReasonCode.NO_CLOSED_BARS, 0.0, ind)
        if self.last_m15_time==bars[-1].time and self.last_snapshot is not None: return self.last_snapshot
        self.last_m15_time=bars[-1].time
        snap=detect_trend(bars,self.config.regimes.trend,self.config.instrument) or detect_range(bars,self.config.regimes.range)
        if snap is None:
            ind=latest_snapshot(bars, ema_fast_period=self.config.regimes.trend.ema_fast_period, ema_slow_period=self.config.regimes.trend.ema_slow_period, atr_period=self.config.regimes.trend.atr_period, adx_period=self.config.regimes.trend.adx_period)
            snap=transition_snapshot(ind,self.config.regimes.transition)
        self.last_snapshot=snap; return snap
