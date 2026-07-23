"""Single app root for source and frozen CHECK.exe."""

from __future__ import annotations

import sys
from pathlib import Path


def app_root() -> Path:
    """Directory that owns config/, clients/, runtime/, mt4/.

    Frozen onedir: next to CHECK.exe (not _internal).
    Source: Check/Platform/.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def ensure_layout(root: Path | None = None) -> Path:
    root = root or app_root()
    (root / "config").mkdir(parents=True, exist_ok=True)
    (root / "clients").mkdir(parents=True, exist_ok=True)
    (root / "runtime").mkdir(parents=True, exist_ok=True)
    return root
