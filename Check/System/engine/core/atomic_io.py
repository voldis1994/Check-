from __future__ import annotations
import json
import os
import time
from pathlib import Path
from typing import Any
from engine.core.retry import RetryAlertContext, RetryPolicy, run_with_retry
from engine.protocol.errors import DataIOError
ATOMIC_IO_MODULE = 'core.atomic_io'
DEFAULT_ENCODING = 'utf-8'
DEFAULT_STABILITY_CHECKS = 2
DEFAULT_READ_WAIT_ATTEMPTS = 20
DEFAULT_READ_WAIT_DELAY_MS = 50

def _io_error(message: str, **context: Any) -> DataIOError:
    return DataIOError(message, module=ATOMIC_IO_MODULE, context=context)

def _resolve_path(path: str | Path) -> Path:
    return Path(path)

def _tmp_path_for(path: Path) -> Path:
    return path.with_name(f'{path.name}.tmp')

def atomic_write_text(path: str | Path, content: str, *, encoding: str=DEFAULT_ENCODING, retry_policy: RetryPolicy | None=None, retry_alert_context: RetryAlertContext | None=None) -> None:
    if retry_policy is None:
        _atomic_write_text_once(path, content, encoding=encoding)
        return
    run_with_retry(retry_policy, lambda: _atomic_write_text_once(path, content, encoding=encoding), alert_context=retry_alert_context)

def _atomic_write_text_once(path: str | Path, content: str, *, encoding: str=DEFAULT_ENCODING) -> None:
    target_path = _resolve_path(path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = _tmp_path_for(target_path)
    try:
        with tmp_path.open('w', encoding=encoding) as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, target_path)
    except OSError as exc:
        raise _io_error('failed atomic text write', path=str(target_path), tmp_path=str(tmp_path), error=str(exc)) from exc

def is_file_stable(path: str | Path, *, checks: int=DEFAULT_STABILITY_CHECKS) -> bool:
    target_path = _resolve_path(path)
    if checks < 1:
        raise _io_error('checks must be >= 1', checks=checks)
    try:
        previous = target_path.stat()
    except OSError:
        return False
    for _ in range(checks):
        try:
            current = target_path.stat()
        except OSError:
            return False
        if (current.st_size, current.st_mtime_ns) != (previous.st_size, previous.st_mtime_ns):
            return False
        previous = current
    return True

def _is_transient_read_error(exc: DataIOError) -> bool:
    message = exc.message.lower()
    return 'tmp file exists' in message or 'not stable' in message

def atomic_read_text(path: str | Path, *, encoding: str=DEFAULT_ENCODING, retry_policy: RetryPolicy | None=None, retry_alert_context: RetryAlertContext | None=None) -> str:
    if retry_policy is not None:
        return run_with_retry(retry_policy, lambda: _atomic_read_text_once(path, encoding=encoding), alert_context=retry_alert_context)
    last_error: DataIOError | None = None
    for attempt in range(1, DEFAULT_READ_WAIT_ATTEMPTS + 1):
        try:
            return _atomic_read_text_once(path, encoding=encoding)
        except DataIOError as exc:
            last_error = exc
            if not _is_transient_read_error(exc) or attempt >= DEFAULT_READ_WAIT_ATTEMPTS:
                raise
            time.sleep(DEFAULT_READ_WAIT_DELAY_MS / 1000.0)
    if last_error is not None:
        raise last_error
    raise _io_error('failed atomic text read', path=str(_resolve_path(path)))

def _atomic_read_text_once(path: str | Path, *, encoding: str=DEFAULT_ENCODING) -> str:
    target_path = _resolve_path(path)
    tmp_path = _tmp_path_for(target_path)
    if tmp_path.exists():
        raise _io_error('tmp file exists, final file is not ready', path=str(target_path), tmp_path=str(tmp_path))
    if not target_path.exists():
        raise _io_error('target file does not exist', path=str(target_path))
    if not is_file_stable(target_path):
        raise _io_error('target file is not stable', path=str(target_path))
    try:
        return target_path.read_text(encoding=encoding)
    except OSError as exc:
        raise _io_error('failed atomic text read', path=str(target_path), error=str(exc)) from exc

def atomic_write_json(path: str | Path, payload: dict[str, Any], *, pretty: bool=False) -> None:
    if not isinstance(payload, dict):
        raise _io_error('payload must be a dict', path=str(_resolve_path(path)), payload_type=type(payload).__name__)
    try:
        if pretty:
            content = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + '\n'
        else:
            content = json.dumps(payload, ensure_ascii=False, separators=(',', ':'), sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise _io_error('failed to serialize json payload', path=str(_resolve_path(path)), error=str(exc)) from exc
    atomic_write_text(path, content)
