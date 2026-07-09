from __future__ import annotations

from dataclasses import dataclass

from engine.normalizer.market_normalizer import NormalizedMarketBar
from engine.protocol.constants import MomentumDirection, TrendDirection


@dataclass(frozen=True)
class MomentumAnalysis:
    momentum_score: float
    momentum_direction: str
    rate_of_change: float
    acceleration: float
    trend_direction: str
    trend_strength: float
    trend_duration_bars: int
    higher_highs: bool
    lower_lows: bool


@dataclass(frozen=True)
class TrendAnalysis:
    trend_direction: str
    trend_strength: float
    trend_duration_bars: int
    higher_highs: bool
    lower_lows: bool

    @classmethod
    def from_momentum(cls, momentum: MomentumAnalysis) -> TrendAnalysis:
        return cls(
            trend_direction=momentum.trend_direction,
            trend_strength=momentum.trend_strength,
            trend_duration_bars=momentum.trend_duration_bars,
            higher_highs=momentum.higher_highs,
            lower_lows=momentum.lower_lows,
        )


def _clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(max_value, value))


def analyze_momentum_and_trend(
    bars: tuple[NormalizedMarketBar, ...],
) -> MomentumAnalysis:
    if len(bars) < 2:
        return MomentumAnalysis(
            momentum_score=0.0,
            momentum_direction=MomentumDirection.NEUTRAL.value,
            rate_of_change=0.0,
            acceleration=0.0,
            trend_direction=TrendDirection.SIDEWAYS.value,
            trend_strength=0.0,
            trend_duration_bars=len(bars),
            higher_highs=False,
            lower_lows=False,
        )

    first_close = bars[0].close
    last_close = bars[-1].close
    previous_close = bars[-2].close
    if first_close == 0:
        rate_of_change = 0.0
    else:
        rate_of_change = (last_close - first_close) / first_close
    acceleration = last_close - previous_close
    momentum_score = _clamp(rate_of_change * 10.0, -1.0, 1.0)

    if momentum_score > 0:
        momentum_direction = MomentumDirection.UP.value
    elif momentum_score < 0:
        momentum_direction = MomentumDirection.DOWN.value
    else:
        momentum_direction = MomentumDirection.NEUTRAL.value

    highs = [bar.high for bar in bars]
    lows = [bar.low for bar in bars]
    higher_highs = all(curr >= prev for prev, curr in zip(highs, highs[1:]))
    lower_lows = all(curr <= prev for prev, curr in zip(lows, lows[1:]))

    if higher_highs and not lower_lows:
        trend_direction = TrendDirection.UP.value
    elif lower_lows and not higher_highs:
        trend_direction = TrendDirection.DOWN.value
    else:
        trend_direction = TrendDirection.SIDEWAYS.value

    trend_strength = _clamp(abs(rate_of_change) * 10.0, 0.0, 1.0)

    return MomentumAnalysis(
        momentum_score=momentum_score,
        momentum_direction=momentum_direction,
        rate_of_change=rate_of_change,
        acceleration=acceleration,
        trend_direction=trend_direction,
        trend_strength=trend_strength,
        trend_duration_bars=len(bars),
        higher_highs=higher_highs,
        lower_lows=lower_lows,
    )
