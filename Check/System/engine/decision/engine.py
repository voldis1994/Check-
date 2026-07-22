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
from engine.decision.signal_quality import SignalQualityResult, evaluate_signal_quality
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
    signal_quality: SignalQualityResult | None = None

def _build_direction_reason(side: str, scoring: ScoringResult, quality: SignalQualityResult) -> str:
    return (
        f'{side}: preferred side passed signal quality '
        f'(buy_score={scoring.buy_score}, sell_score={scoring.sell_score}, '
        f'score_delta={quality.score_delta}, market_quality={quality.market_quality_score}, '
        f'confirmations={quality.confirmation_count})'
    )

def _structure_level_for_side(*, side: str, buy_candidate: BuyCandidate, sell_candidate: SellCandidate) -> float:
    if side == Side.BUY.value and buy_candidate.valid:
        return float(buy_candidate.entry_price)
    if side == Side.SELL.value and sell_candidate.valid:
        return float(sell_candidate.entry_price)
    if buy_candidate.valid:
        return float(buy_candidate.entry_price)
    if sell_candidate.valid:
        return float(sell_candidate.entry_price)
    return 0.0

def _resolve_final_decision(*, scoring: ScoringResult, block_reason: str | None, buy_candidate: BuyCandidate, sell_candidate: SellCandidate, execution_possible: bool, signal_quality: SignalQualityResult) -> tuple[str, str]:
    block_result = evaluate_block_decision(block_reason=block_reason)
    if block_result.is_block:
        return (Decision.BLOCK.value, block_result.reason or '')
    wait_result = evaluate_wait_decision(buy_candidate=buy_candidate, sell_candidate=sell_candidate, scoring=scoring, execution_possible=execution_possible)
    if wait_result.is_wait:
        return (Decision.WAIT.value, wait_result.reason or '')
    if not signal_quality.passed:
        return (Decision.WAIT.value, signal_quality.human_readable_reason)
    if signal_quality.decision == Side.BUY.value:
        return (Decision.BUY.value, _build_direction_reason(Side.BUY.value, scoring, signal_quality))
    if signal_quality.decision == Side.SELL.value:
        return (Decision.SELL.value, _build_direction_reason(Side.SELL.value, scoring, signal_quality))
    return (Decision.WAIT.value, signal_quality.human_readable_reason or 'WAIT: no valid preferred side')

def run_decision_engine(*, universe: UniverseRecord, market_bars: tuple[NormalizedMarketBar, ...], instance_state: InstanceState, relative_spread: float, system_config: SystemConfig, block_reason: str | None=None, execution_possible: bool=True, paths: SystemPaths | None=None, stop_loss_buffer: float | None=None) -> DecisionResult:
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
        effective_stop_loss_buffer = analysis_config.stop_loss_buffer if stop_loss_buffer is None else stop_loss_buffer
        buy_candidate = calculate_buy_candidate(analysis=analysis, market_bars=market_bars, spread_filter=spread_filter, volatility_filter=volatility_filter, news_filter=news_filter, instance_state=instance_state, weights=weights, stop_loss_buffer=effective_stop_loss_buffer, reward_ratio=risk_config.reward_ratio, structure_lookback_bars=analysis_config.structure_lookback_bars, block_ranging_chase_entries=analysis_config.block_ranging_chase_entries, ranging_extreme_threshold=analysis_config.ranging_extreme_threshold, ranging_recent_momentum_bars=analysis_config.ranging_recent_momentum_bars)
        sell_candidate = calculate_sell_candidate(analysis=analysis, market_bars=market_bars, spread_filter=spread_filter, volatility_filter=volatility_filter, news_filter=news_filter, instance_state=instance_state, weights=weights, stop_loss_buffer=effective_stop_loss_buffer, reward_ratio=risk_config.reward_ratio, structure_lookback_bars=analysis_config.structure_lookback_bars, block_ranging_chase_entries=analysis_config.block_ranging_chase_entries, ranging_extreme_threshold=analysis_config.ranging_extreme_threshold, ranging_recent_momentum_bars=analysis_config.ranging_recent_momentum_bars)
        scoring = compare_candidates(buy_candidate=buy_candidate, sell_candidate=sell_candidate, context=analysis.context)
        candle_time_utc = str(market_bars[-1].time_utc) if market_bars else ''
        provisional_side = scoring.preferred_side if scoring.preferred_side in {Side.BUY.value, Side.SELL.value} else (Side.BUY.value if scoring.buy_score >= scoring.sell_score else Side.SELL.value)
        structure_level = _structure_level_for_side(side=provisional_side, buy_candidate=buy_candidate, sell_candidate=sell_candidate)
        instance_state.expire_signal_fingerprints(current_bar_utc=candle_time_utc)
        cooldown_remaining = instance_state.cooldown_bars_remaining(current_bar_utc=candle_time_utc)
        signal_quality = evaluate_signal_quality(
            buy_score=scoring.buy_score,
            sell_score=scoring.sell_score,
            buy_valid=buy_candidate.valid,
            sell_valid=sell_candidate.valid,
            buy_components=buy_candidate.component_scores,
            sell_components=sell_candidate.component_scores,
            market_quality_score=scoring.market_quality_score,
            signal_quality_config=system_config.signal_quality,
            symbol=instance_state.instance.symbol,
            candle_time_utc=candle_time_utc,
            structure_level=structure_level,
            cooldown_bars_remaining=cooldown_remaining,
            last_trade_result=instance_state.last_trade_result,
            last_trade_close_time_utc=instance_state.last_trade_close_time_utc,
            last_trade_close_bar_utc=instance_state.last_trade_close_bar_utc,
            active_fingerprints=instance_state.active_signal_fingerprints,
        )
        decision, reason = _resolve_final_decision(scoring=scoring, block_reason=block_reason, buy_candidate=buy_candidate, sell_candidate=sell_candidate, execution_possible=execution_possible, signal_quality=signal_quality)
        preferred_side = signal_quality.winning_side if signal_quality.passed else scoring.preferred_side
        return DecisionResult(decision_id=str(uuid4()), decision=decision, reason=reason, preferred_side=preferred_side, buy_candidate=buy_candidate, sell_candidate=sell_candidate, buy_score=scoring.buy_score, sell_score=scoring.sell_score, analysis_context=analysis.context, signal_quality=signal_quality)
    except Exception as exc:
        if paths is not None:
            log_error(paths, instance_state.instance, module=MODULE_NAME, error_type=ErrorType.VALIDATION.value, message='decision engine failed', context={'error': str(exc)})
        raise
