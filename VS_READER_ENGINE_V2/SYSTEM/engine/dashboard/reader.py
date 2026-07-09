from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from engine.core.atomic_io import atomic_read_text
from engine.core.clock import now_utc
from engine.core.instance import Instance
from engine.core.lifecycle import discover_instances
from engine.core.paths import SystemPaths
from engine.core.monitoring_store import load_instance_metrics
from engine.execution.ack_reader import build_ack_path, read_ack_record
from engine.journal.decision_journal import build_decision_journal_path
from engine.journal.error_journal import build_error_journal_path
from engine.protocol.errors import SystemError
from engine.protocol.models import SystemConfig
from engine.protocol.parser import parse_decision_journal_line, parse_error_journal_line
from engine.state.instance_state import InstanceState
from engine.state.spread_state import SpreadState

MODULE_NAME = "dashboard.reader"


@dataclass(frozen=True)
class InstanceDashboardView:
    instance: Instance
    last_decision: str | None
    last_reason: str | None
    risk_result: str | None
    risk_reason: str | None
    relative_spread: float | None
    open_ticket: int | None
    position_side: str | None
    position_volume: float | None
    last_ack_status: str | None
    last_ack_command_id: str | None
    last_error_message: str | None
    last_error_type: str | None
    instance_health: str | None = None
    cycle_latency_ms: int | None = None
    ack_latency_ms: int | None = None
    data_freshness_ms: int | None = None
    error_count: int | None = None
    error_rate_per_min: float | None = None


@dataclass(frozen=True)
class DashboardSnapshot:
    generated_at_utc: str
    instances: tuple[InstanceDashboardView, ...]
    monitoring_lines: tuple[str, ...] = ()

    @property
    def instance_count(self) -> int:
        return len(self.instances)


def read_last_journal_line(path: Path) -> str | None:
    if not path.exists():
        return None
    last_line: str | None = None
    for line in atomic_read_text(path).splitlines():
        stripped = line.strip()
        if stripped:
            last_line = stripped
    return last_line


def read_last_decision_entry(paths: SystemPaths, instance: Instance):
    journal_path = build_decision_journal_path(paths, instance)
    last_line = read_last_journal_line(journal_path)
    if last_line is None:
        return None
    try:
        return parse_decision_journal_line(last_line)
    except SystemError:
        return None


def read_last_error_entry(paths: SystemPaths, instance: Instance):
    journal_path = build_error_journal_path(paths, instance)
    last_line = read_last_journal_line(journal_path)
    if last_line is None:
        return None
    try:
        return parse_error_journal_line(last_line)
    except SystemError:
        return None


def read_last_ack(paths: SystemPaths, instance: Instance) -> tuple[str | None, str | None]:
    ack_path = build_ack_path(paths, instance)
    if not ack_path.exists():
        return None, None
    try:
        ack_record = read_ack_record(paths, instance)
    except SystemError:
        return None, None
    return ack_record.status, ack_record.command_id


def read_instance_dashboard_view(paths: SystemPaths, instance: Instance) -> InstanceDashboardView:
    instance_state = InstanceState.load(paths, instance)
    spread_state = SpreadState.load(paths, instance)
    decision_entry = read_last_decision_entry(paths, instance)
    error_entry = read_last_error_entry(paths, instance)
    ack_status, ack_command_id = read_last_ack(paths, instance)

    if ack_status is None:
        ack_status = instance_state.last_ack_status or None
    if ack_command_id is None and instance_state.last_command_id:
        ack_command_id = instance_state.last_command_id

    relative_spread = None
    if spread_state.record is not None:
        relative_spread = spread_state.record.relative_spread

    monitoring = load_instance_metrics(paths, instance)

    return InstanceDashboardView(
        instance=instance,
        last_decision=decision_entry.decision if decision_entry is not None else instance_state.last_decision,
        last_reason=decision_entry.reason if decision_entry is not None else instance_state.last_reason,
        risk_result=decision_entry.risk_result if decision_entry is not None else None,
        risk_reason=decision_entry.risk_reason if decision_entry is not None else None,
        relative_spread=relative_spread,
        open_ticket=instance_state.open_ticket,
        position_side=instance_state.position_side,
        position_volume=instance_state.position_volume,
        last_ack_status=ack_status,
        last_ack_command_id=ack_command_id,
        last_error_message=error_entry.message if error_entry is not None else None,
        last_error_type=error_entry.error_type if error_entry is not None else None,
        instance_health=monitoring.instance_health if monitoring is not None else None,
        cycle_latency_ms=monitoring.cycle_latency_ms if monitoring is not None else None,
        ack_latency_ms=monitoring.ack_latency_ms if monitoring is not None else None,
        data_freshness_ms=monitoring.data_freshness_ms if monitoring is not None else None,
        error_count=monitoring.error_count if monitoring is not None else None,
        error_rate_per_min=monitoring.error_rate_per_min if monitoring is not None else None,
    )


def load_dashboard_snapshot(
    config: SystemConfig,
    paths: SystemPaths,
    *,
    timestamp_utc: str | None = None,
) -> DashboardSnapshot:
    instances = discover_instances(config, paths)
    views = tuple(read_instance_dashboard_view(paths, instance) for instance in instances)
    return DashboardSnapshot(
        generated_at_utc=timestamp_utc or now_utc(),
        instances=views,
        monitoring_lines=read_monitoring_log_lines(paths),
    )


def read_system_log_tail(paths: SystemPaths, *, max_lines: int = 5) -> tuple[str, ...]:
    if max_lines <= 0:
        return ()

    log_dir = paths.logs_dir
    if not log_dir.is_dir():
        return ()

    log_files = sorted(
        (entry for entry in log_dir.iterdir() if entry.is_file() and entry.suffix == ".log"),
        key=lambda entry: entry.stat().st_mtime,
        reverse=True,
    )
    if not log_files:
        return ()

    lines = atomic_read_text(log_files[0]).splitlines()
    return tuple(line for line in lines[-max_lines:] if line.strip())


def read_monitoring_log_lines(paths: SystemPaths, *, max_lines: int = 10) -> tuple[str, ...]:
    lines = read_system_log_tail(paths, max_lines=max_lines * 3)
    monitoring_lines = [
        line
        for line in lines
        if " metrics " in line or " alert code=" in line or "runtime monitoring summary" in line
    ]
    return tuple(monitoring_lines[-max_lines:])
