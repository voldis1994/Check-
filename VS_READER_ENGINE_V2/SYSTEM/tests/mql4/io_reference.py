from __future__ import annotations

import os
from pathlib import Path


def tmp_path_for(path: str | Path) -> Path:
    target = Path(path)
    return target.with_name(f"{target.name}.tmp")


def parent_directory(path: str) -> str:
    normalized = path.rstrip("\\")
    separator = normalized.rfind("\\")
    if separator <= 0:
        return ""
    return normalized[:separator]


def atomic_write_text(path: Path, content: str, *, encoding: str = "utf-8") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = tmp_path_for(path)
    with tmp_path.open("w", encoding=encoding) as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp_path, path)
