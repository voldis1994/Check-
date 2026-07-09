from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from engine.core.paths import SystemPaths
from engine.loader.universe_loader import build_universe_file_path, load_universe_data
from engine.protocol.errors import DataIOError
from tests.loader.conftest import assert_path_suffix, assert_same_path


FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_build_universe_file_path_account_variant() -> None:
    paths = SystemPaths(Path("/tmp/system"))
    file_path = build_universe_file_path(paths, "12345", use_global_universe=False)
    assert_path_suffix(file_path, "data/clients/12345/universe.json")


def test_build_universe_file_path_global_variant() -> None:
    paths = SystemPaths(Path("/tmp/system"))
    file_path = build_universe_file_path(paths, "12345", use_global_universe=True)
    assert_path_suffix(file_path, "data/universe/universe.json")


def test_load_universe_data_account_variant_loads(tmp_path: Path) -> None:
    paths = SystemPaths(tmp_path)
    paths.ensure_account_directories("12345")
    file_path = build_universe_file_path(paths, "12345", use_global_universe=False)
    shutil.copyfile(FIXTURES_DIR / "universe_valid.json", file_path)

    data = load_universe_data(paths, "12345", use_global_universe=False)
    assert_same_path(data.file_path, file_path)
    assert data.modified_utc.endswith("Z")
    assert '"session": "LONDON"' in data.raw_text
    assert len(data.content_hash) == 64


def test_load_universe_data_global_variant_loads(tmp_path: Path) -> None:
    paths = SystemPaths(tmp_path)
    paths.ensure_directories()
    file_path = build_universe_file_path(paths, "12345", use_global_universe=True)
    shutil.copyfile(FIXTURES_DIR / "universe_valid.json", file_path)

    data = load_universe_data(paths, "12345", use_global_universe=True)
    assert_same_path(data.file_path, file_path)
    assert '"market_regime": "trending"' in data.raw_text


def test_load_universe_data_missing_file_raises(tmp_path: Path) -> None:
    paths = SystemPaths(tmp_path)
    paths.ensure_account_directories("12345")
    with pytest.raises(DataIOError, match="No such file|does not exist"):
        load_universe_data(paths, "12345", use_global_universe=False)


def test_load_universe_data_does_not_interpret_trade_signal_content(tmp_path: Path) -> None:
    paths = SystemPaths(tmp_path)
    paths.ensure_account_directories("12345")
    file_path = build_universe_file_path(paths, "12345", use_global_universe=False)
    file_path.write_text('{"buy":true,"signal":"BUY"}', encoding="utf-8")
    data = load_universe_data(paths, "12345", use_global_universe=False)
    assert data.raw_text == '{"buy":true,"signal":"BUY"}'


def test_load_universe_data_uses_cache_for_unchanged_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = SystemPaths(tmp_path)
    paths.ensure_account_directories("12345")
    file_path = build_universe_file_path(paths, "12345", use_global_universe=False)
    shutil.copyfile(FIXTURES_DIR / "universe_valid.json", file_path)
    cache: dict[str, object] = {}
    first = load_universe_data(paths, "12345", use_global_universe=False, cache=cache)

    def fail_read(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("atomic_read_text should not be called for unchanged file")

    monkeypatch.setattr("engine.loader.universe_loader.atomic_read_text", fail_read)
    second = load_universe_data(paths, "12345", use_global_universe=False, cache=cache)
    assert first == second
