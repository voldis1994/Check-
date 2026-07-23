"""File bridge IO — CHECK v5."""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any


def read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def age_s(path: Path) -> float | None:
    if not path.exists():
        return None
    return max(0.0, time.time() - path.stat().st_mtime)


def load_market(bridge: Path) -> dict[str, Any] | None:
    return read_json(bridge / "market" / "latest.json")


def load_status(bridge: Path) -> dict[str, Any] | None:
    return read_json(bridge / "status" / "latest.json")


def write_command(bridge: Path, payload: dict[str, Any]) -> str:
    cmd_id = str(payload.get("id") or uuid.uuid4().hex[:12])
    payload = dict(payload)
    payload["id"] = cmd_id
    folder = bridge / "commands"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"cmd_{cmd_id}.json"
    tmp = folder / f"cmd_{cmd_id}.tmp"
    tmp.write_text(json.dumps(payload, separators=(",", ":")) + "\n", encoding="utf-8")
    tmp.replace(path)
    return cmd_id


def pending_commands(bridge: Path) -> int:
    folder = bridge / "commands"
    if not folder.is_dir():
        return 0
    return len(list(folder.glob("cmd_*.json")))


def latest_ack(bridge: Path, cmd_id: str) -> dict[str, Any] | None:
    return read_json(bridge / "acks" / f"ack_{cmd_id}.json")


def clear_old_acks(bridge: Path, keep: int = 40) -> None:
    folder = bridge / "acks"
    if not folder.is_dir():
        return
    files = sorted(folder.glob("ack_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for path in files[keep:]:
        try:
            path.unlink()
        except OSError:
            pass
