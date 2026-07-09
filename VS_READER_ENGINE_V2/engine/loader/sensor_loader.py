from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import MutableMapping

from engine.core.atomic_io import atomic_read_text
from engine.core.cache import (
    build_sensor_hash_path,
    content_hash,
    should_reload,
    write_hash,
)
from engine.core.clock import format_utc_timestamp
from engine.core.instance import Instance
from engine.core.paths import SystemPaths
from engine.core.retry import RetryAlertContext, RetryPolicy


@dataclass(frozen=True)
class RawSensorData:
    file_path: Path
    modified_utc: str
    row_count: int
    raw_text: str
    history_rows: tuple[str, ...]
    last_row: str | None


@dataclass
class _CacheEntry:
    file_size: int
    modified_ns: int
    content_hash: str
    data: RawSensorData


def build_sensor_file_path(paths: SystemPaths, instance: Instance) -> Path:
    return paths.account_dir(instance.account_id) / instance.sensor_filename()


def _extract_rows(raw_text: str) -> tuple[tuple[str, ...], str | None]:
    rows = tuple(line for line in raw_text.splitlines() if line.strip())
    if len(rows) <= 1:
        return tuple(), None
    history = rows[1:]
    return history, history[-1]


def load_sensor_data(
    paths: SystemPaths,
    instance: Instance,
    *,
    cache: MutableMapping[str, _CacheEntry] | None = None,
    retry_policy: RetryPolicy | None = None,
    retry_alert_context: RetryAlertContext | None = None,
) -> RawSensorData:
    file_path = build_sensor_file_path(paths, instance)
    cache_key = str(file_path)
    stat = file_path.stat() if file_path.exists() else None
    if cache is not None:
        cached = cache.get(cache_key)
        if (
            cached is not None
            and stat is not None
            and cached.file_size == stat.st_size
            and cached.modified_ns == stat.st_mtime_ns
        ):
            return cached.data
        if cached is not None and stat is not None:
            hash_path = build_sensor_hash_path(paths, instance)
            if hash_path.exists() and not should_reload(file_path, hash_path, cached.data.raw_text):
                data = RawSensorData(
                    file_path=file_path,
                    modified_utc=format_utc_timestamp(datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)),
                    row_count=cached.data.row_count,
                    raw_text=cached.data.raw_text,
                    history_rows=cached.data.history_rows,
                    last_row=cached.data.last_row,
                )
                cache[cache_key] = _CacheEntry(
                    file_size=stat.st_size,
                    modified_ns=stat.st_mtime_ns,
                    content_hash=content_hash(cached.data.raw_text),
                    data=data,
                )
                return data

    raw_text = atomic_read_text(
        file_path,
        retry_policy=retry_policy,
        retry_alert_context=retry_alert_context,
    )
    stat = file_path.stat()
    write_hash(file_path, build_sensor_hash_path(paths, instance), raw_text)
    history_rows, last_row = _extract_rows(raw_text)
    data = RawSensorData(
        file_path=file_path,
        modified_utc=format_utc_timestamp(datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)),
        row_count=len(history_rows),
        raw_text=raw_text,
        history_rows=history_rows,
        last_row=last_row,
    )
    if cache is not None:
        cache[cache_key] = _CacheEntry(
            file_size=stat.st_size,
            modified_ns=stat.st_mtime_ns,
            content_hash=content_hash(raw_text),
            data=data,
        )
    return data
