from __future__ import annotations

import hashlib
import json
from pathlib import Path

from engine.core.atomic_io import atomic_read_text, atomic_write_json
from engine.core.instance import Instance
from engine.core.paths import SystemPaths

LAST_MARKET_HASH_FILENAME = "last_market.hash"
LAST_SENSOR_HASH_FILENAME = "last_sensor.hash"


def build_market_hash_path(paths: SystemPaths, instance: Instance) -> Path:
    return paths.instance_cache_dir(instance.account_id, instance.symbol, instance.magic) / LAST_MARKET_HASH_FILENAME


def build_sensor_hash_path(paths: SystemPaths, instance: Instance) -> Path:
    return paths.instance_cache_dir(instance.account_id, instance.symbol, instance.magic) / LAST_SENSOR_HASH_FILENAME


def content_hash(raw_text: str) -> str:
    return hashlib.sha256(raw_text.encode("utf-8")).hexdigest()


def should_reload(source_path: Path, hash_path: Path, raw_text: str) -> bool:
    if not hash_path.exists():
        return True

    current_hash = content_hash(raw_text)
    current_mtime_ns = source_path.stat().st_mtime_ns
    cached = parse_hash_record(atomic_read_text(hash_path))

    if cached["hash"] != current_hash:
        return True
    cached_mtime_ns = int(cached["modified_ns"])
    if cached_mtime_ns != current_mtime_ns:
        # Content hash has priority over modified-time conflicts.
        return False
    return False


def write_hash(source_path: Path, hash_path: Path, raw_text: str) -> None:
    payload = {
        "hash": content_hash(raw_text),
        "modified_ns": source_path.stat().st_mtime_ns,
    }
    atomic_write_json(hash_path, payload, pretty=True)


def invalidate_startup_cache(cache_dir: Path) -> int:
    if not cache_dir.exists():
        return 0
    removed = 0
    for hash_file in cache_dir.glob("*.hash"):
        if hash_file.is_file():
            hash_file.unlink()
            removed += 1
    return removed


def parse_hash_record(raw_text: str) -> dict[str, str | int]:
    payload = json.loads(raw_text)
    return {
        "hash": str(payload["hash"]),
        "modified_ns": int(payload["modified_ns"]),
    }
