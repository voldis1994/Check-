"""Global settings — strategies + portfolio hard caps (no %)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app import paths
from app.risk import GLOBAL_RISK_DEFAULTS

DEFAULTS: dict[str, Any] = dict(GLOBAL_RISK_DEFAULTS)


def _defaults_path() -> Path:
    return paths.app_root() / "config" / "defaults.json"


def _settings_path() -> Path:
    return paths.app_root() / "config" / "settings.json"


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def load() -> dict[str, Any]:
    paths.ensure_layout()
    out = dict(DEFAULTS)
    out.update(_load_json(_defaults_path()))
    out.update(_load_json(_settings_path()))
    for k in list(out):
        if "atr" in k.lower() or "percent" in k.lower() or k.endswith("_pct"):
            out.pop(k, None)
    return out


def save(data: dict[str, Any]) -> Path:
    paths.ensure_layout()
    path = _settings_path()
    payload = dict(DEFAULTS)
    payload.update(_load_json(_defaults_path()))
    payload.update(data)
    for k in list(payload):
        if "atr" in k.lower() or "percent" in k.lower() or k.endswith("_pct"):
            payload.pop(k, None)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path
