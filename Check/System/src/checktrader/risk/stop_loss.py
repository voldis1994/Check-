"""Stop-loss validation helpers."""

from __future__ import annotations

from checktrader.domain.enums import Side
from checktrader.domain.money import SymbolSpecs


def stop_loss_distance_pips(*, entry: float, stop_loss: float, specs: SymbolSpecs) -> float:
    if specs.pip_size <= 0:
        return 0.0
    return abs(entry - stop_loss) / specs.pip_size


def stop_loss_side_ok(*, side: Side, entry: float, stop_loss: float) -> bool:
    if side is Side.BUY:
        return stop_loss < entry
    return stop_loss > entry


def stop_loss_within_max(*, entry: float, stop_loss: float, specs: SymbolSpecs, maximum_stop_loss_pips: float) -> bool:
    distance = stop_loss_distance_pips(entry=entry, stop_loss=stop_loss, specs=specs)
    return 0.0 < distance <= maximum_stop_loss_pips


__all__ = ["stop_loss_distance_pips", "stop_loss_side_ok", "stop_loss_within_max"]
