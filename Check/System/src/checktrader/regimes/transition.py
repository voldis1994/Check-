from __future__ import annotations
from checktrader.config.models import RegimeTransitionConfig
from checktrader.domain.enums import MarketRegime, ReasonCode
from checktrader.domain.models import IndicatorSnapshot, RegimeSnapshot

def transition_snapshot(indicators: IndicatorSnapshot, config: RegimeTransitionConfig) -> RegimeSnapshot:
    return RegimeSnapshot(MarketRegime.TRANSITION, indicators.time, ReasonCode.REGIME_TRANSITION_CONFIRMED, 1.0/float(config.hold_bars), indicators)
