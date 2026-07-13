from __future__ import annotations
from dataclasses import dataclass
from uuid import uuid4
from engine.analysis.engine import run_analysis_engine, with_analysis_context
from engine.analysis.context import with_spread_filter_passed
from engine.core.paths import SystemPaths
from engine.decision.buy import BuyCandidate, calculate_buy_candidate
from engine.decision.filters.news_filter import evaluate_news_filter
from engine.decision.filters.spread_filter import evaluate_spread_filter
from engine.decision.filters.volatility_filter import calculate_relative_volatility, evaluate_volatility_filter
from engine.decision.scorer import ScoringResult, compare_candidates
from engine.decision.sell import SellCandidate, calculate_sell_candidate
from engine.decision.wait_block import evaluate_block_decision, evaluate_wait_decision
from engine.journal.error_journal import log_error
from engine.analysis.context import AnalysisContext
from engine.normalizer.market_normalizer import NormalizedMarketBar
from engine.protocol.constants import Decision, ErrorType, Side
from engine.protocol.models import UniverseRecord, SystemConfig
from engine.state.instance_state import InstanceState
MODULE_NAME = 'decision.engine'

@dataclass(frozen=True)
class DecisionResult:
    decision_id: str
    decision: str
    reason: str
    preferred_side: str
    buy_candidate: BuyCandidate
    sell_candidate: SellCandidate
    buy_score: float
    sell_score: float
    analysis_context: AnalysisContext

def _build_direction_reason(side: str, scoring: ScoringResult) -> str:
    return f'{side}: preferred side selected after scoring (buy_score={scoring.buy_score}, sell_score={scoring.sell_score})'

def _resolve_final_decision(*, scoring: ScoringResult, block_reason: str | None, buy_candidate: BuyCandidate, sell_candidate: SellCandidate, execution_possible: bool) -> tuple[str, str]:
    block_result = evaluate_block_decision(block_reason=block_reason)
    if block_result.is_block:
        return (Decision.BLOCK.value, block_result.reason or '')
    wait_result = evaluate_wait_decision(buy_candidate=buy_candidate, sell_candidate=sell_candidate, scoring=scoring, execution_possible=execution_possible)
    if wait_result.is_wait:
        return (Decision.WAIT.value, wait_result.reason or '')
    if scoring.preferred_side == Side.BUY.value:
        return (Decision.BUY.value, _build_direction_reason(Side.BUY.value, scoring))
    if scoring.preferred_side == Side.SELL.value:
        return (Decision.SELL.value, _build_direction_reason(Side.SELL.value, scoring))
    return (Decision.WAIT.value, wait_result.reason or 'WAIT: no valid preferred side')

def run_decision_engine(*, universe: UniverseRecord, market_bars: tuple[NormalizedMarketBar, ...], instance_state: InstanceState, relative_spread: float, system_config: SystemConfig, block_reason: str | None=None, execution_possible: bool=True, paths: SystemPaths | None=None) -> DecisionResult:
    try:
        analysis_config = system_config.analysis
        risk_config = system_config.risk
        weights = analysis_config.weights.as_mapping()
        analysis = run_analysis_engine(universe, market_bars)
        relative_volatility = calculate_relative_volatility(market_bars, lookback_bars=analysis_config.lookback_bars)
        spread_filter = evaluate_spread_filter(relative_spread, analysis_config.spread_relative_threshold)
        analysis = with_analysis_context(analysis, with_spread_filter_passed(analysis.context, spread_filter.spread_acceptable))
        volatility_filter = evaluate_volatility_filter(relative_volatility, analysis_config.volatility_relative_threshold)
        news_filter = evaluate_news_filter(universe, block_high_impact_news=analysis_config.block_high_impact_news)
        buy_candidate = calculate_buy_candidate(analysis=analysis, market_bars=market_bars, spread_filter=spread_filter, volatility_filter=volatility_filter, news_filter=news_filter, instance_state=instance_state, weights=weights, stop_loss_buffer=analysis_config.stop_loss_buffer, reward_ratio=risk_config.reward_ratio, structure_lookback_bars=analysis_config.structure_lookback_bars)
        sell_candidate = calculate_sell_candidate(analysis=analysis, market_bars=market_bars, spread_filter=spread_filter, volatility_filter=volatility_filter, news_filter=news_filter, instance_state=instance_state, weights=weights, stop_loss_buffer=analysis_config.stop_loss_buffer, reward_ratio=risk_config.reward_ratio, structure_lookback_bars=analysis_config.structure_lookback_bars)
        scoring = compare_candidates(buy_candidate=buy_candidate, sell_candidate=sell_candidate, context=analysis.context)
        decision, reason = _resolve_final_decision(scoring=scoring, block_reason=block_reason, buy_candidate=buy_candidate, sell_candidate=sell_candidate, execution_possible=execution_possible)
        return DecisionResult(decision_id=str(uuid4()), decision=decision, reason=reason, preferred_side=scoring.preferred_side, buy_candidate=buy_candidate, sell_candidate=sell_candidate, buy_score=scoring.buy_score, sell_score=scoring.sell_score, analysis_context=analysis.context)
    except Exception as exc:
        if paths is not None:
            log_error(paths, instance_state.instance, module=MODULE_NAME, error_type=ErrorType.VALIDATION.value, message='decision engine failed', context={'error': str(exc)})
        raise
