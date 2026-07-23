"""CHECK Platform v4 — settings store (EXE-owned)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from app import paths

DEFAULTS_NAME = "defaults.json"
SETTINGS_NAME = "settings.json"

DEFAULTS: dict[str, Any] = {
    "lot": 0.02,
    "sl_atr": 1.0,
    "be_start_atr": 0.75,
    "be_offset_atr": 0.05,
    "trail_start_atr": 0.50,
    "trail_lock_atr": 0.75,
    "symbol": "AUTO",
    "magic": 40001,
    "cycle_sec": 3.0,
    "trend": True,
    "breakout": True,
    "force_idle": False,
    "mt4_exe": "",
    "metaeditor_exe": "",
    "max_bars": 300,
}


def _defaults_path() -> Path:
    return paths.app_root() / "config" / DEFAULTS_NAME


def _settings_path() -> Path:
    return paths.app_root() / "config" / SETTINGS_NAME


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def seed_defaults() -> None:
    paths.ensure_layout()
    dst = _defaults_path()
    if dst.exists():
        return
    # Prefer shipped defaults next to package / bundled data
    candidates = [
        paths.app_root() / "config" / DEFAULTS_NAME,
        Path(__file__).resolve().parents[1] / "config" / DEFAULTS_NAME,
    ]
    for src in candidates:
        if src.exists() and src != dst:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            return
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(DEFAULTS, indent=2) + "\n", encoding="utf-8")


def load() -> dict[str, Any]:
    paths.ensure_layout()
    seed_defaults()
    out = dict(DEFAULTS)
    out.update(_load_json(_defaults_path()))
    out.update(_load_json(_settings_path()))
    return out


def save(data: dict[str, Any]) -> Path:
    paths.ensure_layout()
    seed_defaults()
    path = _settings_path()
    payload = dict(DEFAULTS)
    payload.update(_load_json(_defaults_path()))
    payload.update(data)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path
