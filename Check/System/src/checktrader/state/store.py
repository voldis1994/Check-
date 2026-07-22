"""Persistent instance state."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from checktrader.domain.enums import ConfirmationSource, PositionState, Side
from checktrader.domain.positions import ManagedPosition
from checktrader.domain.trailing import TrailingState
from checktrader.execution.protocol import atomic_write_json, read_json


@dataclass(slots=True)
class InstanceRuntimeState:
    schema_version: str = "2.0.0"
    revision: int = 0
    saved_at_utc: str = ""
    position: ManagedPosition = field(default_factory=ManagedPosition)
    trailing: TrailingState = field(default_factory=TrailingState)
    known_setup_fingerprints: list[str] = field(default_factory=list)
    sequence: int = 0
    last_reason: str | None = None
    pending_command_id: str | None = None

    def next_sequence(self) -> int:
        self.sequence += 1
        return self.sequence


def _checksum(payload: dict[str, Any]) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def save_instance_state(path: Path, state: InstanceRuntimeState, *, now_utc: str) -> None:
    state.revision += 1
    state.saved_at_utc = now_utc
    position_payload: dict[str, Any] = asdict(state.position)
    trailing_payload: dict[str, Any] = asdict(state.trailing)
    position_payload["state"] = state.position.state.value
    if state.position.side is not None:
        position_payload["side"] = state.position.side.value
    trailing_payload["confirmation_source"] = state.trailing.confirmation_source.value
    payload: dict[str, Any] = {
        "schema_version": state.schema_version,
        "revision": state.revision,
        "saved_at_utc": state.saved_at_utc,
        "sequence": state.sequence,
        "last_reason": state.last_reason,
        "pending_command_id": state.pending_command_id,
        "known_setup_fingerprints": list(state.known_setup_fingerprints),
        "position": position_payload,
        "trailing": trailing_payload,
    }
    payload["checksum"] = _checksum({k: v for k, v in payload.items() if k != "checksum"})
    atomic_write_json(path, payload)


def load_instance_state(path: Path) -> InstanceRuntimeState:
    if not path.exists():
        return InstanceRuntimeState()
    payload = read_json(path)
    expected = payload.get("checksum")
    body = {k: v for k, v in payload.items() if k != "checksum"}
    if expected and expected != _checksum(body):
        # corrupt → fresh FLAT with reconciliation needed
        state = InstanceRuntimeState()
        state.position.state = PositionState.RECONCILING
        state.last_reason = "checksum_mismatch"
        return state
    state = InstanceRuntimeState(
        schema_version=str(payload.get("schema_version", "2.0.0")),
        revision=int(payload.get("revision", 0)),
        saved_at_utc=str(payload.get("saved_at_utc", "")),
        sequence=int(payload.get("sequence", 0)),
        last_reason=payload.get("last_reason"),
        pending_command_id=payload.get("pending_command_id"),
        known_setup_fingerprints=list(payload.get("known_setup_fingerprints", [])),
    )
    pos = payload.get("position", {})
    state.position = ManagedPosition(
        state=PositionState(pos.get("state", "FLAT")),
        ticket=pos.get("ticket"),
        side=None if pos.get("side") is None else Side(pos["side"]),
        volume=pos.get("volume"),
        open_price=pos.get("open_price"),
        stop_loss=pos.get("stop_loss"),
        take_profit=pos.get("take_profit"),
        open_time_utc=pos.get("open_time_utc"),
        setup_id=pos.get("setup_id"),
        setup_fingerprint=pos.get("setup_fingerprint"),
        pending_command_id=pos.get("pending_command_id"),
    )
    tr = payload.get("trailing", {})

    state.trailing = TrailingState(
        broker_stop_loss=tr.get("broker_stop_loss"),
        broker_take_profit=tr.get("broker_take_profit"),
        current_bid=tr.get("current_bid"),
        current_ask=tr.get("current_ask"),
        current_net_profit=float(tr.get("current_net_profit", 0)),
        peak_net_profit=float(tr.get("peak_net_profit", 0)),
        position_ticket=tr.get("position_ticket"),
        status_timestamp=tr.get("status_timestamp"),
        calculated_be_sl=tr.get("calculated_be_sl"),
        calculated_grid_step=int(tr.get("calculated_grid_step", 0)),
        calculated_grid_sl=tr.get("calculated_grid_sl"),
        calculated_high_lock_sl=tr.get("calculated_high_lock_sl"),
        calculated_pressure_sl=tr.get("calculated_pressure_sl"),
        final_proposed_sl=tr.get("final_proposed_sl"),
        pending_command_id=tr.get("pending_command_id"),
        pending_stop_loss=tr.get("pending_stop_loss"),
        pending_step=tr.get("pending_step"),
        pending_created_at=tr.get("pending_created_at"),
        retry_count=int(tr.get("retry_count", 0)),
        be_confirmed=bool(tr.get("be_confirmed", False)),
        confirmed_be_sl=tr.get("confirmed_be_sl"),
        confirmed_grid_step=int(tr.get("confirmed_grid_step", 0)),
        confirmed_stop_loss=tr.get("confirmed_stop_loss"),
        confirmed_locked_net_profit=float(tr.get("confirmed_locked_net_profit", 0)),
        confirmed_at=tr.get("confirmed_at"),
        confirmation_source=ConfirmationSource(tr.get("confirmation_source", "NONE")),
        last_reason=tr.get("last_reason"),
    )
    return state
