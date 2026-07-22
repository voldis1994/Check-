"""Keep local system.json trading profile in sync with shipped defaults.

Users should never hand-edit regimes/strategies after a pull. Live/runtime
settings (mode, trading_enabled, paths, account, instrument) are preserved.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# Sections owned by the repo release profile (always refreshed from example).
SHIPPED_TRADING_KEYS: tuple[str, ...] = ("regimes", "strategies")


def example_config_path() -> Path:
    return Path(__file__).resolve().parents[3] / "config" / "system.example.json"


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"config root must be object: {path}")
    return data


def apply_shipped_trading_profile(data: dict[str, Any], *, example: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return a copy of data with regimes/strategies replaced by shipped example."""
    src = example if example is not None else _load_json(example_config_path())
    out = dict(data)
    for key in SHIPPED_TRADING_KEYS:
        if key in src:
            out[key] = src[key]
    return out


def sync_system_json(path: Path | str, *, example_path: Path | str | None = None) -> bool:
    """
    Rewrite regimes/strategies on disk from system.example.json.

    Preserves runtime, account, paths, instrument, risk, management, execution, etc.
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
        changed = any(current.get(k) != merged.get(k) for k in SHIPPED_TRADING_KEYS)
    else:
        merged = dict(example_data)
        changed = True

    if not changed:
        return False

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
    return True
