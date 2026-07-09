from __future__ import annotations
import sys
import time
from dataclasses import dataclass, field
from engine.core.instance import Instance
from engine.core.lifecycle import LiveRuntime
from engine.core.logging_setup import log_event
from engine.protocol.constants import LogLevel
MODULE_NAME = 'core.performance'

@dataclass(frozen=True)
class CycleTimingSnapshot:
    cycle_duration_ms: int
    load_duration_ms: int
    analysis_duration_ms: int
    decision_duration_ms: int
    io_wait_ms: int

@dataclass(frozen=True)
class InstancePerformanceMetrics:
    instance: Instance
    cycle_duration_ms: int
    load_duration_ms: int
    analysis_duration_ms: int
    decision_duration_ms: int
    io_wait_ms: int
    memory_rss_mb: float | None

@dataclass
class PerformanceState:
    last_logged_monotonic: float = 0.0
    pending_metrics: list[InstancePerformanceMetrics] = field(default_factory=list)

def performance_affects_decisions() -> bool:
    return False

def monotonic_elapsed_ms(started_monotonic: float, ended_monotonic: float | None=None) -> int:
    end = ended_monotonic if ended_monotonic is not None else time.monotonic()
    return max(0, int((end - started_monotonic) * 1000))

def read_memory_rss_mb() -> float | None:
    try:
        import resource
        usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if sys.platform == 'darwin':
            return float(usage) / (1024 * 1024)
        return float(usage) / 1024.0
    except (ImportError, OSError):
        pass
    try:
        import psutil
        return psutil.Process().memory_info().rss / (1024 * 1024)
    except (ImportError, OSError):
        return None

def build_instance_performance_metrics(instance: Instance, timings: CycleTimingSnapshot, *, memory_rss_mb: float | None=None) -> InstancePerformanceMetrics:
    resolved_memory = read_memory_rss_mb() if memory_rss_mb is None else memory_rss_mb
    return InstancePerformanceMetrics(instance=instance, cycle_duration_ms=timings.cycle_duration_ms, load_duration_ms=timings.load_duration_ms, analysis_duration_ms=timings.analysis_duration_ms, decision_duration_ms=timings.decision_duration_ms, io_wait_ms=timings.io_wait_ms, memory_rss_mb=resolved_memory)

def format_performance_message(metrics: InstancePerformanceMetrics) -> str:
    instance = metrics.instance
    memory_rss = f'{metrics.memory_rss_mb:.2f}' if metrics.memory_rss_mb is not None else 'n/a'
    return f'performance account={instance.account_id} symbol={instance.symbol} magic={instance.magic} cycle_duration_ms={metrics.cycle_duration_ms} load_duration_ms={metrics.load_duration_ms} analysis_duration_ms={metrics.analysis_duration_ms} decision_duration_ms={metrics.decision_duration_ms} io_wait_ms={metrics.io_wait_ms} memory_rss_mb={memory_rss}'

def log_instance_performance(logger, metrics: InstancePerformanceMetrics) -> None:
    instance = metrics.instance
    log_event(logger, level=LogLevel.INFO.value, module=MODULE_NAME, message=format_performance_message(metrics), account_id=instance.account_id, symbol=instance.symbol, magic=instance.magic)

def record_instance_performance(state: PerformanceState, metrics: InstancePerformanceMetrics) -> PerformanceState:
    state.pending_metrics.append(metrics)
    return state

def should_emit_performance_log(state: PerformanceState, *, metrics_interval_ms: int, current_monotonic: float) -> bool:
    if metrics_interval_ms <= 0:
        return True
    if state.last_logged_monotonic <= 0:
        return True
    elapsed_ms = monotonic_elapsed_ms(state.last_logged_monotonic, current_monotonic)
    return elapsed_ms >= metrics_interval_ms

def flush_runtime_performance(runtime: LiveRuntime, state: PerformanceState, *, current_monotonic: float | None=None, force: bool=False) -> PerformanceState:
    resolved_monotonic = current_monotonic if current_monotonic is not None else time.monotonic()
    if not state.pending_metrics:
        return state
    if not force and (not should_emit_performance_log(state, metrics_interval_ms=runtime.config.runtime.metrics_interval_ms, current_monotonic=resolved_monotonic)):
        return state
    for metrics in state.pending_metrics:
        log_instance_performance(runtime.system_logger, metrics)
    state.pending_metrics.clear()
    state.last_logged_monotonic = resolved_monotonic
    return state

def observe_instance_performance(runtime: LiveRuntime, instance: Instance, timings: CycleTimingSnapshot, *, state: PerformanceState | None=None, memory_rss_mb: float | None=None) -> tuple[InstancePerformanceMetrics, PerformanceState]:
    performance_state = state or PerformanceState()
    metrics = build_instance_performance_metrics(instance, timings, memory_rss_mb=memory_rss_mb)
    record_instance_performance(performance_state, metrics)
    return (metrics, performance_state)
