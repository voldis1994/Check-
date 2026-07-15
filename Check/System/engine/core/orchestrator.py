from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Iterable, MutableMapping
from engine.core.clock import now_utc
from engine.core.cycle import InstanceCycleResult, run_instance_cycle
from engine.core.instance import Instance
from engine.core.lifecycle import LiveRuntime, discover_instances, load_runtime_memory, log_runtime_event, register_account_loggers, spread_snapshot_from_record
from engine.core.logging_setup import log_event
from engine.core.history import archive_market_snapshot
from engine.core.monitoring import MonitoringState, log_runtime_monitoring_summary, observe_instance_cycle
from engine.core.performance import PerformanceState, flush_runtime_performance, observe_instance_performance
from engine.core.retry import RetryAlertContext, build_retry_policy
from engine.journal.error_journal import log_error
from engine.journal.rotation import rotate_account_journals
from engine.protocol.constants import ErrorType
from engine.state.instance_state import InstanceState
from engine.state.spread_state import SpreadState
MODULE_NAME = 'core.orchestrator'

@dataclass(frozen=True)
class OrchestratorCycleResult:
    instance_results: tuple[InstanceCycleResult, ...]
    completed_count: int
    failed_count: int

    @property
    def instance_count(self) -> int:
        return len(self.instance_results)

def resolve_runtime_instances(runtime: LiveRuntime) -> tuple[Instance, ...]:
    return discover_instances(runtime.config, runtime.paths)

def group_instances_by_account(instances: Iterable[Instance]) -> dict[str, tuple[Instance, ...]]:
    grouped: dict[str, list[Instance]] = defaultdict(list)
    for instance in instances:
        grouped[instance.account_id].append(instance)
    return {account_id: tuple(sorted(account_instances, key=lambda item: item.instance_key)) for account_id, account_instances in sorted(grouped.items())}

def register_runtime_instances(runtime: LiveRuntime, instances: Iterable[Instance]) -> tuple[Instance, ...]:
    registered: list[Instance] = []
    for instance in instances:
        item = runtime.memory.get(instance)
        if item is None:
            loaded = load_runtime_memory(runtime.paths, [instance], lookback_bars=runtime.config.analysis.lookback_bars)
            loaded_item = loaded.get(instance)
            item = runtime.memory.get_or_create(instance)
            if loaded_item is not None:
                item.instance_state = loaded_item.instance_state
                item.spread_state = loaded_item.spread_state
        if item.spread_state.record is not None:
            runtime.spread_models[instance.instance_key] = spread_snapshot_from_record(item.spread_state.record)
        registered.append(instance)
    register_account_loggers(runtime, registered)
    return tuple(registered)

def refresh_discovered_instances(runtime: LiveRuntime) -> tuple[Instance, ...]:
    instances = resolve_runtime_instances(runtime)
    return register_runtime_instances(runtime, instances)

def list_registered_instances(runtime: LiveRuntime) -> tuple[Instance, ...]:
    return tuple((item.instance for item in runtime.memory.items().values()))

def run_instance_cycle_isolated(runtime: LiveRuntime, instance: Instance, *, use_global_universe: bool | None=None, timestamp_utc: str | None=None, cache: MutableMapping[str, Any] | None=None) -> InstanceCycleResult:
    try:
        return run_instance_cycle(runtime, instance, use_global_universe=use_global_universe, timestamp_utc=timestamp_utc, cache=cache)
    except Exception as exc:
        resolved_timestamp = timestamp_utc or now_utc()
        log_error(runtime.paths, instance, module=MODULE_NAME, error_type=ErrorType.PROTOCOL.value, message='instance cycle failed with unexpected error', context={'error': str(exc)})
        return InstanceCycleResult(instance=instance, timestamp_utc=resolved_timestamp, completed=False, error_logged=True, skip_reason=f'unexpected_error:{exc}')

def run_runtime_cycles(runtime: LiveRuntime, *, instances: Iterable[Instance] | None=None, use_global_universe: bool | None=None, timestamp_utc: str | None=None, cache: MutableMapping[str, Any] | None=None) -> OrchestratorCycleResult:
    if runtime.shutdown_requested:
        return OrchestratorCycleResult(instance_results=(), completed_count=0, failed_count=0)
    if instances is None:
        target_instances = refresh_discovered_instances(runtime)
    else:
        target_instances = register_runtime_instances(runtime, instances)
    resolved_timestamp = timestamp_utc or now_utc()
    log_runtime_event(runtime, level='INFO', module=MODULE_NAME, message=f'runtime cycle begin instances={len(target_instances)}')
    results: list[InstanceCycleResult] = []
    shared_cache: dict[str, Any] = {} if cache is None else cache
    monitoring_state = MonitoringState()
    performance_state = PerformanceState()
    for instance in target_instances:
        if runtime.shutdown_requested:
            break
        result = run_instance_cycle_isolated(runtime, instance, use_global_universe=use_global_universe, timestamp_utc=resolved_timestamp, cache=shared_cache)
        monitoring_state = observe_instance_cycle(runtime, instance, result, cache=shared_cache, state=monitoring_state, measured_ack_latency_ms=result.ack_latency_ms)
        if result.performance_timings is not None:
            _, performance_state = observe_instance_performance(runtime, instance, result.performance_timings, state=performance_state)
        results.append(result)
    completed_count = sum((1 for result in results if result.completed))
    failed_count = len(results) - completed_count
    log_runtime_event(runtime, level='INFO', module=MODULE_NAME, message=f'runtime cycle end instances={len(results)} completed={completed_count} failed={failed_count}')
    log_runtime_monitoring_summary(runtime, instance_count=len(results), completed_count=completed_count, failed_count=failed_count, total_errors=sum(monitoring_state.error_counts.values()))
    flush_runtime_performance(runtime, performance_state)
    processed_accounts: set[str] = set()
    for instance in target_instances:
        try:
            archive_market_snapshot(runtime.paths, instance, current_utc=resolved_timestamp)
        except Exception as exc:
            log_error(runtime.paths, instance, module=MODULE_NAME, error_type=ErrorType.IO.value, message='market snapshot archive failed', context={'error': str(exc)})
        if instance.account_id in processed_accounts:
            continue
        try:
            rotate_account_journals(runtime.paths, instance.account_id, retention_days=runtime.config.journal.retention_days, current_utc=resolved_timestamp)
        except Exception as exc:
            log_error(runtime.paths, instance, module=MODULE_NAME, error_type=ErrorType.IO.value, message='journal rotation failed', context={'error': str(exc)})
        processed_accounts.add(instance.account_id)
    return OrchestratorCycleResult(instance_results=tuple(results), completed_count=completed_count, failed_count=failed_count)

def reload_instance_state(runtime: LiveRuntime, instance: Instance) -> None:
    item = runtime.memory.get_or_create(instance)
    item.instance_state = InstanceState.load(runtime.paths, instance)
    item.spread_state = SpreadState.load(runtime.paths, instance)
    if item.spread_state.record is not None:
        runtime.spread_models[instance.instance_key] = spread_snapshot_from_record(item.spread_state.record)
