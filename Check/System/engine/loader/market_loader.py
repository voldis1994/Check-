from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import MutableMapping
from engine.core.atomic_io import atomic_read_text
from engine.core.cache import build_market_hash_path, content_hash, should_reload, write_hash
from engine.core.clock import format_utc_timestamp
from engine.core.instance import Instance
from engine.core.paths import SystemPaths
from engine.core.retry import RetryAlertContext, RetryPolicy

@dataclass(frozen=True)
class RawMarketData:
    file_path: Path
    modified_utc: str
    row_count: int
    raw_text: str

@dataclass
class _CacheEntry:
    file_size: int
    modified_ns: int
    content_hash: str
    data: RawMarketData

def build_market_file_path(paths: SystemPaths, instance: Instance) -> Path:
    return paths.account_dir(instance.account_id) / instance.market_filename()

def _count_rows(raw_text: str) -> int:
    lines = [line for line in raw_text.splitlines() if line.strip()]
    if not lines:
        return 0
    return max(0, len(lines) - 1)

def load_market_data(paths: SystemPaths, instance: Instance, *, cache: MutableMapping[str, _CacheEntry] | None=None, retry_policy: RetryPolicy | None=None, retry_alert_context: RetryAlertContext | None=None) -> RawMarketData:
    file_path = build_market_file_path(paths, instance)
    cache_key = str(file_path)
    stat = file_path.stat() if file_path.exists() else None
    if cache is not None:
        cached = cache.get(cache_key)
        if cached is not None and stat is not None and (cached.file_size == stat.st_size) and (cached.modified_ns == stat.st_mtime_ns):
            return cached.data
        if cached is not None and stat is not None:
            hash_path = build_market_hash_path(paths, instance)
            if hash_path.exists() and (not should_reload(file_path, hash_path, cached.data.raw_text)):
                data = RawMarketData(file_path=file_path, modified_utc=format_utc_timestamp(datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)), row_count=cached.data.row_count, raw_text=cached.data.raw_text)
                cache[cache_key] = _CacheEntry(file_size=stat.st_size, modified_ns=stat.st_mtime_ns, content_hash=content_hash(cached.data.raw_text), data=data)
                return data
    raw_text = atomic_read_text(file_path, retry_policy=retry_policy, retry_alert_context=retry_alert_context)
    stat = file_path.stat()
    write_hash(file_path, build_market_hash_path(paths, instance), raw_text)
    modified_utc = format_utc_timestamp(datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc))
    row_count = _count_rows(raw_text)
    data = RawMarketData(file_path=file_path, modified_utc=modified_utc, row_count=row_count, raw_text=raw_text)
    if cache is not None:
        cache[cache_key] = _CacheEntry(file_size=stat.st_size, modified_ns=stat.st_mtime_ns, content_hash=content_hash(raw_text), data=data)
    return data
