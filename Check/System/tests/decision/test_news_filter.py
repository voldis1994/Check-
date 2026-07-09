from __future__ import annotations
import inspect
from engine.decision.filters.news_filter import evaluate_news_filter
from engine.protocol.models import UniverseRecord

def _universe(*, news_window_active: bool, news_impact_level: str | None=None) -> UniverseRecord:
    return UniverseRecord(schema_version='1.0.0', timestamp_utc='2026-07-07T06:00:00.000Z', session='LONDON', market_regime='trending', news_window_active=news_window_active, news_impact_level=news_impact_level)

def test_high_impact_news_window_makes_direction_invalid_when_blocking_enabled() -> None:
    result = evaluate_news_filter(_universe(news_window_active=True, news_impact_level='high'), block_high_impact_news=True)
    assert not result.news_acceptable

def test_news_window_active_with_low_impact_remains_acceptable() -> None:
    result = evaluate_news_filter(_universe(news_window_active=True, news_impact_level='low'), block_high_impact_news=True)
    assert result.news_acceptable
    assert result.reason is None

def test_high_impact_news_window_remains_acceptable_when_blocking_disabled() -> None:
    result = evaluate_news_filter(_universe(news_window_active=True, news_impact_level='high'), block_high_impact_news=False)
    assert result.news_acceptable
    assert result.reason is None

def test_news_window_active_reason_is_generated() -> None:
    result = evaluate_news_filter(_universe(news_window_active=True, news_impact_level='high'), block_high_impact_news=True)
    assert result.reason is not None
    assert 'NEWS_WINDOW_ACTIVE' in result.reason

def test_news_filter_only_evaluates_validity_and_does_not_trade() -> None:
    source = inspect.getsource(evaluate_news_filter)
    assert 'trade' not in source.lower()
    assert 'order' not in source.lower()
    assert 'buy' not in source.lower()
    assert 'sell' not in source.lower()
