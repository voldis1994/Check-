"""Strategy evaluation context helpers."""

from __future__ import annotations

from dataclasses import dataclass

from checktrader.domain.market import Candle
from checktrader.domain.money import SymbolSpecs
from checktrader.market_data.aggregator import aggregate_timeframe


@dataclass(frozen=True, slots=True)
class StrategyContext:
    symbol: str
    specs: SymbolSpecs
    m1: list[Candle]
    m5: list[Candle]
    m15: list[Candle]
    now_utc: str


def build_strategy_context(
    *,
    symbol: str,
    specs: SymbolSpecs,
    bars_m1: list[Candle],
    now_utc: str,
) -> StrategyContext:
    return StrategyContext(
        symbol=symbol,
        specs=specs,
        m1=list(bars_m1),
        m5=aggregate_timeframe(bars_m1, minutes=5, timeframe="M5"),
        m15=aggregate_timeframe(bars_m1, minutes=15, timeframe="M15"),
        now_utc=now_utc,
    )


__all__ = ["StrategyContext", "build_strategy_context"]
