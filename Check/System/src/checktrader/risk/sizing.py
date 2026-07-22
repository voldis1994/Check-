from __future__ import annotations
from checktrader.config.models import PositionSizingConfig
from checktrader.domain.enums import ReasonCode

def fixed_lot(config: PositionSizingConfig) -> tuple[float, ReasonCode]:
    lot=config.fixed_lot
    if lot<config.min_lot or lot>config.max_lot: return lot, ReasonCode.RISK_LOT_INVALID
    steps=round((lot-config.min_lot)/config.lot_step); normalized=config.min_lot+steps*config.lot_step
    return (lot, ReasonCode.RISK_LOT_INVALID) if abs(normalized-lot)>config.lot_step/1000.0 else (lot, ReasonCode.RISK_ACCEPTED)
