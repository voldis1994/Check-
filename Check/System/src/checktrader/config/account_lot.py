"""Per-account lot size overrides (dashboard → runtime/accounts/<id>/lot.json)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from checktrader.config.models import SystemConfig

LOT_FILENAME = "lot.json"


def account_lot_path(runtime_dir: Path, account_id: str) -> Path:
    return Path(runtime_dir) / "accounts" / str(account_id) / LOT_FILENAME


def read_account_lot(path: Path) -> float | None:
    """Return fixed_lot from lot.json, or None if missing/invalid."""
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    raw = data.get("fixed_lot", data.get("lot"))
    try:
        lot = float(raw)
    except (TypeError, ValueError):
        return None
    if lot <= 0:
        return None
    return lot


def write_account_lot(
    path: Path,
    lot: float,
    *,
    source: str = "dashboard",
    extra: dict[str, Any] | None = None,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "fixed_lot": float(lot),
        "updated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": source,
    }
    if extra:
        payload.update(extra)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def clear_account_lot(path: Path) -> bool:
    if path.exists():
        path.unlink()
        return True
    return False


def apply_account_lot_override(config: SystemConfig, account_id: str | None = None) -> SystemConfig:
    """
    If runtime/accounts/<id>/lot.json exists, patch position + position_sizing lots.

    account_id defaults to config.account.account_id.
    """
    acct = str(account_id or config.account.account_id or "").strip()
    if not acct or acct in {"-", "unknown"}:
        return config
    lot = read_account_lot(account_lot_path(config.paths.runtime_dir, acct))
    if lot is None:
        return config
    if abs(config.position_sizing.fixed_lot - lot) < 1e-12 and abs(config.position.default_lot - lot) < 1e-12:
        return config
    return config.model_copy(
        update={
            "position": config.position.model_copy(update={"default_lot": lot}),
            "position_sizing": config.position_sizing.model_copy(update={"fixed_lot": lot}),
        }
    )
