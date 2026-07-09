from __future__ import annotations

from datetime import datetime, timezone

from engine.analysis.context import (
    AnalysisContext,
    build_analysis_context,
    with_spread_filter_passed,
)
from engine.normalizer.market_normalizer import NormalizedMarketBar
from engine.protocol.models import UniverseRecord


def _bar(index: int) -> NormalizedMarketBar:
    return NormalizedMarketBar(
        time_utc=datetime(2026, 7, 7, 6, index, tzinfo=timezone.utc),
        open=1.1,
        high=1.2,
        low=1.0,
        close=1.15,
        volume=100.0,
        symbol="EURUSD",
        timeframe="M1",
        digits=5,
        point=0.00001,
        bar_index=index,
    )


def _universe(regime: str, news_active: bool) -> UniverseRecord:
    return UniverseRecord(
        schema_version="1.0.0",
        timestamp_utc="2026-07-07T06:00:00.000Z",
        session="LONDON",
        market_regime=regime,
        news_window_active=news_active,
    )


def test_context_trade_environment_values() -> None:
    favorable = build_analysis_context(_universe("trending", False), (_bar(0),))
    neutral = build_analysis_context(_universe("ranging", False), (_bar(0),))
    hostile = build_analysis_context(_universe("volatile", False), (_bar(0),))

    assert favorable.trade_environment == "FAVORABLE"
    assert neutral.trade_environment == "NEUTRAL"
    assert hostile.trade_environment == "HOSTILE"


def test_context_news_active_from_universe() -> None:
    context = build_analysis_context(_universe("trending", True), (_bar(0),))
    assert context.news_active
    assert context.trade_environment == "HOSTILE"


def test_context_does_not_generate_trade_signal() -> None:
    context = build_analysis_context(_universe("trending", False), (_bar(0), _bar(1)))
    assert context.session == "LONDON"
    assert context.regime == "trending"
    assert 0.0 <= context.context_quality <= 1.0
    assert context.spread_filter_passed is True
    assert not hasattr(context, "decision")
    assert not hasattr(context, "action")


def test_with_spread_filter_passed_sets_accepted_value() -> None:
    base = build_analysis_context(_universe("trending", False), (_bar(0),))
    accepted = with_spread_filter_passed(base, True)
    rejected = with_spread_filter_passed(base, False)

    assert accepted.spread_filter_passed is True
    assert rejected.spread_filter_passed is False
    assert accepted.session == base.session
    assert rejected.trade_environment == base.trade_environment


def test_analysis_context_round_trip_serialization() -> None:
    context = AnalysisContext(
        session="LONDON",
        regime="trending",
        news_active=False,
        context_quality=0.9,
        trade_environment="FAVORABLE",
        spread_filter_passed=False,
    )

    restored = AnalysisContext.from_dict(context.to_dict())

    assert restored == context
