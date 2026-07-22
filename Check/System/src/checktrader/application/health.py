"""Health checks."""

from __future__ import annotations

from pathlib import Path


def kill_switch_active(root: Path) -> bool:
    return (root / "runtime" / "STOP_TRADING").exists()


def bridge_ready(bridge_root: Path) -> bool:
    return (bridge_root / "market").exists() and (bridge_root / "status").exists()
