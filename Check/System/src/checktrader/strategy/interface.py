"""Strategy interface protocol."""

from __future__ import annotations

from typing import Protocol

from checktrader.config.models import StrategyConfig
from checktrader.domain.market import Candle
from checktrader.domain.money import SymbolSpecs
from checktrader.strategy.trend_pullback import StrategyDecision


class StrategyEngine(Protocol):
    def evaluate(
        self,
        *,
        symbol: str,
        specs: SymbolSpecs,
        bars_m1: list[Candle],
        config: StrategyConfig,
        now_utc: str,
    ) -> StrategyDecision: ...


__all__ = ["StrategyEngine", "StrategyDecision"]
