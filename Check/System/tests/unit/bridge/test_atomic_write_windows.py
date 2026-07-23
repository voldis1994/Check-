"""Atomic JSON write must not fail when directory fsync is denied (Windows/MT4)."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

from checktrader.bridge.atomic_files import read_json, write_json_atomic


def test_read_json_retries_transient_partial(tmp_path: Path) -> None:
    path = tmp_path / "latest.json"
    path.write_text('{"ok": true}', encoding="utf-8")
    calls = {"n": 0}
    real_read = Path.read_text

    def flaky(self: Path, *args: object, **kwargs: object) -> str:
        calls["n"] += 1
        if calls["n"] < 3:
            raise OSError(32, "sharing violation")
        return real_read(self, *args, **kwargs)

    with patch.object(Path, "read_text", flaky):
        data = read_json(path)
    assert data == {"ok": True}
    assert calls["n"] >= 3

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
