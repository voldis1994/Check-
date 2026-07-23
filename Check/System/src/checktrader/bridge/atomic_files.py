from __future__ import annotations

import json
import os
import sys
import time
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
    """Read JSON with brief retries — MT4 may be replacing the file (sharing/partial)."""
    if not path.exists():
        return None
    last_exc: Exception | None = None
    for attempt in range(5):
        try:
            text = path.read_text(encoding="utf-8")
            if not text.strip():
                return None
            data = json.loads(text)
            return data if isinstance(data, dict) else None
        except (OSError, json.JSONDecodeError, UnicodeError) as exc:
            last_exc = exc
            time.sleep(0.02 * (attempt + 1))
    if last_exc is not None:
        return None
    return None
