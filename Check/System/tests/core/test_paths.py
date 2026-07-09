from __future__ import annotations
from pathlib import Path
import pytest
from engine.core.paths import CONFIG_RELATIVE_PATH, DEFAULT_CACHE_PATH, DEFAULT_CLIENTS_PATH, DEFAULT_HISTORY_PATH, DEFAULT_LOGS_PATH, DEFAULT_UNIVERSE_PATH, SystemPaths
from engine.protocol.constants import DEFAULT_ROOT_PATH, FILENAME_UNIVERSE
from engine.protocol.errors import ValidationError

@pytest.fixture
def root(tmp_path: Path) -> Path:
    return tmp_path

@pytest.fixture
def paths(root: Path) -> SystemPaths:
    return SystemPaths(root)

def test_system_paths_root_property(root: Path) -> None:
    system_paths = SystemPaths(root)
    assert system_paths.root == root.resolve()

def test_system_paths_default_root_matches_specification() -> None:
    system_paths = SystemPaths()
    assert str(system_paths.root) == str(Path(DEFAULT_ROOT_PATH).resolve())

def test_system_paths_config_path(root: Path) -> None:
    system_paths = SystemPaths(root)
    assert system_paths.config_path == root / CONFIG_RELATIVE_PATH

def test_system_paths_clients_dir(root: Path) -> None:
    system_paths = SystemPaths(root)
    assert system_paths.clients_dir == root / DEFAULT_CLIENTS_PATH

def test_system_paths_logs_dir(root: Path) -> None:
    system_paths = SystemPaths(root)
    assert system_paths.logs_dir == root / DEFAULT_LOGS_PATH

def test_system_paths_cache_dir(root: Path) -> None:
    system_paths = SystemPaths(root)
    assert system_paths.cache_dir == root / DEFAULT_CACHE_PATH

def test_system_paths_history_dir(root: Path) -> None:
    system_paths = SystemPaths(root)
    assert system_paths.history_dir == root / DEFAULT_HISTORY_PATH

def test_system_paths_universe_dir(root: Path) -> None:
    system_paths = SystemPaths(root)
    assert system_paths.universe_dir == root / DEFAULT_UNIVERSE_PATH

def test_system_paths_universe_file(root: Path) -> None:
    system_paths = SystemPaths(root)
    assert system_paths.universe_file == root / DEFAULT_UNIVERSE_PATH / FILENAME_UNIVERSE

def test_system_paths_account_dir(paths: SystemPaths, root: Path) -> None:
    assert paths.account_dir('12345') == root / 'data/clients/12345'

def test_system_paths_account_journal_dir(paths: SystemPaths, root: Path) -> None:
    assert paths.account_journal_dir('12345') == root / 'data/clients/12345/journal'

def test_system_paths_account_state_dir(paths: SystemPaths, root: Path) -> None:
    assert paths.account_state_dir('12345') == root / 'data/clients/12345/state'

def test_system_paths_instance_cache_dir(paths: SystemPaths, root: Path) -> None:
    assert paths.instance_cache_dir('12345', 'EURUSD', 100001) == root / 'data/cache/12345/EURUSD_100001'

def test_system_paths_instance_history_dir(paths: SystemPaths, root: Path) -> None:
    assert paths.instance_history_dir('12345', 'EURUSD', 100001) == root / 'data/history/12345/EURUSD_100001'

def test_system_paths_custom_relative_paths(root: Path) -> None:
    system_paths = SystemPaths(root, clients_path='custom/clients', logs_path='custom/logs', cache_path='custom/cache', history_path='custom/history', universe_path='custom/universe')
    assert system_paths.clients_dir == root / 'custom/clients'
    assert system_paths.logs_dir == root / 'custom/logs'
    assert system_paths.cache_dir == root / 'custom/cache'
    assert system_paths.history_dir == root / 'custom/history'
    assert system_paths.universe_dir == root / 'custom/universe'

def test_system_paths_rejects_empty_account_id(paths: SystemPaths) -> None:
    with pytest.raises(ValidationError, match='account_id'):
        paths.account_dir('')

def test_system_paths_rejects_empty_symbol(paths: SystemPaths) -> None:
    with pytest.raises(ValidationError, match='symbol'):
        paths.instance_cache_dir('12345', '  ', 1)

def test_system_paths_rejects_negative_magic(paths: SystemPaths) -> None:
    with pytest.raises(ValidationError, match='magic'):
        paths.instance_history_dir('12345', 'EURUSD', -1)

def test_ensure_directories_creates_global_data_hierarchy(paths: SystemPaths) -> None:
    paths.ensure_directories()
    assert paths.clients_dir.is_dir()
    assert paths.logs_dir.is_dir()
    assert paths.cache_dir.is_dir()
    assert paths.history_dir.is_dir()
    assert paths.universe_dir.is_dir()

def test_ensure_directories_is_idempotent(paths: SystemPaths) -> None:
    paths.ensure_directories()
    paths.ensure_directories()
    assert paths.clients_dir.is_dir()

def test_ensure_account_directories_creates_journal_and_state(paths: SystemPaths) -> None:
    paths.ensure_account_directories('12345')
    assert paths.account_dir('12345').is_dir()
    assert paths.account_journal_dir('12345').is_dir()
    assert paths.account_state_dir('12345').is_dir()

def test_ensure_instance_directories_creates_cache_and_history(paths: SystemPaths) -> None:
    paths.ensure_instance_directories('12345', 'EURUSD', 100001)
    assert paths.instance_cache_dir('12345', 'EURUSD', 100001).is_dir()
    assert paths.instance_history_dir('12345', 'EURUSD', 100001).is_dir()
    assert paths.account_journal_dir('12345').is_dir()
    assert paths.account_state_dir('12345').is_dir()
