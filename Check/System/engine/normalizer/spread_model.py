from __future__ import annotations
import statistics
from dataclasses import dataclass
from typing import Sequence
from engine.protocol.errors import ValidationError
from engine.protocol.models import SensorReading

@dataclass(frozen=True)
class SpreadModelSnapshot:
    history: tuple[float, ...]
    mean_spread: float
    std_spread: float
    median_spread: float
    current_spread: float
    relative_spread: float

    @property
    def sample_count(self) -> int:
        return len(self.history)

def update_spread_model(history: Sequence[float], *, current_spread: float, lookback_bars: int) -> SpreadModelSnapshot:
    if lookback_bars <= 0:
        raise ValidationError('lookback_bars must be positive', module='normalizer.spread_model', context={'lookback_bars': lookback_bars})
    if current_spread < 0:
        raise ValidationError('current_spread must be non-negative', module='normalizer.spread_model', context={'current_spread': current_spread})
    combined = [float(value) for value in history]
    combined.append(float(current_spread))
    trimmed_history = tuple(combined[-lookback_bars:])
    mean_spread = statistics.fmean(trimmed_history)
    median_spread = statistics.median(trimmed_history)
    std_spread = statistics.pstdev(trimmed_history) if len(trimmed_history) > 1 else 0.0
    if std_spread > 0:
        relative_spread = (float(current_spread) - mean_spread) / std_spread
    elif len(trimmed_history) < 2:
        relative_spread = 1.0
    else:
        relative_spread = 0.0
    return SpreadModelSnapshot(history=trimmed_history, mean_spread=mean_spread, std_spread=std_spread, median_spread=median_spread, current_spread=float(current_spread), relative_spread=relative_spread)

def update_spread_model_from_sensor(history: Sequence[float], sensor: SensorReading, *, lookback_bars: int) -> SpreadModelSnapshot:
    return update_spread_model(history, current_spread=sensor.spread, lookback_bars=lookback_bars)
