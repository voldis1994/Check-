from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from engine.core.instance import Instance
from engine.core.paths import SystemPaths
from engine.loader.sensor_loader import build_sensor_file_path, load_sensor_data
from engine.protocol.errors import DataIOError
from tests.loader.conftest import assert_path_suffix, assert_same_path


FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _prepare_sensor_file(tmp_path: Path, fixture_name: str) -> tuple[SystemPaths, Instance, Path]:
    paths = SystemPaths(tmp_path)
    instance = Instance(account_id="12345", symbol="EURUSD", magic=100001)
    paths.ensure_account_directories(instance.account_id)
    file_path = build_sensor_file_path(paths, instance)
    shutil.copyfile(FIXTURES_DIR / fixture_name, file_path)
    return paths, instance, file_path


def test_build_sensor_file_path() -> None:
    paths = SystemPaths(Path("/tmp/system"))
    instance = Instance(account_id="12345", symbol="EURUSD", magic=100001)
    assert_path_suffix(
        build_sensor_file_path(paths, instance),
        "data/clients/12345/sensor_EURUSD_100001.csv",
    )


def test_load_sensor_data_valid_csv_loads_history_and_last_row(tmp_path: Path) -> None:
    paths, instance, file_path = _prepare_sensor_file(tmp_path, "sensor_valid.csv")
    data = load_sensor_data(paths, instance)
    assert_same_path(data.file_path, file_path)
    assert data.row_count == 3
    assert data.last_row == "2026-07-07T06:02:00.000Z,1.08510,1.08530,0.00020,20,EURUSD,5,0.00001"
    assert len(data.history_rows) == 3
    assert data.modified_utc.endswith("Z")


def test_load_sensor_data_missing_file_raises_error(tmp_path: Path) -> None:
    paths = SystemPaths(tmp_path)
    instance = Instance(account_id="12345", symbol="EURUSD", magic=100001)
    paths.ensure_account_directories(instance.account_id)
    with pytest.raises(DataIOError, match="No such file|does not exist"):
        load_sensor_data(paths, instance)


def test_load_sensor_data_does_not_validate_spread_consistency(tmp_path: Path) -> None:
    paths, instance, _ = _prepare_sensor_file(tmp_path, "sensor_unvalidated.csv")
    data = load_sensor_data(paths, instance)
    assert data.row_count == 1
    assert data.last_row == "this,is,not,validated"


def test_load_sensor_data_uses_cache_for_unchanged_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths, instance, _ = _prepare_sensor_file(tmp_path, "sensor_valid.csv")
    cache: dict[str, object] = {}
    first = load_sensor_data(paths, instance, cache=cache)

    def fail_read(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("atomic_read_text should not be called for unchanged file")

    monkeypatch.setattr("engine.loader.sensor_loader.atomic_read_text", fail_read)
    second = load_sensor_data(paths, instance, cache=cache)
    assert first == second
