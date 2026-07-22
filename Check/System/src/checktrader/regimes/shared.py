"""Shared market-regime detection across multi-account bridges.

Two MT4 accounts on the same symbol must not invent different regimes just because
one terminal attached later or has a shorter warm-up history. Regime is a market
property: compute it once from the richest sequential M15 series for that symbol,
then every account reuses the same snapshot for routing and management.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from checktrader.config.models import SystemConfig
from checktrader.domain.models import Candle, RegimeSnapshot
from checktrader.market_data.bars import closed_bars
from checktrader.market_data.validation import sequential_bars
from checktrader.regimes.detector import RegimeDetector


def _symbol_key(symbol: str) -> str:
    return (symbol or "").strip().upper() or "AUTO"


@dataclass(slots=True)
class SharedRegimeHub:
    config: SystemConfig
    _detectors: dict[str, RegimeDetector] = field(default_factory=dict)
    _best_m15: dict[str, list[Candle]] = field(default_factory=dict)
    _best_m1: dict[str, list[Candle]] = field(default_factory=dict)
    _snapshots: dict[str, RegimeSnapshot] = field(default_factory=dict)

    def consider(self, symbol: str, *, m1: list[Candle], m15: list[Candle], timeframe: str = "M15") -> None:
        key = _symbol_key(symbol)
        closed_m1 = closed_bars(m1)
        if closed_m1:
            prev_m1 = self._best_m1.get(key) or []
            if len(closed_m1) > len(closed_bars(prev_m1)):
                self._best_m1[key] = list(m1)

        ok, _ = sequential_bars(m15, timeframe)
        if not ok:
            return
        closed_m15 = closed_bars(m15)
        if not closed_m15:
            return
        prev = self._best_m15.get(key) or []
        if len(closed_m15) >= len(closed_bars(prev)):
            self._best_m15[key] = list(m15)

    def best_m1(self, symbol: str) -> list[Candle]:
        return list(self._best_m1.get(_symbol_key(symbol)) or [])

    def finalize(self) -> None:
        for key, m15 in self._best_m15.items():
            det = self._detectors.setdefault(key, RegimeDetector(self.config))
            snap = det.update(m15)
            meta = dict(snap.metadata or {})
            meta["regime_source"] = "shared"
            meta["shared_m15"] = len(closed_bars(m15))
            snap.metadata = meta
            self._snapshots[key] = snap

    def get(self, symbol: str) -> RegimeSnapshot | None:
        return self._snapshots.get(_symbol_key(symbol))
