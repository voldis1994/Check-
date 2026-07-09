from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from engine.core.atomic_io import atomic_read_text, atomic_write_text
from engine.core.instance import Instance
from engine.core.paths import SystemPaths
from engine.protocol.constants import PROTOCOL_SCHEMA_VERSION
from engine.protocol.errors import DataIOError

MODULE_NAME = "core.monitoring_store"


def _data_io_error(message: str, **context: object) -> DataIOError:
    return DataIOError(message, module=MODULE_NAME, context=dict(context))


@dataclass(frozen=True)
class PersistedMonitoringMetrics:
    schema_version: str
    account_id: str
    symbol: str
    magic: int
    timestamp_utc: str
    cycle_latency_ms: int | None
    ack_latency_ms: int | None
    data_freshness_ms: int | None
    error_count: int
    error_rate_per_min: float
    instance_health: str


def build_monitoring_snapshot_path(paths: SystemPaths, instance: Instance) -> Path:
    return paths.account_state_dir(instance.account_id) / instance.monitoring_snapshot_filename()


def persist_instance_metrics(
    paths: SystemPaths,
    instance: Instance,
    metrics: PersistedMonitoringMetrics,
) -> Path:
    snapshot_path = build_monitoring_snapshot_path(paths, instance)
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(snapshot_path, json.dumps(asdict(metrics), sort_keys=True))
    return snapshot_path


def load_instance_metrics(
    paths: SystemPaths,
    instance: Instance,
) -> PersistedMonitoringMetrics | None:
    snapshot_path = build_monitoring_snapshot_path(paths, instance)
    if not snapshot_path.exists():
        return None
    try:
        payload = json.loads(atomic_read_text(snapshot_path))
    except json.JSONDecodeError as exc:
        raise _data_io_error(
            "monitoring snapshot is not valid JSON",
            path=str(snapshot_path),
            error=str(exc),
        ) from exc
    if not isinstance(payload, dict):
        raise _data_io_error(
            "monitoring snapshot must be an object",
            path=str(snapshot_path),
        )
    return PersistedMonitoringMetrics(
        schema_version=str(payload.get("schema_version", PROTOCOL_SCHEMA_VERSION)),
        account_id=str(payload.get("account_id", instance.account_id)),
        symbol=str(payload.get("symbol", instance.symbol)),
        magic=int(payload.get("magic", instance.magic)),
        timestamp_utc=str(payload.get("timestamp_utc", "")),
        cycle_latency_ms=payload.get("cycle_latency_ms"),
        ack_latency_ms=payload.get("ack_latency_ms"),
        data_freshness_ms=payload.get("data_freshness_ms"),
        error_count=int(payload.get("error_count", 0)),
        error_rate_per_min=float(payload.get("error_rate_per_min", 0.0)),
        instance_health=str(payload.get("instance_health", "VALID")),
    )
