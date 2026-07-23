"""CHECK v5 — paths for source and frozen EXE."""

from __future__ import annotations

import sys
from pathlib import Path


def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def ensure_layout(root: Path | None = None) -> Path:
    root = root or app_root()
    for name in ("config", "clients", "runtime", "instances", "template", "mt4"):
        (root / name).mkdir(parents=True, exist_ok=True)
    return root
