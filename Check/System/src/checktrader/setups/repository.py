from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from checktrader.domain.enums import MarketRegime, ReasonCode, SetupState, Side, StrategyType
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
                # Support both old key (trigger_price) and new key (trigger_level)
                trigger = r.get("trigger_level") or r.get("trigger_price")
                if trigger is None:
                    continue

                raw_bar = r.get("created_at_bar")
                created_at_bar = datetime.fromisoformat(str(raw_bar)) if raw_bar else datetime.now()
                raw_utc = r.get("created_at_utc") or raw_bar
                created_at_utc = datetime.fromisoformat(str(raw_utc)) if raw_utc else created_at_bar

                regime_raw = r.get("regime")
                regime = MarketRegime(regime_raw) if regime_raw else None

                indicator_snap = r.get("indicator_snapshot")

                status_history = r.get("status_history", [])
                if not isinstance(status_history, list):
                    status_history = []

                repo.upsert(
                    Setup(
                        str(r["setup_id"]),
                        str(r["symbol"]),
                        StrategyType(r["strategy"]),
                        Side(r["side"]),
                        SetupState(r["state"]),
                        created_at_bar,
                        created_at_utc,
                        float(trigger),
                        float(r["stop_loss"]),
                        str(r.get("account_number", "")),
                        regime,
                        datetime.fromisoformat(str(r["expires_at_bar"])) if r.get("expires_at_bar") else None,
                        float(r["take_profit"]) if r.get("take_profit") is not None else None,
                        float(r["invalidation_level"]) if r.get("invalidation_level") is not None else None,
                        float(r["stop_loss_candidate"]) if r.get("stop_loss_candidate") is not None else None,
                        dict(indicator_snap) if isinstance(indicator_snap, dict) else None,
                        list(status_history),
                        r.get("cancellation_reason") or None,
                        r.get("command_id") or None,
                        r.get("ticket") or None,
                        ReasonCode(r.get("reason", "SETUP_CREATED")),
                        dict(r.get("metadata", {})),
                    )
                )
            except (KeyError, ValueError, TypeError):
                continue
        return repo
