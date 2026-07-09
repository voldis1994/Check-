from __future__ import annotations

from typing import Literal, Mapping

from engine.analysis.engine import AnalysisEngineResult
from engine.decision.filters.news_filter import NewsFilterResult
from engine.decision.filters.spread_filter import SpreadFilterResult
from engine.decision.filters.volatility_filter import VolatilityFilterResult
from engine.reason import build_reason
from engine.normalizer.market_normalizer import NormalizedMarketBar
from engine.protocol.constants import REASON_DATA_INVALID, StructureBias, TrendDirection
from engine.state.instance_state import InstanceState

COMPONENT_KEYS = (
    "momentum",
    "trend",
    "structure",
    "pressure",
    "behavior",
    "impact",
    "context",
)

TradeSide = Literal["buy", "sell"]


def round_price(price: float, digits: int) -> float:
    return round(price, digits)


def calculate_weighted_score(
    component_scores: Mapping[str, float],
    weights: Mapping[str, float],
) -> float:
    weight_total = sum(weights[key] for key in COMPONENT_KEYS)
    if weight_total <= 0:
        return 0.0
    return sum(component_scores[key] * weights[key] for key in COMPONENT_KEYS) / weight_total


def build_component_scores(analysis: AnalysisEngineResult, side: TradeSide) -> dict[str, float]:
    if side == "buy":
        momentum_component = (analysis.momentum.momentum_score + 1.0) / 2.0
        if analysis.momentum.trend_direction == TrendDirection.UP.value:
            trend_component = analysis.momentum.trend_strength
        elif analysis.momentum.trend_direction == TrendDirection.DOWN.value:
            trend_component = 1.0 - analysis.momentum.trend_strength
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
        momentum_component = (1.0 - analysis.momentum.momentum_score) / 2.0
        if analysis.momentum.trend_direction == TrendDirection.DOWN.value:
            trend_component = analysis.momentum.trend_strength
        elif analysis.momentum.trend_direction == TrendDirection.UP.value:
            trend_component = 1.0 - analysis.momentum.trend_strength
        else:
            trend_component = 0.5

        if analysis.structure.structure_bias == StructureBias.BEARISH.value:
            structure_component = 1.0
        elif analysis.structure.structure_bias == StructureBias.BULLISH.value:
            structure_component = 0.0
        else:
            structure_component = 0.5

        pressure_component = analysis.pressure.sell_pressure

    return {
        "momentum": momentum_component,
        "trend": trend_component,
        "structure": structure_component,
        "pressure": pressure_component,
        "behavior": analysis.behavior.behavior_score,
        "impact": analysis.impact.impact_score,
        "context": analysis.context.context_quality,
    }


def evaluate_filter_chain(
    *,
    analysis: AnalysisEngineResult,
    spread_filter: SpreadFilterResult,
    volatility_filter: VolatilityFilterResult,
    news_filter: NewsFilterResult,
    market_bars: tuple[NormalizedMarketBar, ...],
    side: TradeSide,
) -> str | None:
    if not analysis.context.spread_filter_passed:
        return spread_filter.reason or build_reason(
            REASON_DATA_INVALID,
            f"spread filter rejected {side} setup",
        )
    if not volatility_filter.volatility_acceptable:
        return volatility_filter.reason or build_reason(
            REASON_DATA_INVALID,
            f"volatility filter rejected {side} setup",
        )
    if not news_filter.news_acceptable:
        return news_filter.reason or build_reason(
            REASON_DATA_INVALID,
            f"news filter rejected {side} setup",
        )
    if not market_bars:
        return build_reason(REASON_DATA_INVALID, f"market bars required for {side} setup")
    return None


def calculate_trade_levels(
    *,
    analysis: AnalysisEngineResult,
    market_bars: tuple[NormalizedMarketBar, ...],
    instance_state: InstanceState,
    stop_loss_buffer: float,
    reward_ratio: float,
    side: TradeSide,
) -> tuple[float, float, float] | str:
    digits = instance_state.instrument_digits
    entry_price = round_price(market_bars[-1].close, digits)

    if side == "buy":
        stop_loss = round_price(analysis.structure.swing_low - stop_loss_buffer, digits)
        if stop_loss >= entry_price:
            return build_reason(
                REASON_DATA_INVALID,
                "buy stop loss must be below entry price",
                entry_price=entry_price,
                stop_loss=stop_loss,
            )
        stop_loss_distance = entry_price - stop_loss
        take_profit = round_price(entry_price + stop_loss_distance * reward_ratio, digits)
        return entry_price, stop_loss, take_profit

    stop_loss = round_price(analysis.structure.swing_high + stop_loss_buffer, digits)
    if stop_loss <= entry_price:
        return build_reason(
            REASON_DATA_INVALID,
            "sell stop loss must be above entry price",
            entry_price=entry_price,
            stop_loss=stop_loss,
        )
    stop_loss_distance = stop_loss - entry_price
    take_profit = round_price(entry_price - stop_loss_distance * reward_ratio, digits)
    return entry_price, stop_loss, take_profit
