"""Trade copier — master → followers with hard lot size."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app import paths


def _path() -> Path:
    return paths.app_root() / "config" / "copier.json"


DEFAULTS: dict[str, Any] = {
    "enabled": False,
    "master_id": "",
    "copy_sl": True,
    "copy_pending": False,
    "reverse": False,
    "followers": [],  # [{id, enabled, lot}]
}


def load() -> dict[str, Any]:
    paths.ensure_layout()
    p = _path()
    if not p.exists():
        return dict(DEFAULTS)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dict(DEFAULTS)
    out = dict(DEFAULTS)
    if isinstance(data, dict):
        out.update(data)
    out.setdefault("followers", [])
    return out


def save(data: dict[str, Any]) -> None:
    paths.ensure_layout()
    payload = dict(DEFAULTS)
    payload.update(data)
    _path().write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
