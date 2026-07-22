from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol
from checktrader.config.models import SystemConfig
from checktrader.domain.models import AccountStatus, Candle, MarketSnapshot, Position, RegimeSnapshot, StrategyResult, SymbolSpecs
from checktrader.setups.repository import SetupRepository
@dataclass(slots=True)
class StrategyContext:
    config: SystemConfig; specs: SymbolSpecs; market: MarketSnapshot; regime: RegimeSnapshot; account: AccountStatus|None; positions: list[Position]; setups: SetupRepository
    @property
    def m15(self) -> list[Candle]: return self.market.m15
    @property
    def m5(self) -> list[Candle]: return self.market.m5
    @property
    def m1(self) -> list[Candle]: return self.market.m1
class Strategy(Protocol):
    def evaluate(self, context: StrategyContext) -> StrategyResult: ...
