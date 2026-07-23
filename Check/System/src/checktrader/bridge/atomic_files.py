from __future__ import annotations

import json
import os
import sys
from contextlib import suppress
from pathlib import Path
from typing import Any
from uuid import uuid4


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    """Atomic JSON write. Directory fsync is Unix-only — Windows denies O_RDONLY on dirs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        with tmp.open("w", encoding="utf-8") as h:
            json.dump(payload, h, separators=(",", ":"), sort_keys=True)
            h.flush()
            os.fsync(h.fileno())
        os.replace(tmp, path)
    except Exception:
        if tmp.exists():
            with suppress(OSError):
                tmp.unlink()
        raise

    # Best-effort dir durability. On Windows AppData/MT4 paths this often raises
    # PermissionError (Errno 13) and previously aborted live OPEN commands.
    if sys.platform == "win32":
        return
    try:
        fd = os.open(path.parent, os.O_RDONLY)
    except OSError:
        return
    try:
        with suppress(OSError):
            os.fsync(fd)
    finally:
        os.close(fd)


def read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else None
