"""Keep local system.json trading profile in sync with shipped defaults.

Users should never hand-edit trading gates after a pull. Live/runtime/account_id
and paths are preserved; regimes/strategies/risk/limits/spread/position refresh.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# Sections owned by the repo release profile (always refreshed from example).
SHIPPED_TRADING_KEYS: tuple[str, ...] = (
    "regimes",
    "strategies",
    "risk",
    "limits",
    "spread",
    "position",
    "position_sizing",
)


def example_config_path() -> Path:
    return Path(__file__).resolve().parents[3] / "config" / "system.example.json"


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"config root must be object: {path}")
    return data


def apply_shipped_trading_profile(data: dict[str, Any], *, example: dict[str, Any] | None = None) -> dict[str, Any]:
    """Replace trading-gate sections; keep runtime/paths/account_id."""
    src = example if example is not None else _load_json(example_config_path())
    out = dict(data)
    for key in SHIPPED_TRADING_KEYS:
        if key in src:
            out[key] = src[key]
    # Soft-patch account equity gates without wiping account_id/currency.
    if isinstance(src.get("account"), dict):
        acc = dict(out.get("account") or {})
        if not acc.get("account_id"):
            acc["account_id"] = src["account"].get("account_id", "PAPER")
        if not acc.get("currency"):
            acc["currency"] = src["account"].get("currency", "USD")
        acc["min_equity"] = float(src["account"].get("min_equity", 0.0))
        acc["max_drawdown_percent"] = float(src["account"].get("max_drawdown_percent", 100.0))
        out["account"] = acc
    return out


def sync_system_json(path: Path | str, *, example_path: Path | str | None = None) -> bool:
    """
    Rewrite trading-gate sections on disk from system.example.json.

    Preserves runtime, paths, instrument, account_id, etc.
    Returns True when the file content changed (or was created).
    """
    target = Path(path)
    example = Path(example_path) if example_path is not None else example_config_path()
    if not example.exists():
        return False

    example_data = _load_json(example)
    if target.exists():
        current = _load_json(target)
        merged = apply_shipped_trading_profile(current, example=example_data)
        changed = merged != current
    else:
        merged = dict(example_data)
        changed = True

    if not changed:
        return False

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
    return True
