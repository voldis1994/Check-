from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import MutableMapping

from engine.core.atomic_io import atomic_read_text
from engine.core.clock import format_utc_timestamp
from engine.core.paths import SystemPaths
from engine.core.retry import RetryAlertContext, RetryPolicy
from engine.protocol.constants import FILENAME_STATUS


@dataclass(frozen=True)
class RawStatusData:
    file_path: Path
    modified_utc: str
    raw_text: str
    content_hash: str


@dataclass
class _CacheEntry:
    file_size: int
    modified_ns: int
    data: RawStatusData


def build_status_file_path(paths: SystemPaths, account_id: str) -> Path:
    return paths.account_dir(account_id) / FILENAME_STATUS.format(account_id=account_id)


def _content_hash(raw_text: str) -> str:
    return hashlib.sha256(raw_text.encode("utf-8")).hexdigest()


def load_status_data(
    paths: SystemPaths,
    account_id: str,
    *,
    cache: MutableMapping[str, _CacheEntry] | None = None,
    retry_policy: RetryPolicy | None = None,
    retry_alert_context: RetryAlertContext | None = None,
) -> RawStatusData:
    file_path = build_status_file_path(paths, account_id)
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

    raw_text = atomic_read_text(
        file_path,
        retry_policy=retry_policy,
        retry_alert_context=retry_alert_context,
    )
    stat = file_path.stat()
    data = RawStatusData(
        file_path=file_path,
        modified_utc=format_utc_timestamp(datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)),
        raw_text=raw_text,
        content_hash=_content_hash(raw_text),
    )
    if cache is not None:
        cache[cache_key] = _CacheEntry(
            file_size=stat.st_size,
            modified_ns=stat.st_mtime_ns,
            data=data,
        )
    return data
