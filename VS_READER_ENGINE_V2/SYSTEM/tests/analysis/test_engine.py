from __future__ import annotations

from datetime import datetime, timezone

import engine.analysis.engine as analysis_engine_module
from engine.analysis.engine import run_analysis_engine
from engine.normalizer.market_normalizer import NormalizedMarketBar
from engine.protocol.models import UniverseRecord


def _bar(index: int, open_: float, high: float, low: float, close: float) -> NormalizedMarketBar:
    return NormalizedMarketBar(
        time_utc=datetime(2026, 7, 7, 6, index, tzinfo=timezone.utc),
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=100.0,
        symbol="EURUSD",
        timeframe="M1",
        digits=5,
        point=0.00001,
        bar_index=index,
    )


def _universe() -> UniverseRecord:
    return UniverseRecord(
        schema_version="1.0.0",
        timestamp_utc="2026-07-07T06:00:00.000Z",
        session="LONDON",
        market_regime="trending",
        news_window_active=False,
    )


def test_analysis_engine_runs_modules_in_fixed_order(monkeypatch) -> None:
    call_order: list[str] = []
    bars = (_bar(0, 1.1, 1.2, 1.0, 1.15), _bar(1, 1.15, 1.21, 1.1, 1.2))

    original_context = analysis_engine_module.build_analysis_context
    original_structure = analysis_engine_module.analyze_structure
    original_momentum = analysis_engine_module.analyze_momentum_and_trend
    original_pressure = analysis_engine_module.analyze_pressure
    original_behavior = analysis_engine_module.analyze_behavior
    original_impact = analysis_engine_module.analyze_impact

    def wrapped_context(*args, **kwargs):  # type: ignore[no-untyped-def]
        call_order.append("context")
        return original_context(*args, **kwargs)

    def wrapped_structure(*args, **kwargs):  # type: ignore[no-untyped-def]
        call_order.append("structure")
        return original_structure(*args, **kwargs)

    def wrapped_momentum(*args, **kwargs):  # type: ignore[no-untyped-def]
        call_order.append("momentum")
        return original_momentum(*args, **kwargs)

    def wrapped_pressure(*args, **kwargs):  # type: ignore[no-untyped-def]
        call_order.append("pressure")
        return original_pressure(*args, **kwargs)

    def wrapped_behavior(*args, **kwargs):  # type: ignore[no-untyped-def]
        call_order.append("behavior")
        return original_behavior(*args, **kwargs)

    def wrapped_impact(*args, **kwargs):  # type: ignore[no-untyped-def]
        call_order.append("impact")
        return original_impact(*args, **kwargs)

    monkeypatch.setattr(analysis_engine_module, "build_analysis_context", wrapped_context)
    monkeypatch.setattr(analysis_engine_module, "analyze_structure", wrapped_structure)
    monkeypatch.setattr(analysis_engine_module, "analyze_momentum_and_trend", wrapped_momentum)
    monkeypatch.setattr(analysis_engine_module, "analyze_pressure", wrapped_pressure)
    monkeypatch.setattr(analysis_engine_module, "analyze_behavior", wrapped_behavior)
    monkeypatch.setattr(analysis_engine_module, "analyze_impact", wrapped_impact)

    run_analysis_engine(_universe(), bars)

    assert call_order == ["context", "structure", "momentum", "pressure", "behavior", "impact"]


def test_analysis_engine_returns_full_analysis_context() -> None:
    bars = (
        _bar(0, 1.1000, 1.1020, 1.0990, 1.1015),
        _bar(1, 1.1015, 1.1030, 1.1005, 1.1022),
        _bar(2, 1.1022, 1.1040, 1.1010, 1.1031),
    )
    result = run_analysis_engine(_universe(), bars)

    assert result.context.session == "LONDON"
    assert result.structure.swing_high > 0
    assert -1.0 <= result.momentum.momentum_score <= 1.0
    assert 0.0 <= result.pressure.buy_pressure <= 1.0
    assert 0.0 <= result.behavior.behavior_score <= 1.0
    assert 0.0 <= result.impact.setup_quality <= 1.0
    assert result.trend.trend_direction in {"UP", "DOWN", "SIDEWAYS"}


def test_trend_view_reflects_momentum_without_duplicate_storage() -> None:
    bars = (
        _bar(0, 1.1000, 1.1020, 1.0990, 1.1015),
        _bar(1, 1.1015, 1.1030, 1.1005, 1.1022),
        _bar(2, 1.1022, 1.1040, 1.1010, 1.1031),
    )
    result = run_analysis_engine(_universe(), bars)

    assert result.trend.trend_direction == result.momentum.trend_direction
    assert result.trend.trend_strength == result.momentum.trend_strength
    assert result.trend.trend_duration_bars == result.momentum.trend_duration_bars
    assert result.trend.higher_highs == result.momentum.higher_highs
    assert result.trend.lower_lows == result.momentum.lower_lows
    assert "trend" not in result.__dataclass_fields__


def test_analysis_engine_does_not_call_decision_or_risk() -> None:
    source = (analysis_engine_module.__file__ and open(analysis_engine_module.__file__, encoding="utf-8").read()) or ""
    assert "engine.decision" not in source
    assert "engine.risk" not in source
