from __future__ import annotations

import inspect

from engine.analysis.engine import run_analysis_engine
from engine.analysis.momentum import TrendAnalysis
from engine.decision.candidate import build_component_scores, calculate_weighted_score
from engine.decision.buy import build_buy_component_scores, calculate_buy_score
from engine.decision.sell import build_sell_component_scores, calculate_sell_score
from engine.normalizer.market_normalizer import NormalizedMarketBar
from engine.protocol.models import UniverseRecord
from datetime import datetime, timezone


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


def _analysis():
    bars = (
        _bar(0, 1.1000, 1.1020, 1.0990, 1.1015),
        _bar(1, 1.1015, 1.1030, 1.1005, 1.1022),
        _bar(2, 1.1022, 1.1040, 1.1010, 1.1031),
    )
    return run_analysis_engine(_universe(), bars)


def test_buy_and_sell_use_shared_component_score_builder() -> None:
    analysis = _analysis()
    buy_scores = build_component_scores(analysis, "buy")
    sell_scores = build_component_scores(analysis, "sell")

    assert buy_scores == build_buy_component_scores(analysis)
    assert sell_scores == build_sell_component_scores(analysis)
    assert buy_scores.keys() == sell_scores.keys()


def test_buy_and_sell_use_shared_weighted_score_calculation() -> None:
    weights = {
        "momentum": 1.0,
        "trend": 1.0,
        "structure": 1.0,
        "pressure": 1.0,
        "behavior": 1.0,
        "impact": 1.0,
        "context": 1.0,
    }
    scores = build_component_scores(_analysis(), "buy")

    assert calculate_buy_score(scores, weights) == calculate_weighted_score(scores, weights)
    assert calculate_sell_score(scores, weights) == calculate_weighted_score(scores, weights)


def test_candidate_module_is_shared_by_buy_and_sell() -> None:
    buy_source = inspect.getsource(build_buy_component_scores)
    sell_source = inspect.getsource(build_sell_component_scores)

    assert "build_component_scores" in buy_source
    assert "build_component_scores" in sell_source
    assert "evaluate_filter_chain" not in buy_source
    assert "evaluate_filter_chain" not in sell_source
