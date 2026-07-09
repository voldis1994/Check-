from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Sequence

from engine.decision.reason import build_reason
from engine.normalizer.market_normalizer import NormalizedMarketBar
from engine.protocol.constants import REASON_VOLATILITY_ABNORMAL
from engine.protocol.errors import ValidationError


@dataclass(frozen=True)
class VolatilityFilterResult:
    volatility_acceptable: bool
    relative_volatility: float
    threshold: float
    reason: str | None


def _bar_true_range(bar: NormalizedMarketBar, previous_close: float | None) -> float:
    bar_range = bar.high - bar.low
    if previous_close is None:
        return bar_range
    return max(bar_range, abs(bar.high - previous_close), abs(bar.low - previous_close))


def calculate_relative_volatility(
    bars: Sequence[NormalizedMarketBar],
    *,
    lookback_bars: int,
) -> float:
    if lookback_bars <= 0:
        raise ValidationError(
            "lookback_bars must be positive",
            module="decision.filters.volatility_filter",
            context={"lookback_bars": lookback_bars},
        )
    if not bars:
        return 0.0

    materialized = tuple(bars)
    window = materialized[-lookback_bars:]
    true_ranges: list[float] = []
    window_start = len(materialized) - len(window)
    for offset, bar in enumerate(window):
        bar_index = window_start + offset
        previous_close = materialized[bar_index - 1].close if bar_index > 0 else None
        true_ranges.append(_bar_true_range(bar, previous_close))

    current_atr = true_ranges[-1]
    mean_atr = statistics.fmean(true_ranges)
    if mean_atr <= 0:
        return 0.0 if current_atr <= 0 else float("inf")
    return current_atr / mean_atr


def evaluate_volatility_filter(
    relative_volatility: float,
    threshold: float,
) -> VolatilityFilterResult:
    volatility_acceptable = relative_volatility <= threshold
    reason: str | None = None
    if not volatility_acceptable:
        reason = build_reason(
            REASON_VOLATILITY_ABNORMAL,
            "relative volatility above threshold",
            relative_volatility=relative_volatility,
            threshold=threshold,
        )
    return VolatilityFilterResult(
        volatility_acceptable=volatility_acceptable,
        relative_volatility=relative_volatility,
        threshold=threshold,
        reason=reason,
    )
