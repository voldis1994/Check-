from __future__ import annotations
from dataclasses import dataclass
from engine.analysis.context import AnalysisContext
from engine.decision.buy import BuyCandidate
from engine.decision.sell import SellCandidate
from engine.protocol.constants import Side

@dataclass(frozen=True)
class ScoringResult:
    buy_score: float
    sell_score: float
    score_delta: float
    preferred_side: str
    market_quality_score: float = 1.0

def _default_scoring_context() -> AnalysisContext:
    return AnalysisContext(session='', regime='', news_active=False, context_quality=1.0, trade_environment='NEUTRAL', spread_filter_passed=True)

def _resolve_preferred_side_from_scores(*, buy_valid: bool, sell_valid: bool, buy_score: float, sell_score: float) -> str:
    if buy_valid and sell_valid:
        if buy_score > sell_score:
            return Side.BUY.value
        if sell_score > buy_score:
            return Side.SELL.value
        return Side.NONE.value
    if buy_valid:
        return Side.BUY.value
    if sell_valid:
        return Side.SELL.value
    return Side.NONE.value

def compare_candidates(*, buy_candidate: BuyCandidate, sell_candidate: SellCandidate, context: AnalysisContext) -> ScoringResult:
    """Compare directional scores only; market quality is gated separately.

    Shared quality components (behavior/impact/context) must not inflate both
    BUY and SELL equally. Context quality is exposed as ``market_quality_score``
    metadata for the signal-quality layer, not multiplied into scores here.
    """
    from engine.decision.candidate import calculate_market_quality_from_components
    buy_score = buy_candidate.buy_score
    sell_score = sell_candidate.sell_score
    market_quality_score = (
        calculate_market_quality_from_components(buy_candidate.component_scores)
        + calculate_market_quality_from_components(sell_candidate.component_scores)
    ) / 2.0
    # Keep context as a soft ceiling on quality without boosting directional scores.
    market_quality_score = min(market_quality_score, max(0.0, float(context.context_quality)))
    preferred_side = _resolve_preferred_side_from_scores(buy_valid=buy_candidate.valid, sell_valid=sell_candidate.valid, buy_score=buy_score, sell_score=sell_score)
    return ScoringResult(buy_score=buy_score, sell_score=sell_score, score_delta=buy_score - sell_score, preferred_side=preferred_side, market_quality_score=market_quality_score)

def resolve_preferred_side(buy_candidate: BuyCandidate, sell_candidate: SellCandidate, *, context: AnalysisContext | None=None) -> str:
    return compare_candidates(buy_candidate=buy_candidate, sell_candidate=sell_candidate, context=context or _default_scoring_context()).preferred_side
