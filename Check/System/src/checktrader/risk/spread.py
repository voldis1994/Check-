from __future__ import annotations
from checktrader.config.models import SpreadConfig
from checktrader.domain.enums import ReasonCode
from checktrader.domain.models import SymbolSpecs

def spread_points(bid: float, ask: float, specs: SymbolSpecs) -> float: return max(0.0, ask-bid)/specs.point
def validate_spread(bid: float, ask: float, atr_value: float|None, specs: SymbolSpecs, config: SpreadConfig) -> ReasonCode:
    points=spread_points(bid,ask,specs)
    if points>config.max_points: return ReasonCode.SPREAD_POINTS_TOO_HIGH
    if atr_value is not None:
        atr_points=atr_value/specs.point
        if atr_points>0.0 and points>config.max_atr_fraction*atr_points: return ReasonCode.SPREAD_ATR_TOO_HIGH
    return ReasonCode.RISK_ACCEPTED
