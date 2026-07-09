from __future__ import annotations
import shutil
from pathlib import Path
import pytest
from engine.core.paths import SystemPaths
from engine.loader.status_loader import build_status_file_path, load_status_data
from engine.protocol.errors import DataIOError
from tests.loader.conftest import assert_path_suffix, assert_same_path
FIXTURES_DIR = Path(__file__).parent / 'fixtures'

def _prepare_status_file(tmp_path: Path, account_id: str='12345') -> tuple[SystemPaths, Path]:
    paths = SystemPaths(tmp_path)
    paths.ensure_account_directories(account_id)
    file_path = build_status_file_path(paths, account_id)
    shutil.copyfile(FIXTURES_DIR / 'status_valid.json', file_path)
    return (paths, file_path)

def test_build_status_file_path() -> None:
    paths = SystemPaths(Path('/tmp/system'))
    path = build_status_file_path(paths, '12345')
    assert_path_suffix(path, 'data/clients/12345/status_12345.json')

def test_load_status_data_valid_json_loads(tmp_path: Path) -> None:
    paths, file_path = _prepare_status_file(tmp_path)
    data = load_status_data(paths, '12345')
    assert_same_path(data.file_path, file_path)
    assert data.modified_utc.endswith('Z')
    assert '"account_id": "12345"' in data.raw_text
    assert len(data.content_hash) == 64

def test_load_status_data_missing_file_raises_error(tmp_path: Path) -> None:
    paths = SystemPaths(tmp_path)
    paths.ensure_account_directories('12345')
    with pytest.raises(DataIOError, match='No such file|does not exist'):
        load_status_data(paths, '12345')

def test_load_status_data_uses_cache_for_unchanged_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths, _ = _prepare_status_file(tmp_path)
    cache: dict[str, object] = {}
    first = load_status_data(paths, '12345', cache=cache)

    def fail_read(*_args, **_kwargs):
        raise AssertionError('atomic_read_text should not be called for unchanged file')
    monkeypatch.setattr('engine.loader.status_loader.atomic_read_text', fail_read)
    second = load_status_data(paths, '12345', cache=cache)
    assert first == second
