"""Bridge protocol unit tests — writer puts commands/, reader parses market, dedupe."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from tests.fixtures.market_payloads import MARKET_LATEST_PAYLOAD, STATUS_PAYLOAD

from checktrader.bridge.reader import read_market, read_status
from checktrader.bridge.writer import write_command
from checktrader.domain.enums import OrderAction
from checktrader.domain.models import Command
from checktrader.execution.idempotency import CommandDedupe

# ── Writer ─────────────────────────────────────────────────────────────────────


def test_writer_puts_file_under_commands_dir(tmp_path: Path) -> None:
    bridge_dir = tmp_path / "bridge"
    bridge_dir.mkdir(parents=True)

    cmd = Command(
        command_id="test-001",
        action=OrderAction.OPEN,
        symbol="EURUSD",
        protocol_version="3.0.0",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        payload={"side": "BUY", "lot": 0.01, "entry_price": 1.1000, "stop_loss": 1.0950, "take_profit": 1.1100},
    )
    path = write_command(bridge_dir, cmd)
    assert path.exists()
    # File must be inside bridge_dir/commands/
    assert path.parent == bridge_dir / "commands"
    assert "test-001" in path.name
    data = json.loads(path.read_text())
    assert data["payload"]["command_id"] == "test-001"


def test_writer_command_file_has_correct_action(tmp_path: Path) -> None:
    bridge_dir = tmp_path / "bridge"
    bridge_dir.mkdir(parents=True)

    cmd = Command(
        command_id="close-cmd-001",
        action=OrderAction.CLOSE,
        symbol="EURUSD",
        protocol_version="3.0.0",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        payload={"position_id": "pos-001"},
    )
    path = write_command(bridge_dir, cmd)
    data = json.loads(path.read_text())
    assert data["payload"]["action"] == "CLOSE"


# ── Reader: market ─────────────────────────────────────────────────────────────


def test_reader_parses_bars_m1_from_market_json(tmp_path: Path) -> None:
    """Reader should parse bars_m1 from bridge_dir/market/latest.json fixture."""
    bridge_dir = tmp_path / "bridge"
    market_dir = bridge_dir / "market"
    market_dir.mkdir(parents=True)
    (market_dir / "latest.json").write_text(json.dumps(MARKET_LATEST_PAYLOAD))

    snap = read_market(bridge_dir, "EURUSD")
    assert snap is not None
    assert len(snap.m1) > 0
    # Verify bar fields
    first = snap.m1[0]
    assert first.open > 0
    assert first.high >= first.open
    assert first.low <= first.open
    assert first.close > 0
    assert first.timeframe == "M1"
    assert first.closed is True


def test_reader_parses_m5_and_m15(tmp_path: Path) -> None:
    """Reader returns empty M5/M15 (aggregated from M1 in cycle); no crash."""
    bridge_dir = tmp_path / "bridge"
    market_dir = bridge_dir / "market"
    market_dir.mkdir(parents=True)
    (market_dir / "latest.json").write_text(json.dumps(MARKET_LATEST_PAYLOAD))

    snap = read_market(bridge_dir, "EURUSD")
    assert snap is not None
    # M5/M15 are aggregated from M1 in the cycle, not provided by the reader
    assert isinstance(snap.m5, list)
    assert isinstance(snap.m15, list)


def test_reader_returns_none_for_missing_file(tmp_path: Path) -> None:
    market_dir = tmp_path / "bridge" / "market"
    market_dir.mkdir(parents=True)
    snap = read_market(tmp_path / "bridge", "EURUSD")
    assert snap is None


def test_reader_parses_status(tmp_path: Path) -> None:
    bridge_dir = tmp_path / "bridge"
    status_dir = bridge_dir / "status"
    status_dir.mkdir(parents=True)
    (status_dir / "latest.json").write_text(json.dumps(STATUS_PAYLOAD))

    account = read_status(bridge_dir)
    assert account is not None
    assert account.balance == pytest.approx(10000.0)
    assert account.connected is True
    assert account.trading_allowed is True


# ── Dedupe ─────────────────────────────────────────────────────────────────────


def test_dedupe_remember_first_time_returns_true() -> None:
    store = CommandDedupe(window_seconds=60.0)
    now = datetime(2026, 1, 1, tzinfo=UTC)
    assert store.remember("cmd-001", now) is True


def test_dedupe_remember_twice_same_returns_false() -> None:
    store = CommandDedupe(window_seconds=60.0)
    now = datetime(2026, 1, 1, tzinfo=UTC)
    store.remember("cmd-001", now)
    assert store.remember("cmd-001", now) is False


def test_dedupe_different_ids_both_remembered() -> None:
    store = CommandDedupe(window_seconds=60.0)
    now = datetime(2026, 1, 1, tzinfo=UTC)
    assert store.remember("cmd-001", now) is True
    assert store.remember("cmd-002", now) is True


def test_dedupe_expires_after_window() -> None:
    store = CommandDedupe(window_seconds=10.0)
    t0 = datetime(2026, 1, 1, tzinfo=UTC)
    store.remember("cmd-001", t0)
    # Advance past window
    t1 = t0 + timedelta(seconds=15)
    assert store.remember("cmd-001", t1) is True  # should be re-remembered after expiry
