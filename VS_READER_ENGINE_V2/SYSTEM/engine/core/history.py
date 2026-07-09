from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

from engine.core.atomic_io import atomic_read_text, atomic_write_text
from engine.core.clock import format_utc_timestamp
from engine.core.instance import Instance
from engine.core.paths import SystemPaths
from engine.loader.market_loader import build_market_file_path
from engine.protocol.errors import DataIOError

MODULE_NAME = "core.history"


def _build_control_path(paths: SystemPaths, instance: Instance) -> Path:
    return paths.account_dir(instance.account_id) / instance.control_filename()


def _build_ack_path(paths: SystemPaths, instance: Instance) -> Path:
    return paths.account_dir(instance.account_id) / instance.ack_filename()


def _history_error(message: str, **context: object) -> DataIOError:
    return DataIOError(message, module=MODULE_NAME, context=dict(context))


def _parse_utc_date(value: str | None) -> str:
    resolved = value or format_utc_timestamp(datetime.now(timezone.utc))
    normalized = resolved.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).strftime("%Y-%m-%d")


def _archive_file(source: Path, destination: Path) -> Path | None:
    if not source.exists():
        return None
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(destination))
    return destination


def archive_processed_control(paths: SystemPaths, instance: Instance) -> Path | None:
    control_path = _build_control_path(paths, instance)
    destination_dir = paths.instance_history_dir(
        instance.account_id,
        instance.symbol,
        instance.magic,
    )
    destination = destination_dir / instance.control_filename()
    return _archive_file(control_path, destination)


def archive_processed_ack(paths: SystemPaths, instance: Instance) -> Path | None:
    ack_path = _build_ack_path(paths, instance)
    destination_dir = paths.instance_history_dir(
        instance.account_id,
        instance.symbol,
        instance.magic,
    )
    destination = destination_dir / instance.ack_filename()
    return _archive_file(ack_path, destination)


def archive_market_snapshot(
    paths: SystemPaths,
    instance: Instance,
    *,
    current_utc: str | None = None,
) -> Path | None:
    market_path = build_market_file_path(paths, instance)
    if not market_path.exists():
        return None
    destination_dir = paths.instance_history_dir(
        instance.account_id,
        instance.symbol,
        instance.magic,
    )
    destination_dir.mkdir(parents=True, exist_ok=True)
    archive_date = _parse_utc_date(current_utc)
    destination = destination_dir / f"market_{archive_date}.csv"
    try:
        content = atomic_read_text(market_path)
        atomic_write_text(destination, content)
    except DataIOError:
        return None
    return destination


def find_latest_archived_file(directory: Path, *, prefix: str) -> Path | None:
    if not directory.is_dir():
        return None
    matches = sorted(
        (entry for entry in directory.iterdir() if entry.is_file() and entry.name.startswith(prefix)),
        key=lambda entry: entry.stat().st_mtime,
    )
    if not matches:
        return None
    return matches[-1]


def read_archived_control_text(paths: SystemPaths, instance: Instance) -> str | None:
    history_dir = paths.instance_history_dir(
        instance.account_id,
        instance.symbol,
        instance.magic,
    )
    canonical = history_dir / instance.control_filename()
    if canonical.exists():
        return atomic_read_text(canonical)
    archived = find_latest_archived_file(history_dir, prefix="control_")
    if archived is None:
        return None
    return atomic_read_text(archived)
