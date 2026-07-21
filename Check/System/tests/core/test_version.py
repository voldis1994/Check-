from __future__ import annotations
from pathlib import Path
from engine.core.version import FALLBACK_SYSTEM_VERSION, read_system_version


def test_read_system_version_from_repo_root() -> None:
    read_system_version.cache_clear()
    version = read_system_version()
    assert version == '1.1.4'


def test_read_system_version_missing_file_falls_back(tmp_path: Path) -> None:
    read_system_version.cache_clear()
    try:
        assert read_system_version(tmp_path) == FALLBACK_SYSTEM_VERSION
    finally:
        read_system_version.cache_clear()
