from __future__ import annotations
from dataclasses import dataclass
from engine.decision.reason import build_reason
from engine.protocol.constants import REASON_NEWS_WINDOW_ACTIVE, NewsImpactLevel
from engine.protocol.models import UniverseRecord

NEWS_FILTER_INACTIVE_REASON = 'news_filter_inactive'

@dataclass(frozen=True)
class NewsFilterResult:
    news_acceptable: bool
    news_window_active: bool
    news_impact_level: str | None
    block_high_impact_news: bool
    reason: str | None

def evaluate_news_filter(universe: UniverseRecord, *, block_high_impact_news: bool) -> NewsFilterResult:
    if not block_high_impact_news:
        return NewsFilterResult(news_acceptable=True, news_window_active=universe.news_window_active, news_impact_level=universe.news_impact_level, block_high_impact_news=block_high_impact_news, reason=NEWS_FILTER_INACTIVE_REASON)
    if universe.metadata is not None and universe.metadata.get('news_data_available') is False:
        return NewsFilterResult(news_acceptable=True, news_window_active=universe.news_window_active, news_impact_level=universe.news_impact_level, block_high_impact_news=block_high_impact_news, reason=NEWS_FILTER_INACTIVE_REASON)
    high_impact_news_window = universe.news_window_active and universe.news_impact_level == NewsImpactLevel.HIGH.value
    news_acceptable = not (block_high_impact_news and high_impact_news_window)
    reason: str | None = None
    if not news_acceptable:
        reason = build_reason(REASON_NEWS_WINDOW_ACTIVE, 'high impact news window active', news_window_active=universe.news_window_active, news_impact_level=universe.news_impact_level)
    return NewsFilterResult(news_acceptable=news_acceptable, news_window_active=universe.news_window_active, news_impact_level=universe.news_impact_level, block_high_impact_news=block_high_impact_news, reason=reason)
