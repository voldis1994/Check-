"""CHECK Platform v4 — settings store."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = ROOT / "config" / "defaults.json"
SETTINGS = ROOT / "config" / "settings.json"


def _load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def load() -> dict[str, Any]:
    out = _load(DEFAULTS)
    out.update(_load(SETTINGS))
    return out


def save(data: dict[str, Any]) -> Path:
    SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    base = _load(DEFAULTS)
    base.update(data)
    SETTINGS.write_text(json.dumps(base, indent=2) + "\n", encoding="utf-8")
    return SETTINGS
