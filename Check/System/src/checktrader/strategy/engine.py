"""Strategy engine facade."""

from __future__ import annotations

from checktrader.config.models import StrategyConfig
from checktrader.domain.market import Candle
from checktrader.domain.money import SymbolSpecs
from checktrader.market_data.aggregator import aggregate_timeframe, validate_candle_sequence
from checktrader.strategy.trend_pullback import StrategyDecision, evaluate_trend_pullback


def run_strategy(
    *,
    symbol: str,
    specs: SymbolSpecs,
    bars_m1: list[Candle],
    config: StrategyConfig,
    now_utc: str,
) -> StrategyDecision:
    validate_candle_sequence(bars_m1)
    m5 = aggregate_timeframe(bars_m1, minutes=5, timeframe="M5")
    m15 = aggregate_timeframe(bars_m1, minutes=15, timeframe="M15")
    return evaluate_trend_pullback(
        symbol=symbol,
        specs=specs,
        m15=m15,
        m5=m5,
        m1=bars_m1,
        config=config,
        now_utc=now_utc,
    )
