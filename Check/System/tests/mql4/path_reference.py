from __future__ import annotations
from pathlib import Path

def join_path(left: str, right: str) -> str:
    if not left:
        return right
    if not right:
        return left
    normalized_left = left.rstrip('\\')
    normalized_right = right.lstrip('\\')
    return f'{normalized_left}\\{normalized_right}'

def build_clients_dir(root_path: str, clients_relative: str) -> str:
    return join_path(root_path, clients_relative)

def build_account_dir(root_path: str, clients_relative: str, account_id: str) -> str:
    return join_path(build_clients_dir(root_path, clients_relative), account_id)

def build_account_journal_dir(root_path: str, clients_relative: str, account_id: str) -> str:
    return join_path(build_account_dir(root_path, clients_relative, account_id), 'journal')

def build_account_state_dir(root_path: str, clients_relative: str, account_id: str) -> str:
    return join_path(build_account_dir(root_path, clients_relative, account_id), 'state')

def build_logs_dir(root_path: str, logs_relative: str) -> str:
    return join_path(root_path, logs_relative)

def build_cache_dir(root_path: str, cache_relative: str) -> str:
    return join_path(root_path, cache_relative)

def build_history_dir(root_path: str, history_relative: str) -> str:
    return join_path(root_path, history_relative)

def build_universe_dir(root_path: str, universe_relative: str) -> str:
    return join_path(root_path, universe_relative)

def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)

def ensure_directories(root_path: Path, *, clients: str, logs: str, cache: str, history: str, universe: str) -> None:
    ensure_directory(root_path / clients.replace('\\', '/'))
    ensure_directory(root_path / logs.replace('\\', '/'))
    ensure_directory(root_path / cache.replace('\\', '/'))
    ensure_directory(root_path / history.replace('\\', '/'))
    ensure_directory(root_path / universe.replace('\\', '/'))

def ensure_account_directories(root_path: Path, account_id: str, *, clients: str, logs: str, cache: str, history: str, universe: str) -> Path:
    ensure_directories(root_path, clients=clients, logs=logs, cache=cache, history=history, universe=universe)
    account_dir = root_path / clients.replace('\\', '/') / account_id
    journal_dir = account_dir / 'journal'
    state_dir = account_dir / 'state'
    ensure_directory(account_dir)
    ensure_directory(journal_dir)
    ensure_directory(state_dir)
    return account_dir
