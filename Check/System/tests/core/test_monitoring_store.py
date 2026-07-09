from __future__ import annotations
import json
from pathlib import Path
from engine.core.instance import Instance
from engine.core.monitoring import MonitoringState, compute_error_rate_per_min, record_cycle_error
from engine.core.monitoring_store import PersistedMonitoringMetrics, load_instance_metrics, persist_instance_metrics
from engine.core.paths import SystemPaths
from engine.protocol.constants import PROTOCOL_SCHEMA_VERSION

def _instance() -> Instance:
    return Instance(account_id='12345', symbol='EURUSD', magic=100001)

def test_record_cycle_error_tracks_error_rate_per_min() -> None:
    state = MonitoringState()
    instance = _instance()
    record_cycle_error(state, instance, current_monotonic=100.0)
    record_cycle_error(state, instance, current_monotonic=110.0)
    timestamps = state.error_timestamps[instance.instance_key]
    rate = compute_error_rate_per_min(timestamps, current_monotonic=120.0)
    assert rate == 2.0

def test_persist_and_load_instance_metrics_round_trip(tmp_path: Path) -> None:
    paths = SystemPaths(tmp_path)
    paths.ensure_directories()
    instance = _instance()
    metrics = PersistedMonitoringMetrics(schema_version=PROTOCOL_SCHEMA_VERSION, account_id=instance.account_id, symbol=instance.symbol, magic=instance.magic, timestamp_utc='2026-07-07T06:00:00.000Z', cycle_latency_ms=1500, ack_latency_ms=800, data_freshness_ms=120000, error_count=2, error_rate_per_min=1.5, instance_health='VALID')
    persist_instance_metrics(paths, instance, metrics)
    loaded = load_instance_metrics(paths, instance)
    assert loaded is not None
    assert loaded.cycle_latency_ms == 1500
    assert loaded.error_rate_per_min == 1.5
    snapshot_path = paths.account_state_dir(instance.account_id) / instance.monitoring_snapshot_filename()
    assert json.loads(snapshot_path.read_text(encoding='utf-8'))['instance_health'] == 'VALID'
