"""Alerts config — On/Off + hard thresholds."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app import paths


def _path() -> Path:
    return paths.app_root() / "config" / "alerts.json"


DEFAULTS: dict[str, Any] = {
    "equity_drawdown_enabled": False,
    "equity_drawdown": 500.0,
    "daily_profit_target_enabled": False,
    "daily_profit_target": 300.0,
    "trade_opened_enabled": True,
    "trade_closed_enabled": True,
    "email_enabled": False,
    "push_enabled": False,
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
    return out


def save(data: dict[str, Any]) -> None:
    paths.ensure_layout()
    payload = dict(DEFAULTS)
    payload.update(data)
    _path().write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
