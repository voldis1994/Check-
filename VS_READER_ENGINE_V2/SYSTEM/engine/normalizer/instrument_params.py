from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from engine.normalizer.market_normalizer import NormalizedMarketBar
from engine.protocol.errors import ValidationError


@dataclass(frozen=True)
class InstrumentParams:
    symbol: str
    digits: int
    point: float
    pip: float


def calculate_pip(point: float, digits: int) -> float:
    if digits in (3, 5):
        return point * 10.0
    return point


def derive_instrument_params(bars: Sequence[NormalizedMarketBar]) -> InstrumentParams:
    if not bars:
        raise ValidationError(
            "market bars are required to derive instrument parameters",
            module="normalizer.instrument_params",
        )

    first_bar = bars[0]
    return InstrumentParams(
        symbol=first_bar.symbol,
        digits=first_bar.digits,
        point=first_bar.point,
        pip=calculate_pip(first_bar.point, first_bar.digits),
    )


def detect_params_change(current: InstrumentParams, incoming: InstrumentParams) -> bool:
    return current.digits != incoming.digits or current.point != incoming.point
