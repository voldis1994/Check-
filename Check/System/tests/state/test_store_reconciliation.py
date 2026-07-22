"""State store + reconciliation tests."""

from __future__ import annotations

from pathlib import Path

from checktrader.domain.enums import PositionState, Side
from checktrader.domain.positions import ManagedPosition
from checktrader.execution.reconciliation import is_ack_timeout, reconcile_position_from_broker
from checktrader.observability.reason_codes import ReasonCode
from checktrader.state.store import InstanceRuntimeState, load_instance_state, save_instance_state
from tests.fixtures.helpers import broker_position


def test_save_load_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "instance.json"
    state = InstanceRuntimeState()
    state.position = ManagedPosition(state=PositionState.OPEN_PENDING, side=Side.BUY, volume=0.01)
    state.pending_command_id = "cmd-open-1"
    state.known_setup_fingerprints.append("fp1")
    save_instance_state(path, state, now_utc="2026-03-01T12:00:00Z")
    loaded = load_instance_state(path)
    assert loaded.position.state is PositionState.OPEN_PENDING
    assert loaded.pending_command_id == "cmd-open-1"
    assert loaded.known_setup_fingerprints == ["fp1"]


def test_checksum_mismatch_forces_reconciling(tmp_path: Path) -> None:
    path = tmp_path / "instance.json"
    state = InstanceRuntimeState()
    save_instance_state(path, state, now_utc="2026-03-01T12:00:00Z")
    text = path.read_text(encoding="utf-8").replace('"revision": 1', '"revision": 99')
    path.write_text(text, encoding="utf-8")
    loaded = load_instance_state(path)
    assert loaded.position.state is PositionState.RECONCILING


def test_pending_open_survives_restart(tmp_path: Path) -> None:
    path = tmp_path / "instance.json"
    state = InstanceRuntimeState()
    state.position.state = PositionState.OPEN_PENDING
    state.pending_command_id = "pending-open"
    save_instance_state(path, state, now_utc="2026-03-01T12:00:00Z")
    again = load_instance_state(path)
    assert again.position.state is PositionState.OPEN_PENDING
    assert again.pending_command_id == "pending-open"


def test_broker_already_closed_reconciling() -> None:
    managed = ManagedPosition(state=PositionState.OPEN, ticket=10, side=Side.BUY)
    managed, reason = reconcile_position_from_broker(managed, None)
    assert managed.state is PositionState.RECONCILING
    assert reason is ReasonCode.RECONCILIATION_REQUIRED


def test_open_pending_missing_broker_keeps_pending() -> None:
    managed = ManagedPosition(state=PositionState.OPEN_PENDING)
    managed, reason = reconcile_position_from_broker(managed, None)
    assert reason is ReasonCode.COMMAND_ALREADY_PENDING
    assert managed.state is PositionState.OPEN_PENDING


def test_broker_present_confirms_open() -> None:
    managed = ManagedPosition(state=PositionState.RECONCILING)
    pos = broker_position(ticket=55)
    managed, reason = reconcile_position_from_broker(managed, pos)
    assert reason is ReasonCode.RECONCILIATION_CONFIRMED
    assert managed.state is PositionState.OPEN
    assert managed.ticket == 55


def test_ack_timeout_helper() -> None:
    assert is_ack_timeout(
        pending_created_at="2026-03-01T12:00:00Z",
        now_utc="2026-03-01T12:00:06Z",
        ack_timeout_ms=5000,
    )
    assert not is_ack_timeout(
        pending_created_at="2026-03-01T12:00:00Z",
        now_utc="2026-03-01T12:00:04Z",
        ack_timeout_ms=5000,
    )
