from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Iterable, MutableMapping
from engine.core.atomic_io import atomic_read_text
from engine.core.cache import invalidate_startup_cache
from engine.core.clock import now_utc
from engine.core.history import archive_processed_ack, archive_processed_control
from engine.core.instance import Instance
from engine.core.lifecycle import LiveRuntime, spread_snapshot_from_record
from engine.core.paths import SystemPaths
from engine.core.logging_setup import log_event
from engine.core.timeout import log_ack_timeout
from engine.execution.ack_reader import build_ack_path, interpret_ack, read_ack_for_command
from engine.execution.command import OrderCommand
from engine.execution.control_writer import build_control_path
from engine.loader.market_loader import load_market_data
from engine.loader.sensor_loader import load_sensor_data
from engine.loader.status_loader import load_status_data
from engine.normalizer.market_normalizer import normalize_market_csv
from engine.normalizer.spread_model import SpreadModelSnapshot, update_spread_model_from_sensor
from engine.protocol.constants import AckStatus, OrderAction, ValidationStatus
from engine.protocol.errors import SystemError
from engine.protocol.models import ControlCommand, StatusRecord
from engine.protocol.parser import parse_control, parse_sensor_csv
from engine.core.position_sync import reconcile_position_with_status
from engine.state.instance_state import InstanceState
from engine.state.spread_state import SpreadState
from engine.validator.market_validator import validate_market_csv
from engine.validator.sensor_validator import validate_sensor_csv
from engine.validator.status_validator import validate_status_json
MODULE_NAME = 'core.recovery'
TERMINAL_ACK_STATUSES = frozenset({AckStatus.SUCCESS.value, AckStatus.FAILED.value, AckStatus.REJECTED.value, AckStatus.TIMEOUT.value})

@dataclass(frozen=True)
class UnconfirmedControlInfo:
    control: ControlCommand
    pending_ack: bool

@dataclass(frozen=True)
class AckRecoveryResult:
    recovered: bool
    timed_out: bool
    command_id: str | None = None

@dataclass(frozen=True)
class InstanceRecoveryResult:
    instance: Instance
    state_reloaded: bool
    ack_recovery: AckRecoveryResult
    position_synced: bool
    spread_recovered: bool
    cache_reconciled: bool
    unconfirmed_control: UnconfirmedControlInfo | None = None

@dataclass(frozen=True)
class RuntimeRecoveryResult:
    instance_results: tuple[InstanceRecoveryResult, ...]

    @property
    def instance_count(self) -> int:
        return len(self.instance_results)

def is_terminal_ack_status(status: str) -> bool:
    return status in TERMINAL_ACK_STATUSES

def order_command_from_control(control: ControlCommand) -> OrderCommand:
    return OrderCommand(command_id=control.command_id, action=control.action, reason=control.reason, decision_id=control.decision_id, side=control.side, volume=control.volume, stop_loss=control.stop_loss, take_profit=control.take_profit, ticket=control.ticket)

def read_control_command_if_exists(paths: SystemPaths, instance: Instance) -> ControlCommand | None:
    control_path = build_control_path(paths, instance)
    if not control_path.exists():
        return None
    return parse_control(atomic_read_text(control_path))

def reload_instance_state_from_disk(runtime: LiveRuntime, instance: Instance) -> bool:
    item = runtime.memory.get_or_create(instance)
    loaded_state = InstanceState.load(runtime.paths, instance)
    loaded_spread = SpreadState.load(runtime.paths, instance)
    item.instance_state = loaded_state
    item.spread_state = loaded_spread
    if loaded_spread.record is not None:
        runtime.spread_models[instance.instance_key] = spread_snapshot_from_record(loaded_spread.record)
    elif instance.instance_key in runtime.spread_models:
        runtime.spread_models.pop(instance.instance_key, None)
    return True

def sync_instance_state(runtime: LiveRuntime, instance: Instance) -> bool:
    item = runtime.memory.get_or_create(instance)
    item.instance_state = InstanceState.load(runtime.paths, instance)
    return True

def resolve_recovery_entry_price_for_open(runtime: LiveRuntime, instance: Instance) -> float | None:
    try:
        market_raw = load_market_data(runtime.paths, instance)
    except SystemError:
        return None
    validation = validate_market_csv(market_raw.raw_text)
    if not validation.is_valid:
        return None
    market_bars = normalize_market_csv(market_raw.raw_text)
    if not market_bars:
        return None
    return market_bars[-1].close

def detect_unconfirmed_control(paths: SystemPaths, instance: Instance, instance_state: InstanceState) -> UnconfirmedControlInfo | None:
    control = read_control_command_if_exists(paths, instance)
    if control is None:
        return None
    if control.instance_key.as_tuple() != instance.instance_key:
        return None
    if instance_state.last_command_id == control.command_id and is_terminal_ack_status(instance_state.last_ack_status):
        return None
    if control.action == OrderAction.NONE.value:
        return None
    return UnconfirmedControlInfo(control=control, pending_ack=True)

def is_control_republish_allowed(instance_state: InstanceState, unconfirmed: UnconfirmedControlInfo | None, *, proposed_command_id: str, proposed_action: str | None=None) -> bool:
    if unconfirmed is None:
        return True
    if unconfirmed.control.command_id == proposed_command_id:
        return False
    # Protective trailing/close must not wait behind a stuck OPEN control file.
    if proposed_action in {OrderAction.MODIFY.value, OrderAction.CLOSE.value} and unconfirmed.control.action == OrderAction.OPEN.value:
        return True
    if instance_state.last_command_id != unconfirmed.control.command_id:
        return True
    return is_terminal_ack_status(instance_state.last_ack_status)

def recover_pending_ack(runtime: LiveRuntime, instance: Instance, *, unconfirmed: UnconfirmedControlInfo | None=None, timestamp_utc: str | None=None) -> AckRecoveryResult:
    item = runtime.memory.get_or_create(instance)
    instance_state = item.instance_state
    resolved_unconfirmed = unconfirmed or detect_unconfirmed_control(runtime.paths, instance, instance_state)
    if resolved_unconfirmed is None:
        return AckRecoveryResult(recovered=False, timed_out=False)
    command_id = resolved_unconfirmed.control.command_id
    ack_path = build_ack_path(runtime.paths, instance)
    if ack_path.exists():
        try:
            ack_record = read_ack_for_command(runtime.paths, instance, expected_command_id=command_id)
        except SystemError:
            ack_record = None
        else:
            from engine.execution.engine import apply_ack_to_instance_state, log_ack_failure
            order_command = order_command_from_control(resolved_unconfirmed.control)
            entry_price = None
            if order_command.action == OrderAction.OPEN.value:
                entry_price = resolve_recovery_entry_price_for_open(runtime, instance)
            log_ack_failure(runtime.paths, instance, ack_record)
            apply_ack_to_instance_state(
                instance_state,
                order_command,
                ack_record,
                entry_price=entry_price,
                trailing_step_pips=runtime.config.trade_management.trailing_step_pips,
            )
            interpret_ack(ack_record)
            archive_processed_control(runtime.paths, instance)
            archive_processed_ack(runtime.paths, instance)
            return AckRecoveryResult(recovered=True, timed_out=False, command_id=command_id)
    if instance_state.last_command_id == command_id and instance_state.last_ack_status == AckStatus.TIMEOUT.value:
        archive_processed_control(runtime.paths, instance)
        archive_processed_ack(runtime.paths, instance)
        return AckRecoveryResult(recovered=False, timed_out=False, command_id=command_id)
    resolved_timestamp = timestamp_utc or now_utc()
    log_ack_timeout(runtime.paths, instance, command_id=command_id)
    instance_state.update_execution(command_id=command_id, ack_status=AckStatus.TIMEOUT.value)
    archive_processed_control(runtime.paths, instance)
    archive_processed_ack(runtime.paths, instance)
    return AckRecoveryResult(recovered=True, timed_out=True, command_id=command_id)

def load_status_for_recovery(runtime: LiveRuntime, instance: Instance) -> StatusRecord | None:
    try:
        status_raw = load_status_data(runtime.paths, instance.account_id)
    except SystemError:
        return None
    validation = validate_status_json(status_raw.raw_text)
    if not validation.is_valid or validation.record is None:
        return None
    return validation.record

def sync_position_with_status(instance_state: InstanceState, status: StatusRecord, instance: Instance, *, paths: SystemPaths | None=None, timestamp_utc: str | None=None) -> bool:
    if paths is not None and timestamp_utc is not None:
        return reconcile_position_with_status(paths, instance, instance_state, status, timestamp_utc=timestamp_utc).changed
    changed = False
    if status.balance > 0 and instance_state.day_start_balance is None:
        instance_state.update_risk_metrics(day_start_balance=status.balance)
        changed = True
    if status.equity > 0 and (instance_state.peak_equity is None or status.equity > instance_state.peak_equity):
        instance_state.update_risk_metrics(peak_equity=status.equity)
        changed = True
    return changed

def recover_spread_model_from_sensor(runtime: LiveRuntime, instance: Instance, *, timestamp_utc: str | None=None, cache: MutableMapping[str, Any] | None=None) -> SpreadModelSnapshot | None:
    try:
        sensor_raw = load_sensor_data(runtime.paths, instance, cache=cache)
    except SystemError:
        return None
    validation = validate_sensor_csv(sensor_raw.raw_text)
    if validation.status != ValidationStatus.VALID.value:
        return None
    readings = parse_sensor_csv(sensor_raw.raw_text)
    if not readings:
        return None
    history: list[float] = []
    snapshot: SpreadModelSnapshot | None = None
    for reading in readings:
        snapshot = update_spread_model_from_sensor(history, reading, lookback_bars=runtime.config.analysis.lookback_bars)
        history = list(snapshot.history)
    if snapshot is None:
        return None
    resolved_timestamp = timestamp_utc or now_utc()
    item = runtime.memory.get_or_create(instance)
    item.spread_state.update_from_snapshot(snapshot, resolved_timestamp)
    runtime.spread_models[instance.instance_key] = snapshot
    return snapshot

def reconcile_instance_cache(runtime: LiveRuntime, instance: Instance) -> bool:
    cache_dir = runtime.paths.instance_cache_dir(instance.account_id, instance.symbol, instance.magic)
    removed = invalidate_startup_cache(cache_dir)
    return removed > 0

def recover_instance(runtime: LiveRuntime, instance: Instance, *, timestamp_utc: str | None=None, cache: MutableMapping[str, Any] | None=None) -> InstanceRecoveryResult:
    resolved_timestamp = timestamp_utc or now_utc()
    state_reloaded = reload_instance_state_from_disk(runtime, instance)
    cache_reconciled = reconcile_instance_cache(runtime, instance)
    item = runtime.memory.get_or_create(instance)
    unconfirmed = detect_unconfirmed_control(runtime.paths, instance, item.instance_state)
    ack_recovery = recover_pending_ack(runtime, instance, unconfirmed=unconfirmed, timestamp_utc=timestamp_utc)
    status = load_status_for_recovery(runtime, instance)
    position_synced = False
    if status is not None:
        position_synced = sync_position_with_status(item.instance_state, status, instance, paths=runtime.paths, timestamp_utc=resolved_timestamp)
    spread_recovered = recover_spread_model_from_sensor(runtime, instance, timestamp_utc=timestamp_utc, cache=cache) is not None
    item.instance_state.save(runtime.paths)
    if item.spread_state.record is not None:
        item.spread_state.save(runtime.paths)
    return InstanceRecoveryResult(instance=instance, state_reloaded=state_reloaded, ack_recovery=ack_recovery, position_synced=position_synced, spread_recovered=spread_recovered, cache_reconciled=cache_reconciled, unconfirmed_control=unconfirmed)

def run_runtime_recovery(runtime: LiveRuntime, *, instances: Iterable[Instance] | None=None, timestamp_utc: str | None=None, cache: MutableMapping[str, Any] | None=None) -> RuntimeRecoveryResult:
    if instances is None:
        target_instances = tuple((item.instance for item in runtime.memory.items().values()))
    else:
        target_instances = tuple(instances)
    resolved_timestamp = timestamp_utc or now_utc()
    log_event(runtime.system_logger, level='INFO', module=MODULE_NAME, message=f'runtime recovery begin instances={len(target_instances)}')
    shared_cache: dict[str, Any] = {} if cache is None else cache
    results = [recover_instance(runtime, instance, timestamp_utc=resolved_timestamp, cache=shared_cache) for instance in target_instances]
    log_event(runtime.system_logger, level='INFO', module=MODULE_NAME, message=f'runtime recovery end instances={len(results)}')
    return RuntimeRecoveryResult(instance_results=tuple(results))
