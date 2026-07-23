"""Atomic JSON write must not fail when directory fsync is denied (Windows/MT4)."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

from checktrader.bridge.atomic_files import read_json, write_json_atomic


def test_atomic_write_succeeds_when_dir_fsync_denied(tmp_path: Path) -> None:
    path = tmp_path / "commands" / "command_x.json"
    real_open = os.open

    def _open(path_like: object, flags: int, *args: object, **kwargs: object) -> int:
        # Simulate Windows PermissionError on directory open used for fsync.
        if Path(path_like).is_dir():  # type: ignore[arg-type]
            raise PermissionError(13, "Permission denied", str(path_like))
        return real_open(path_like, flags, *args, **kwargs)  # type: ignore[arg-type]

    with patch("checktrader.bridge.atomic_files.sys.platform", "win32"):
        write_json_atomic(path, {"action": "OPEN", "lot": 0.02})
    # Also exercise non-win32 path with denied dir open.
    with (
        patch("checktrader.bridge.atomic_files.sys.platform", "linux"),
        patch("checktrader.bridge.atomic_files.os.open", side_effect=_open),
    ):
        write_json_atomic(path, {"action": "OPEN", "lot": 0.02, "n": 2})

    data = read_json(path)
    assert data is not None
    assert data["lot"] == 0.02
    assert data["n"] == 2
