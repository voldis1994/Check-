"""Execution idempotency and reconciliation."""

from __future__ import annotations

from datetime import UTC, datetime

from checktrader.domain.enums import ReasonCode, Side, StrategyType
from checktrader.domain.models import Position
from checktrader.execution.idempotency import CommandDedupe
from checktrader.execution.reconciliation import reconcile


def test_duplicate_command_id_rejected() -> None:
    dedupe = CommandDedupe(30.0)
    now = datetime(2026, 1, 1, tzinfo=UTC)
    assert dedupe.remember("cmd-1", now)
    assert not dedupe.remember("cmd-1", now)


def test_broker_positions_win() -> None:
    local = [
        Position(
            "local",
            "TEST",
            Side.BUY,
            0.01,
            100.0,
            99.0,
            None,
            datetime(2026, 1, 1, tzinfo=UTC),
            StrategyType.TREND_CONTINUATION,
        )
    ]
    broker = [
        Position(
            "broker",
            "TEST",
            Side.SELL,
            0.01,
            101.0,
            102.0,
            None,
            datetime(2026, 1, 1, tzinfo=UTC),
            StrategyType.BREAKOUT,
        )
    ]
    result = reconcile(local, broker)
    assert result.positions[0].position_id == "broker"
    assert result.reason is ReasonCode.RECONCILED_WITH_BROKER


def test_empty_broker_clears_local_ghosts() -> None:
    """Flat MT4 (`positions: []`) must wipe stale state.json ghosts — not keep them via `[] or local`."""
    from checktrader.execution.reconciliation import broker_positions_or_empty

    local = [
        Position(
            "ghost",
            "EURUSD",
            Side.BUY,
            0.02,
            1.1,
            1.09,
            None,
            datetime(2026, 1, 1, tzinfo=UTC),
            StrategyType.BREAKOUT,
        )
    ]
    assert broker_positions_or_empty([]) == []
    result = reconcile(local, broker_positions_or_empty([]))
    assert result.positions == []
    assert result.closed_position_ids == ["ghost"]
