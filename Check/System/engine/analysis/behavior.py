from __future__ import annotations
from dataclasses import dataclass
from engine.normalizer.market_normalizer import NormalizedMarketBar

@dataclass(frozen=True)
class BehaviorAnalysis:
    dominant_pattern: str
    indecision_detected: bool
    rejection_detected: bool
    behavior_score: float

def _clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(max_value, value))

def analyze_behavior(bars: tuple[NormalizedMarketBar, ...]) -> BehaviorAnalysis:
    if not bars:
        return BehaviorAnalysis(dominant_pattern='NONE', indecision_detected=False, rejection_detected=False, behavior_score=0.5)
    bullish_bodies = 0
    bearish_bodies = 0
    indecision_count = 0
    rejection_count = 0
    for bar in bars:
        bar_range = bar.high - bar.low
        if bar_range <= 0:
            indecision_count += 1
            continue
        body = bar.close - bar.open
        body_abs = abs(body)
        upper_wick = bar.high - max(bar.open, bar.close)
        lower_wick = min(bar.open, bar.close) - bar.low
        if body > 0:
            bullish_bodies += 1
        elif body < 0:
            bearish_bodies += 1
        if body_abs <= 0.15 * bar_range:
            indecision_count += 1
        if max(upper_wick, lower_wick) >= 0.6 * bar_range and body_abs <= 0.35 * bar_range:
            rejection_count += 1
    if bullish_bodies > bearish_bodies:
        dominant_pattern = 'BULLISH_BODY'
    elif bearish_bodies > bullish_bodies:
        dominant_pattern = 'BEARISH_BODY'
    else:
        dominant_pattern = 'MIXED'
    indecision_detected = indecision_count > 0
    rejection_detected = rejection_count > 0
    directional_edge = abs(bullish_bodies - bearish_bodies) / max(1, len(bars))
    noise_penalty = indecision_count / max(1, len(bars))
    behavior_score = _clamp(0.5 + 0.5 * directional_edge - 0.3 * noise_penalty, 0.0, 1.0)
    return BehaviorAnalysis(dominant_pattern=dominant_pattern, indecision_detected=indecision_detected, rejection_detected=rejection_detected, behavior_score=behavior_score)
