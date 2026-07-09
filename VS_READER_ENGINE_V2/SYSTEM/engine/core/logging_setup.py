from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from engine.core.paths import SystemPaths
from engine.protocol.constants import LogLevel
from engine.protocol.errors import ConfigurationError

LOGGING_MODULE = "core.logging_setup"
DEFAULT_LOG_FORMAT = "standard"
LOG_ENCODING = "utf-8"


def _config_error(message: str, **context: object) -> ConfigurationError:
    return ConfigurationError(message, module=LOGGING_MODULE, context=dict(context))


def _normalize_format_name(format_name: str) -> str:
    if not isinstance(format_name, str):
        raise _config_error(
            "log format must be a string",
            field="logging.format",
            value_type=type(format_name).__name__,
        )
    value = format_name.strip().lower()
    if value != DEFAULT_LOG_FORMAT:
        raise _config_error(
            "unsupported log format",
            field="logging.format",
            value=format_name,
            allowed=[DEFAULT_LOG_FORMAT],
        )
    return value


def _to_level(level: str) -> int:
    if not isinstance(level, str):
        raise _config_error(
            "log level must be a string",
            field="logging.level",
            value_type=type(level).__name__,
        )
    normalized = level.strip().upper()
    if normalized not in LogLevel._value2member_map_:
        raise _config_error(
            "unsupported log level",
            field="logging.level",
            value=level,
            allowed=[member.value for member in LogLevel],
        )
    return getattr(logging, normalized)


def _build_log_filename(prefix: str) -> str:
    date_stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"{prefix}_{date_stamp}.log"


class _StructuredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        dt = datetime.fromtimestamp(record.created, tz=timezone.utc)
        timestamp_utc = dt.isoformat(timespec="milliseconds").replace("+00:00", "Z")
        module_name = getattr(record, "module_name", record.name)
        account_id = getattr(record, "account_id", "-")
        symbol = getattr(record, "symbol", "-")
        magic = getattr(record, "magic", "-")
        message = record.getMessage()
        return (
            f"{timestamp_utc} | {record.levelname} | {module_name} | "
            f"{account_id} | {symbol} | {magic} | {message}"
        )


def _configure_file_logger(name: str, level: str, log_path: Path, format_name: str) -> logging.Logger:
    _normalize_format_name(format_name)
    level_value = _to_level(level)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(level_value)
    logger.propagate = False
    logger.handlers.clear()

    handler = logging.FileHandler(log_path, mode="a", encoding=LOG_ENCODING)
    handler.setLevel(level_value)
    handler.setFormatter(_StructuredFormatter())
    logger.addHandler(handler)
    return logger


def setup_system_logger(
    paths: SystemPaths,
    *,
    level: str = LogLevel.INFO.value,
    format_name: str = DEFAULT_LOG_FORMAT,
) -> logging.Logger:
    if not isinstance(paths, SystemPaths):
        raise _config_error("paths must be SystemPaths", field="paths")
    return _configure_file_logger(
        name="system",
        level=level,
        log_path=paths.logs_dir / _build_log_filename("system"),
        format_name=format_name,
    )


def setup_account_logger(
    paths: SystemPaths,
    account_id: str,
    *,
    level: str = LogLevel.INFO.value,
    format_name: str = DEFAULT_LOG_FORMAT,
) -> logging.Logger:
    if not isinstance(paths, SystemPaths):
        raise _config_error("paths must be SystemPaths", field="paths")
    if not isinstance(account_id, str) or not account_id.strip():
        raise _config_error("account_id must be a non-empty string", field="account_id")
    clean_account_id = account_id.strip()
    return _configure_file_logger(
        name=f"account.{clean_account_id}",
        level=level,
        log_path=paths.logs_dir / _build_log_filename(f"account_{clean_account_id}"),
        format_name=format_name,
    )


def log_event(
    logger: logging.Logger,
    *,
    level: str,
    module: str,
    message: str,
    account_id: str | None = None,
    symbol: str | None = None,
    magic: int | None = None,
) -> None:
    if not isinstance(logger, logging.Logger):
        raise _config_error("logger must be logging.Logger", field="logger")
    if not isinstance(module, str) or not module.strip():
        raise _config_error("module must be a non-empty string", field="module")
    if not isinstance(message, str) or not message.strip():
        raise _config_error("message must be a non-empty string", field="message")

    level_value = _to_level(level)
    logger.log(
        level_value,
        message.strip(),
        extra={
            "module_name": module.strip(),
            "account_id": account_id.strip() if isinstance(account_id, str) and account_id.strip() else "-",
            "symbol": symbol.strip() if isinstance(symbol, str) and symbol.strip() else "-",
            "magic": magic if magic is not None else "-",
        },
    )
