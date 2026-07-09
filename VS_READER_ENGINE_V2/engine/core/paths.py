from __future__ import annotations

from pathlib import Path

from engine.protocol.constants import DEFAULT_ROOT_PATH, FILENAME_UNIVERSE
from engine.protocol.identity import validate_account_id, validate_magic, validate_symbol
from engine.protocol.errors import ValidationError

PATHS_MODULE = "core.paths"

DEFAULT_CLIENTS_PATH = "data/clients"
DEFAULT_LOGS_PATH = "data/logs"
DEFAULT_CACHE_PATH = "data/cache"
DEFAULT_HISTORY_PATH = "data/history"
DEFAULT_UNIVERSE_PATH = "data/universe"
CONFIG_RELATIVE_PATH = "config/system.json"

ACCOUNT_JOURNAL_DIRNAME = "journal"
ACCOUNT_STATE_DIRNAME = "state"


def _validation_error(message: str, **context: object) -> ValidationError:
    return ValidationError(message, module=PATHS_MODULE, context=dict(context))


def _normalize_relative_path(value: str, field_name: str) -> str:
    if not isinstance(value, str):
        raise _validation_error(
            f"{field_name} must be a string",
            field=field_name,
            value_type=type(value).__name__,
        )
    normalized = value.replace("\\", "/").strip()
    if not normalized:
        raise _validation_error(f"{field_name} must not be empty", field=field_name)
    if normalized.startswith("/") or ":" in normalized:
        raise _validation_error(
            f"{field_name} must be a relative path",
            field=field_name,
            value=value,
        )
    return normalized


def _instance_segment(symbol: str, magic: int) -> str:
    return f"{validate_symbol(symbol, PATHS_MODULE)}_{validate_magic(magic, PATHS_MODULE)}"


class SystemPaths:
    def __init__(
        self,
        root_path: str | Path | None = None,
        *,
        clients_path: str = DEFAULT_CLIENTS_PATH,
        logs_path: str = DEFAULT_LOGS_PATH,
        cache_path: str = DEFAULT_CACHE_PATH,
        history_path: str = DEFAULT_HISTORY_PATH,
        universe_path: str = DEFAULT_UNIVERSE_PATH,
    ) -> None:
        resolved_root = root_path if root_path is not None else DEFAULT_ROOT_PATH
        self._root = Path(resolved_root).expanduser().resolve()
        self._clients_path = _normalize_relative_path(clients_path, "clients_path")
        self._logs_path = _normalize_relative_path(logs_path, "logs_path")
        self._cache_path = _normalize_relative_path(cache_path, "cache_path")
        self._history_path = _normalize_relative_path(history_path, "history_path")
        self._universe_path = _normalize_relative_path(universe_path, "universe_path")

    @property
    def root(self) -> Path:
        return self._root

    @property
    def config_path(self) -> Path:
        return self._root / CONFIG_RELATIVE_PATH

    @property
    def clients_dir(self) -> Path:
        return self._root / self._clients_path

    @property
    def logs_dir(self) -> Path:
        return self._root / self._logs_path

    @property
    def cache_dir(self) -> Path:
        return self._root / self._cache_path

    @property
    def history_dir(self) -> Path:
        return self._root / self._history_path

    @property
    def universe_dir(self) -> Path:
        return self._root / self._universe_path

    @property
    def universe_file(self) -> Path:
        return self.universe_dir / FILENAME_UNIVERSE

    def account_dir(self, account_id: str) -> Path:
        return self.clients_dir / validate_account_id(account_id, PATHS_MODULE)

    def account_journal_dir(self, account_id: str) -> Path:
        return self.account_dir(account_id) / ACCOUNT_JOURNAL_DIRNAME

    def account_state_dir(self, account_id: str) -> Path:
        return self.account_dir(account_id) / ACCOUNT_STATE_DIRNAME

    def instance_cache_dir(self, account_id: str, symbol: str, magic: int) -> Path:
        return self.cache_dir / validate_account_id(account_id, PATHS_MODULE) / _instance_segment(
            symbol,
            magic,
        )

    def instance_history_dir(self, account_id: str, symbol: str, magic: int) -> Path:
        return self.history_dir / validate_account_id(account_id, PATHS_MODULE) / _instance_segment(
            symbol,
            magic,
        )

    def ensure_directories(self) -> None:
        for directory in (
            self.clients_dir,
            self.logs_dir,
            self.cache_dir,
            self.history_dir,
            self.universe_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)

    def ensure_account_directories(self, account_id: str) -> None:
        self.ensure_directories()
        for directory in (
            self.account_dir(account_id),
            self.account_journal_dir(account_id),
            self.account_state_dir(account_id),
        ):
            directory.mkdir(parents=True, exist_ok=True)

    def ensure_instance_directories(self, account_id: str, symbol: str, magic: int) -> None:
        self.ensure_account_directories(account_id)
        for directory in (
            self.instance_cache_dir(account_id, symbol, magic),
            self.instance_history_dir(account_id, symbol, magic),
        ):
            directory.mkdir(parents=True, exist_ok=True)
