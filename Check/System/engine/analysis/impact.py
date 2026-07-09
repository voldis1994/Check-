from __future__ import annotations
from dataclasses import dataclass
from engine.analysis.behavior import BehaviorAnalysis
from engine.analysis.context import AnalysisContext
from engine.analysis.momentum import MomentumAnalysis
from engine.analysis.pressure import PressureAnalysis
from engine.analysis.structure import StructureAnalysis

@dataclass(frozen=True)
class ImpactAnalysis:
    setup_quality: float
    impact_label: str
    impact_score: float

def _clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(max_value, value))

def analyze_impact(*, context: AnalysisContext, structure: StructureAnalysis, momentum: MomentumAnalysis, pressure: PressureAnalysis, behavior: BehaviorAnalysis) -> ImpactAnalysis:
    direction_alignment = 0.0
    if structure.structure_bias == 'BULLISH' and momentum.trend_direction == 'UP':
        direction_alignment = 1.0
    elif structure.structure_bias == 'BEARISH' and momentum.trend_direction == 'DOWN':
        direction_alignment = 1.0
    elif structure.structure_bias == 'NEUTRAL' or momentum.trend_direction == 'SIDEWAYS':
        direction_alignment = 0.5
    pressure_balance = 1.0 - min(1.0, abs(pressure.pressure_delta))
    momentum_component = (momentum.momentum_score + 1.0) / 2.0
    behavior_component = behavior.behavior_score
    context_component = context.context_quality
    structure_component = direction_alignment
    setup_quality = _clamp(0.25 * context_component + 0.2 * structure_component + 0.2 * momentum_component + 0.2 * behavior_component + 0.15 * pressure_balance, 0.0, 1.0)
    impact_score = _clamp(setup_quality, 0.0, 1.0)
    if impact_score >= 0.75:
        impact_label = 'HIGH'
    elif impact_score >= 0.45:
        impact_label = 'MEDIUM'
    else:
        impact_label = 'LOW'
    return ImpactAnalysis(setup_quality=setup_quality, impact_label=impact_label, impact_score=impact_score)
