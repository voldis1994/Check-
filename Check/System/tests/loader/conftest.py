from __future__ import annotations
from pathlib import Path

def assert_path_suffix(path: Path, expected_suffix: str) -> None:
    normalized_suffix = expected_suffix.replace('\\', '/')
    assert path.as_posix().endswith(normalized_suffix)

def assert_same_path(left: Path, right: Path) -> None:
    assert left.resolve() == right.resolve()
