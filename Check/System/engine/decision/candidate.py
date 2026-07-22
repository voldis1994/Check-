from __future__ import annotations
from typing import Literal, Mapping
from engine.analysis.engine import AnalysisEngineResult
from engine.analysis.momentum import analyze_momentum_and_trend
from engine.decision.filters.news_filter import NewsFilterResult
from engine.decision.filters.range_filter import evaluate_counter_momentum_filter, evaluate_ranging_entry_filter
from engine.decision.filters.spread_filter import SpreadFilterResult
from engine.decision.filters.volatility_filter import VolatilityFilterResult
from engine.reason import build_reason
from engine.normalizer.market_normalizer import NormalizedMarketBar
from engine.protocol.constants import MarketRegime, REASON_DATA_INVALID, StructureBias, TrendDirection
from engine.state.instance_state import InstanceState
COMPONENT_KEYS = ('momentum', 'trend', 'structure', 'pressure', 'behavior', 'impact', 'context')
TradeSide = Literal['buy', 'sell']

def round_price(price: float, digits: int) -> float:
    return round(price, digits)

def calculate_weighted_score(component_scores: Mapping[str, float], weights: Mapping[str, float]) -> float:
    weight_total = sum((weights[key] for key in COMPONENT_KEYS))
    if weight_total <= 0:
        return 0.0
    return sum((component_scores[key] * weights[key] for key in COMPONENT_KEYS)) / weight_total

def build_component_scores(analysis: AnalysisEngineResult, side: TradeSide, *, market_bars: tuple[NormalizedMarketBar, ...] | None=None, ranging_recent_momentum_bars: int=0) -> dict[str, float]:
    momentum = analysis.momentum
    if ranging_recent_momentum_bars > 0 and analysis.context.regime == MarketRegime.RANGING.value and market_bars:
        recent_window = market_bars[-ranging_recent_momentum_bars:] if len(market_bars) > ranging_recent_momentum_bars else market_bars
        if len(recent_window) >= 2:
            momentum = analyze_momentum_and_trend(recent_window)
    if side == 'buy':
        momentum_component = (momentum.momentum_score + 1.0) / 2.0
        if momentum.trend_direction == TrendDirection.UP.value:
            trend_component = momentum.trend_strength
        elif momentum.trend_direction == TrendDirection.DOWN.value:
            trend_component = 1.0 - momentum.trend_strength
        else:
            trend_component = 0.5
        if analysis.structure.structure_bias == StructureBias.BULLISH.value:
            structure_component = 1.0
        elif analysis.structure.structure_bias == StructureBias.BEARISH.value:
            structure_component = 0.0
        else:
            structure_component = 0.5
        pressure_component = analysis.pressure.buy_pressure
    else:
        momentum_component = (1.0 - momentum.momentum_score) / 2.0
        if momentum.trend_direction == TrendDirection.DOWN.value:
            trend_component = momentum.trend_strength
        elif momentum.trend_direction == TrendDirection.UP.value:
            trend_component = 1.0 - momentum.trend_strength
        else:
            trend_component = 0.5
        if analysis.structure.structure_bias == StructureBias.BEARISH.value:
            structure_component = 1.0
        elif analysis.structure.structure_bias == StructureBias.BULLISH.value:
            structure_component = 0.0
        else:
            structure_component = 0.5
        pressure_component = analysis.pressure.sell_pressure
    return {'momentum': momentum_component, 'trend': trend_component, 'structure': structure_component, 'pressure': pressure_component, 'behavior': analysis.behavior.behavior_score, 'impact': analysis.impact.impact_score, 'context': analysis.context.context_quality}

def evaluate_filter_chain(*, analysis: AnalysisEngineResult, spread_filter: SpreadFilterResult, volatility_filter: VolatilityFilterResult, news_filter: NewsFilterResult, market_bars: tuple[NormalizedMarketBar, ...], side: TradeSide, structure_lookback_bars: int, block_ranging_chase_entries: bool, ranging_extreme_threshold: float, ranging_recent_momentum_bars: int) -> str | None:
    if not analysis.context.spread_filter_passed:
        return spread_filter.reason or build_reason(REASON_DATA_INVALID, f'spread filter rejected {side} setup')
    if not volatility_filter.volatility_acceptable:
        return volatility_filter.reason or build_reason(REASON_DATA_INVALID, f'volatility filter rejected {side} setup')
    if not news_filter.news_acceptable:
        return news_filter.reason or build_reason(REASON_DATA_INVALID, f'news filter rejected {side} setup')
    if not market_bars:
        return build_reason(REASON_DATA_INVALID, f'market bars required for {side} setup')
    counter_reason = evaluate_counter_momentum_filter(market_bars=market_bars, side=side, recent_bars=ranging_recent_momentum_bars)
    if counter_reason is not None:
        return counter_reason
    ranging_reason = evaluate_ranging_entry_filter(regime=analysis.context.regime, market_bars=market_bars, side=side, structure_lookback_bars=structure_lookback_bars, block_ranging_chase_entries=block_ranging_chase_entries, ranging_extreme_threshold=ranging_extreme_threshold, ranging_recent_momentum_bars=ranging_recent_momentum_bars)
    if ranging_reason is not None:
        return ranging_reason
    return None

def calculate_trade_levels(*, analysis: AnalysisEngineResult, market_bars: tuple[NormalizedMarketBar, ...], instance_state: InstanceState, stop_loss_buffer: float, reward_ratio: float, side: TradeSide, structure_lookback_bars: int) -> tuple[float, float, float] | str:
    from engine.analysis.structure import analyze_structure_window
    digits = instance_state.instrument_digits
    entry_price = round_price(market_bars[-1].close, digits)
    structure = analyze_structure_window(market_bars, structure_lookback_bars=structure_lookback_bars)
    if side == 'buy':
        stop_loss = round_price(structure.swing_low - stop_loss_buffer, digits)
        if stop_loss >= entry_price:
            return build_reason(REASON_DATA_INVALID, 'buy stop loss must be below entry price', entry_price=entry_price, stop_loss=stop_loss)
        stop_loss_distance = entry_price - stop_loss
        take_profit = round_price(entry_price + stop_loss_distance * reward_ratio, digits)
        return (entry_price, stop_loss, take_profit)
    stop_loss = round_price(structure.swing_high + stop_loss_buffer, digits)
    if stop_loss <= entry_price:
        return build_reason(REASON_DATA_INVALID, 'sell stop loss must be above entry price', entry_price=entry_price, stop_loss=stop_loss)
    stop_loss_distance = stop_loss - entry_price
    take_profit = round_price(entry_price - stop_loss_distance * reward_ratio, digits)
    return (entry_price, stop_loss, take_profit)
