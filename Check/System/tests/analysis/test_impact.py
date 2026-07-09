from __future__ import annotations
from datetime import datetime, timezone
from engine.analysis.behavior import analyze_behavior
from engine.analysis.context import build_analysis_context
from engine.analysis.impact import analyze_impact
from engine.analysis.momentum import analyze_momentum_and_trend
from engine.analysis.pressure import analyze_pressure
from engine.analysis.structure import analyze_structure
from engine.normalizer.market_normalizer import NormalizedMarketBar
from engine.protocol.models import UniverseRecord

def _bar(index: int, open_: float, high: float, low: float, close: float) -> NormalizedMarketBar:
    return NormalizedMarketBar(time_utc=datetime(2026, 7, 7, 6, index, tzinfo=timezone.utc), open=open_, high=high, low=low, close=close, volume=100.0, symbol='EURUSD', timeframe='M1', digits=5, point=1e-05, bar_index=index)

def _universe() -> UniverseRecord:
    return UniverseRecord(schema_version='1.0.0', timestamp_utc='2026-07-07T06:00:00.000Z', session='LONDON', market_regime='trending', news_window_active=False)

def test_impact_contains_quality_assessment() -> None:
    bars = (_bar(0, 1.1, 1.102, 1.099, 1.1015), _bar(1, 1.1015, 1.103, 1.1005, 1.1022), _bar(2, 1.1022, 1.104, 1.101, 1.1031))
    impact = analyze_impact(context=build_analysis_context(_universe(), bars), structure=analyze_structure(bars), momentum=analyze_momentum_and_trend(bars), pressure=analyze_pressure(bars), behavior=analyze_behavior(bars))
    assert 0.0 <= impact.setup_quality <= 1.0
    assert 0.0 <= impact.impact_score <= 1.0
    assert impact.impact_label in {'LOW', 'MEDIUM', 'HIGH'}

def test_impact_does_not_generate_trade() -> None:
    bars = (_bar(0, 1.1, 1.101, 1.099, 1.1005), _bar(1, 1.1005, 1.102, 1.1, 1.101))
    impact = analyze_impact(context=build_analysis_context(_universe(), bars), structure=analyze_structure(bars), momentum=analyze_momentum_and_trend(bars), pressure=analyze_pressure(bars), behavior=analyze_behavior(bars))
    assert not hasattr(impact, 'decision')
    assert not hasattr(impact, 'action')
