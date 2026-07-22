from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from checktrader.domain.enums import ReasonCode, SetupState, Side, StrategyType
from checktrader.domain.models import Setup
from checktrader.setups.state_machine import TERMINAL_STATES


@dataclass(slots=True)
class SetupRepository:
    setups: dict[str, Setup] = field(default_factory=dict)

    def upsert(self, setup: Setup) -> Setup:
        self.setups[setup.setup_id] = setup
        return setup

    def get(self, setup_id: str) -> Setup | None:
        return self.setups.get(setup_id)

    def active(
        self, *, symbol: str | None = None, strategy: StrategyType | None = None, side: Side | None = None
    ) -> list[Setup]:
        rows = [s for s in self.setups.values() if s.state not in TERMINAL_STATES]
        if symbol:
            rows = [s for s in rows if s.symbol == symbol]
        if strategy:
            rows = [s for s in rows if s.strategy == strategy]
        if side:
            rows = [s for s in rows if s.side == side]
        return sorted(rows, key=lambda s: s.created_at_bar)

    def to_list(self) -> list[dict[str, Any]]:
        return [s.to_dict() for s in self.setups.values()]

    @classmethod
    def from_list(cls, rows: list[dict[str, Any]]) -> SetupRepository:
        repo = cls()
        for r in rows:
            try:
                repo.upsert(
                    Setup(
                        str(r["setup_id"]),
                        str(r["symbol"]),
                        StrategyType(r["strategy"]),
                        Side(r["side"]),
                        SetupState(r["state"]),
                        datetime.fromisoformat(str(r["created_at_bar"])),
                        datetime.fromisoformat(str(r["expires_at_bar"])) if r.get("expires_at_bar") else None,
                        float(r["trigger_price"]),
                        float(r["stop_loss"]),
                        float(r["take_profit"]) if r.get("take_profit") is not None else None,
                        ReasonCode(r.get("reason", "SETUP_CREATED")),
                        dict(r.get("metadata", {})),
                    )
                )
            except (KeyError, ValueError, TypeError):
                continue
        return repo
