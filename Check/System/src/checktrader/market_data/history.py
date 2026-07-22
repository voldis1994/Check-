from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from checktrader.domain.models import Candle
from checktrader.market_data.bars import sort_unique


@dataclass(slots=True)
class RollingHistory:
    max_bars: dict[str, int]
    candles: dict[str, list[Candle]] = field(default_factory=lambda: {"M1": [], "M5": [], "M15": []})

    def clear(self) -> None:
        self.candles = {tf: [] for tf in ("M1", "M5", "M15")}

    def merge(self, timeframe: str, incoming: list[Candle]) -> list[Candle]:
        merged = sort_unique([*self.candles.get(timeframe, []), *incoming])
        limit = self.max_bars.get(timeframe)
        self.candles[timeframe] = merged[-limit:] if limit else merged
        return self.candles[timeframe]

    def get(self, timeframe: str) -> list[Candle]:
        return list(self.candles.get(timeframe, []))

    def to_dict(self) -> dict[str, Any]:
        return {tf: [b.to_dict() for b in bars] for tf, bars in self.candles.items()}

    @classmethod
    def from_dict(cls, data: dict[str, Any], max_bars: dict[str, int]) -> RollingHistory:
        h = cls(max_bars)
        for tf, rows in data.items():
            if isinstance(rows, list):
                h.candles[tf] = sort_unique([Candle.from_dict(r, tf) for r in rows if isinstance(r, dict)])
        return h


def load_history(path: Path, max_bars: dict[str, int]) -> RollingHistory:
    if not path.exists():
        return RollingHistory(max_bars)
    data = json.loads(path.read_text(encoding="utf-8"))
    return RollingHistory.from_dict(data if isinstance(data, dict) else {}, max_bars)


def save_history(path: Path, history: RollingHistory) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(history.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)
