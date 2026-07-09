from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from engine.analysis.engine import AnalysisEngineResult
from engine.decision.candidate import (
    build_component_scores,
    calculate_trade_levels,
    calculate_weighted_score,
    evaluate_filter_chain,
)
from engine.decision.filters.news_filter import NewsFilterResult
from engine.decision.filters.spread_filter import SpreadFilterResult
from engine.decision.filters.volatility_filter import VolatilityFilterResult
from engine.normalizer.market_normalizer import NormalizedMarketBar
from engine.state.instance_state import InstanceState


@dataclass(frozen=True)
class SellCandidate:
    valid: bool
    invalid_reason: str | None
    entry_price: float
    stop_loss: float
    take_profit: float
    component_scores: dict[str, float]
    sell_score: float


def build_sell_component_scores(analysis: AnalysisEngineResult) -> dict[str, float]:
    return build_component_scores(analysis, "sell")


def calculate_sell_score(
    component_scores: Mapping[str, float],
    weights: Mapping[str, float],
) -> float:
    return calculate_weighted_score(component_scores, weights)


def _invalid_candidate(
    *,
    invalid_reason: str,
    component_scores: dict[str, float],
    sell_score: float,
) -> SellCandidate:
    return SellCandidate(
        valid=False,
        invalid_reason=invalid_reason,
        entry_price=0.0,
        stop_loss=0.0,
        take_profit=0.0,
        component_scores=component_scores,
        sell_score=sell_score,
    )


def calculate_sell_candidate(
    *,
    analysis: AnalysisEngineResult,
    market_bars: tuple[NormalizedMarketBar, ...],
    spread_filter: SpreadFilterResult,
    volatility_filter: VolatilityFilterResult,
    news_filter: NewsFilterResult,
    instance_state: InstanceState,
    weights: Mapping[str, float],
    stop_loss_buffer: float,
    reward_ratio: float,
) -> SellCandidate:
    component_scores = build_sell_component_scores(analysis)
    sell_score = calculate_sell_score(component_scores, weights)

    invalid_reason = evaluate_filter_chain(
        analysis=analysis,
        spread_filter=spread_filter,
        volatility_filter=volatility_filter,
        news_filter=news_filter,
        market_bars=market_bars,
        side="sell",
    )
    if invalid_reason is not None:
        return _invalid_candidate(
            invalid_reason=invalid_reason,
            component_scores=component_scores,
            sell_score=sell_score,
        )

    levels = calculate_trade_levels(
        analysis=analysis,
        market_bars=market_bars,
        instance_state=instance_state,
        stop_loss_buffer=stop_loss_buffer,
        reward_ratio=reward_ratio,
        side="sell",
    )
    if isinstance(levels, str):
        return _invalid_candidate(
            invalid_reason=levels,
            component_scores=component_scores,
            sell_score=sell_score,
        )

    entry_price, stop_loss, take_profit = levels
    return SellCandidate(
        valid=True,
        invalid_reason=None,
        entry_price=entry_price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        component_scores=component_scores,
        sell_score=sell_score,
    )
