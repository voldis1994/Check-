from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from engine.core.instance import Instance
from engine.core.paths import SystemPaths
from engine.loader.market_loader import build_market_file_path, load_market_data
from engine.protocol.errors import DataIOError
from tests.loader.conftest import assert_path_suffix, assert_same_path


FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _prepare_market_file(tmp_path: Path, fixture_name: str) -> tuple[SystemPaths, Instance, Path]:
    paths = SystemPaths(tmp_path)
    instance = Instance(account_id="12345", symbol="EURUSD", magic=100001)
    paths.ensure_account_directories(instance.account_id)
    file_path = build_market_file_path(paths, instance)
    shutil.copyfile(FIXTURES_DIR / fixture_name, file_path)
    return paths, instance, file_path


def test_build_market_file_path() -> None:
    paths = SystemPaths(Path("/tmp/system"))
    instance = Instance(account_id="12345", symbol="EURUSD", magic=100001)
    assert_path_suffix(
        build_market_file_path(paths, instance),
        "data/clients/12345/market_EURUSD_100001.csv",
    )


def test_load_market_data_valid_csv_row_count(tmp_path: Path) -> None:
    paths, instance, file_path = _prepare_market_file(tmp_path, "market_valid.csv")
    data = load_market_data(paths, instance)
    assert_same_path(data.file_path, file_path)
    assert data.row_count == 2
    assert "time_utc,open,high,low,close" in data.raw_text
    assert data.modified_utc.endswith("Z")


def test_load_market_data_missing_file_raises_io_error(tmp_path: Path) -> None:
    paths = SystemPaths(tmp_path)
    instance = Instance(account_id="12345", symbol="EURUSD", magic=100001)
    paths.ensure_account_directories(instance.account_id)
    with pytest.raises(DataIOError, match="No such file|does not exist"):
        load_market_data(paths, instance)


def test_load_market_data_does_not_validate_content(tmp_path: Path) -> None:
    paths, instance, _ = _prepare_market_file(tmp_path, "market_missing.csv")
    data = load_market_data(paths, instance)
    assert data.row_count == 1
    assert "bad_header_1,bad_header_2" in data.raw_text


def test_load_market_data_uses_cache_hash(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths, instance, _ = _prepare_market_file(tmp_path, "market_valid.csv")
    cache: dict[str, object] = {}
    first = load_market_data(paths, instance, cache=cache)

    def fail_read(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("atomic_read_text should not be called for unchanged file")

    monkeypatch.setattr("engine.loader.market_loader.atomic_read_text", fail_read)
    second = load_market_data(paths, instance, cache=cache)
    assert first == second
