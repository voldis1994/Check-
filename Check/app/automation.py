"""Automations — hard $ / count triggers + On/Off."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app import paths


def _path() -> Path:
    return paths.app_root() / "config" / "automation.json"


DEFAULTS: dict[str, Any] = {
    "close_all_profit_enabled": False,
    "close_all_profit": 500.0,
    "close_all_loss_enabled": False,
    "close_all_loss": 300.0,
    "reduce_lot_after_loss_enabled": False,
    "reduce_lot_to": 0.01,
    "news_filter_enabled": False,
    "trading_hours_enabled": False,
    # hard hours 0-23, Mon=0 .. Sun=6
    "hours": {
        "0": {"on": True, "start": 0, "end": 23},
        "1": {"on": True, "start": 0, "end": 23},
        "2": {"on": True, "start": 0, "end": 23},
        "3": {"on": True, "start": 0, "end": 23},
        "4": {"on": True, "start": 0, "end": 23},
        "5": {"on": False, "start": 0, "end": 23},
        "6": {"on": False, "start": 0, "end": 23},
    },
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
        if isinstance(data.get("hours"), dict):
            hours = dict(DEFAULTS["hours"])
            hours.update(data["hours"])
            out["hours"] = hours
    return out


def save(data: dict[str, Any]) -> None:
    paths.ensure_layout()
    payload = dict(DEFAULTS)
    payload.update(data)
    _path().write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def within_trading_hours(cfg: dict[str, Any], weekday: int, hour: int) -> bool:
    if not cfg.get("trading_hours_enabled"):
        return True
    day = (cfg.get("hours") or {}).get(str(weekday)) or {}
    if not day.get("on", True):
        return False
    start = int(day.get("start", 0))
    end = int(day.get("end", 23))
    if start <= end:
        return start <= hour <= end
    return hour >= start or hour <= end
