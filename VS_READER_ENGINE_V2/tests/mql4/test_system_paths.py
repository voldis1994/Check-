from __future__ import annotations

from pathlib import Path

import pytest

from engine.core.paths import (
    DEFAULT_CACHE_PATH,
    DEFAULT_CLIENTS_PATH,
    DEFAULT_HISTORY_PATH,
    DEFAULT_LOGS_PATH,
    DEFAULT_UNIVERSE_PATH,
)
from engine.protocol.constants import DEFAULT_ROOT_PATH
from tests.mql4 import mql_source, path_reference


@pytest.fixture
def paths_source() -> str:
    return mql_source.load_mqh("SYSTEM_Paths.mqh")


@pytest.fixture
def root_config_source() -> str:
    return mql_source.load_mqh("SYSTEM_RootConfig.mqh")


def test_system_paths_source_defines_root_path_as_c_system(root_config_source: str) -> None:
    assert mql_source.parse_define(root_config_source, "SYSTEM_ROOT_PATH") == r"C:\SYSTEM"


def test_system_paths_constants_match_python_core_paths(paths_source: str) -> None:
    assert mql_source.parse_define(paths_source, "SYSTEM_CLIENTS_RELATIVE_PATH") == DEFAULT_CLIENTS_PATH.replace(
        "/",
        "\\",
    )
    assert mql_source.parse_define(paths_source, "SYSTEM_LOGS_RELATIVE_PATH") == DEFAULT_LOGS_PATH.replace("/", "\\")
    assert mql_source.parse_define(paths_source, "SYSTEM_CACHE_RELATIVE_PATH") == DEFAULT_CACHE_PATH.replace(
        "/",
        "\\",
    )
    assert mql_source.parse_define(paths_source, "SYSTEM_HISTORY_RELATIVE_PATH") == DEFAULT_HISTORY_PATH.replace(
        "/",
        "\\",
    )
    assert mql_source.parse_define(paths_source, "SYSTEM_UNIVERSE_RELATIVE_PATH") == DEFAULT_UNIVERSE_PATH.replace(
        "/",
        "\\",
    )


def test_system_paths_public_functions_are_defined(paths_source: str) -> None:
    expected = {
        "SYSTEM_GetRootPath",
        "SYSTEM_GetClientsRelativePath",
        "SYSTEM_GetLogsRelativePath",
        "SYSTEM_GetCacheRelativePath",
        "SYSTEM_GetHistoryRelativePath",
        "SYSTEM_GetUniverseRelativePath",
        "SYSTEM_JoinPath",
        "SYSTEM_BuildClientsDir",
        "SYSTEM_BuildAccountDir",
        "SYSTEM_BuildAccountJournalDir",
        "SYSTEM_BuildAccountStateDir",
        "SYSTEM_BuildLogsDir",
        "SYSTEM_BuildCacheDir",
        "SYSTEM_BuildHistoryDir",
        "SYSTEM_BuildUniverseDir",
        "SYSTEM_DirectoryExists",
        "SYSTEM_EnsureDirectory",
        "SYSTEM_EnsureDirectories",
        "SYSTEM_EnsureAccountDirectories",
        "SYSTEM_InitPaths",
    }
    assert expected.issubset(set(mql_source.public_function_names(paths_source)))


def test_system_get_root_path_returns_specified_root(paths_source: str) -> None:
    body = mql_source.function_body(paths_source, "SYSTEM_GetRootPath")
    assert "SYSTEM_ROOT_PATH" in body
    assert "g_system_root_override" in body


def test_system_get_clients_relative_path_returns_clients_segment(paths_source: str) -> None:
    body = mql_source.function_body(paths_source, "SYSTEM_GetClientsRelativePath")
    assert "SYSTEM_CLIENTS_RELATIVE_PATH" in body


def test_system_get_logs_relative_path_returns_logs_segment(paths_source: str) -> None:
    body = mql_source.function_body(paths_source, "SYSTEM_GetLogsRelativePath")
    assert "SYSTEM_LOGS_RELATIVE_PATH" in body


def test_system_get_cache_relative_path_returns_cache_segment(paths_source: str) -> None:
    body = mql_source.function_body(paths_source, "SYSTEM_GetCacheRelativePath")
    assert "SYSTEM_CACHE_RELATIVE_PATH" in body


def test_system_get_history_relative_path_returns_history_segment(paths_source: str) -> None:
    body = mql_source.function_body(paths_source, "SYSTEM_GetHistoryRelativePath")
    assert "SYSTEM_HISTORY_RELATIVE_PATH" in body


def test_system_get_universe_relative_path_returns_universe_segment(paths_source: str) -> None:
    body = mql_source.function_body(paths_source, "SYSTEM_GetUniverseRelativePath")
    assert "SYSTEM_UNIVERSE_RELATIVE_PATH" in body


def test_system_join_path_normalizes_separators() -> None:
    assert path_reference.join_path("C:\\SYSTEM", "data\\clients") == "C:\\SYSTEM\\data\\clients"
    assert path_reference.join_path("C:\\SYSTEM\\", "\\data\\clients") == "C:\\SYSTEM\\data\\clients"
    assert path_reference.join_path("", "data\\clients") == "data\\clients"
    assert path_reference.join_path("C:\\SYSTEM", "") == "C:\\SYSTEM"


def test_system_build_clients_dir_matches_python_paths() -> None:
    root = DEFAULT_ROOT_PATH
    clients = DEFAULT_CLIENTS_PATH.replace("/", "\\")
    expected = path_reference.join_path(root, clients)
    assert path_reference.build_clients_dir(root, clients) == expected


def test_system_build_account_dir_matches_python_paths() -> None:
    root = DEFAULT_ROOT_PATH
    clients = DEFAULT_CLIENTS_PATH.replace("/", "\\")
    expected = path_reference.join_path(path_reference.build_clients_dir(root, clients), "12345")
    assert path_reference.build_account_dir(root, clients, "12345") == expected


def test_system_build_account_journal_dir_matches_python_paths() -> None:
    root = DEFAULT_ROOT_PATH
    clients = DEFAULT_CLIENTS_PATH.replace("/", "\\")
    expected = path_reference.join_path(
        path_reference.build_account_dir(root, clients, "12345"),
        "journal",
    )
    assert path_reference.build_account_journal_dir(root, clients, "12345") == expected


def test_system_build_account_state_dir_matches_python_paths() -> None:
    root = DEFAULT_ROOT_PATH
    clients = DEFAULT_CLIENTS_PATH.replace("/", "\\")
    expected = path_reference.join_path(
        path_reference.build_account_dir(root, clients, "12345"),
        "state",
    )
    assert path_reference.build_account_state_dir(root, clients, "12345") == expected


def test_system_build_logs_dir_matches_python_paths() -> None:
    root = DEFAULT_ROOT_PATH
    logs = DEFAULT_LOGS_PATH.replace("/", "\\")
    assert path_reference.build_logs_dir(root, logs) == path_reference.join_path(root, logs)


def test_system_build_cache_dir_matches_python_paths() -> None:
    root = DEFAULT_ROOT_PATH
    cache = DEFAULT_CACHE_PATH.replace("/", "\\")
    assert path_reference.build_cache_dir(root, cache) == path_reference.join_path(root, cache)


def test_system_build_history_dir_matches_python_paths() -> None:
    root = DEFAULT_ROOT_PATH
    history = DEFAULT_HISTORY_PATH.replace("/", "\\")
    assert path_reference.build_history_dir(root, history) == path_reference.join_path(root, history)


def test_system_build_universe_dir_matches_python_paths() -> None:
    root = DEFAULT_ROOT_PATH
    universe = DEFAULT_UNIVERSE_PATH.replace("/", "\\")
    assert path_reference.build_universe_dir(root, universe) == path_reference.join_path(root, universe)


def test_system_directory_exists_uses_get_file_attributes(paths_source: str) -> None:
    body = mql_source.function_body(paths_source, "SYSTEM_DirectoryExists")
    assert "GetFileAttributesW" in body
    assert "SYSTEM_FILE_ATTRIBUTE_DIRECTORY" in body


def test_system_ensure_directory_creates_parents_recursively(paths_source: str) -> None:
    body = mql_source.function_body(paths_source, "SYSTEM_EnsureDirectory")
    assert "CreateDirectoryW" in body
    assert "SYSTEM_EnsureDirectory(parent)" in body


def test_system_ensure_directories_creates_global_data_dirs(paths_source: str) -> None:
    body = mql_source.function_body(paths_source, "SYSTEM_EnsureDirectories")
    assert "SYSTEM_BuildClientsDir" in body
    assert "SYSTEM_BuildLogsDir" in body
    assert "SYSTEM_BuildCacheDir" in body
    assert "SYSTEM_BuildHistoryDir" in body
    assert "SYSTEM_BuildUniverseDir" in body


def test_system_ensure_account_directories_creates_account_journal_and_state(
    tmp_path: Path,
    paths_source: str,
) -> None:
    body = mql_source.function_body(paths_source, "SYSTEM_EnsureAccountDirectories")
    assert "SYSTEM_EnsureDirectories" in body
    assert "SYSTEM_BuildAccountDir" in body
    assert "SYSTEM_BuildAccountJournalDir" in body
    assert "SYSTEM_BuildAccountStateDir" in body

    account_dir = path_reference.ensure_account_directories(
        tmp_path,
        "12345",
        clients="data\\clients",
        logs="data\\logs",
        cache="data\\cache",
        history="data\\history",
        universe="data\\universe",
    )

    assert account_dir == tmp_path / "data" / "clients" / "12345"
    assert (account_dir / "journal").is_dir()
    assert (account_dir / "state").is_dir()


def test_ea_startup_creates_data_clients_account_directory(tmp_path: Path, paths_source: str) -> None:
    account_id = "67890"
    account_dir = path_reference.ensure_account_directories(
        tmp_path,
        account_id,
        clients=mql_source.parse_define(paths_source, "SYSTEM_CLIENTS_RELATIVE_PATH"),
        logs=mql_source.parse_define(paths_source, "SYSTEM_LOGS_RELATIVE_PATH"),
        cache=mql_source.parse_define(paths_source, "SYSTEM_CACHE_RELATIVE_PATH"),
        history=mql_source.parse_define(paths_source, "SYSTEM_HISTORY_RELATIVE_PATH"),
        universe=mql_source.parse_define(paths_source, "SYSTEM_UNIVERSE_RELATIVE_PATH"),
    )

    assert account_dir.exists()
    assert account_dir == tmp_path / "data" / "clients" / account_id


def test_system_init_paths_uses_account_number(paths_source: str) -> None:
    body = mql_source.function_body(paths_source, "SYSTEM_InitPaths")
    assert "AccountNumber" in body
    assert "SYSTEM_EnsureAccountDirectories" in body


def test_system_path_points_to_c_system_root(root_config_source: str, paths_source: str) -> None:
    root = mql_source.parse_define(root_config_source, "SYSTEM_ROOT_PATH")
    clients = mql_source.parse_define(paths_source, "SYSTEM_CLIENTS_RELATIVE_PATH")
    account_dir = path_reference.build_account_dir(root, clients, "12345")
    assert account_dir == r"C:\SYSTEM\data\clients\12345"
