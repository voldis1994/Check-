from __future__ import annotations
import inspect
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING
from engine.core.clock import now_utc
from engine.core.instance import Instance
from engine.core.paths import SystemPaths
from engine.core.history import archive_processed_ack, archive_processed_control
from engine.core.retry import RetryAlertContext, RetryPolicy, build_retry_policy, validate_control_command_retry
from engine.core.timeout import build_ack_timeout_config, is_ack_timeout_elapsed, log_ack_timeout
from engine.execution.ack_reader import AckInterpretation, build_ack_path, build_ack_timeout_interpretation, interpret_ack, read_ack_for_command
from engine.execution.command import OrderCommand, resolve_order_command
from engine.execution.control_writer import publish_control
from engine.journal.error_journal import log_error
from engine.journal.trade_journal import TradeIntentParams, log_trade_ack, log_trade_ack_timeout, log_trade_intent
from engine.protocol.constants import AckStatus, ErrorType, OrderAction, Side
from engine.protocol.models import AckRecord, RuntimeConfig, TradeJournalEntry
from engine.state.instance_state import InstanceState
if TYPE_CHECKING:
    from engine.decision.engine import DecisionResult
    from engine.risk.engine import RiskEngineResult
    from engine.risk.trade_management import TradeManagementResult
MODULE_NAME = 'execution.engine'

@dataclass(frozen=True)
class ExecutionResult:
    order_command: OrderCommand
    control_published: bool
    trade_intent_logged: bool
    ack_interpretation: AckInterpretation | None
    trade_journal_entry: TradeJournalEntry | None
    state_updated: bool

def build_trade_intent_params(order_command: OrderCommand) -> TradeIntentParams:
    return TradeIntentParams(command_id=order_command.command_id, event=order_command.action, reason=order_command.reason, side=order_command.side, volume=order_command.volume, ticket=order_command.ticket, stop_loss=order_command.stop_loss)

def wait_for_ack(*, started_monotonic: float, ack_timeout_ms: int, ack_available: Callable[[], bool], monotonic_fn: Callable[[], float]=time.monotonic, sleep_fn: Callable[[float], None]=time.sleep, poll_interval_ms: int=50) -> bool:
    while not is_ack_timeout_elapsed(started_monotonic=started_monotonic, current_monotonic=monotonic_fn(), ack_timeout_ms=ack_timeout_ms):
        if ack_available():
            return True
        sleep_fn(poll_interval_ms / 1000.0)
    return ack_available()

def resolve_entry_price_for_open(decision_result: DecisionResult, order_command: OrderCommand) -> float | None:
    if order_command.action != OrderAction.OPEN.value:
        return None
    if order_command.side == Side.BUY.value and decision_result.buy_candidate.valid:
        return decision_result.buy_candidate.entry_price
    if order_command.side == Side.SELL.value and decision_result.sell_candidate.valid:
        return decision_result.sell_candidate.entry_price
    return None

def resolve_reference_take_profit_for_open(decision_result: DecisionResult, order_command: OrderCommand) -> float | None:
    if order_command.action != OrderAction.OPEN.value:
        return None
    if order_command.take_profit is not None and order_command.take_profit > 0:
        return None
    if order_command.side == Side.BUY.value and decision_result.buy_candidate.valid:
        return decision_result.buy_candidate.take_profit
    if order_command.side == Side.SELL.value and decision_result.sell_candidate.valid:
        return decision_result.sell_candidate.take_profit
    return None

def apply_ack_to_instance_state(instance_state: InstanceState, order_command: OrderCommand, ack_record: AckRecord, *, entry_price: float | None=None, reference_take_profit: float | None=None, position_last_bar_utc: str | None=None) -> None:
    instance_state.update_execution(command_id=ack_record.command_id, ack_status=ack_record.status)
    instance_state.clear_pending_execution()
    if ack_record.status != AckStatus.SUCCESS.value:
        return
    if order_command.action == OrderAction.OPEN.value and ack_record.ticket is not None:
        ack_side = getattr(ack_record, 'side', None)
        ack_volume = getattr(ack_record, 'volume', None)
        ack_fill = getattr(ack_record, 'fill_price', None)
        ack_open_time = getattr(ack_record, 'open_time_utc', None)
        side = ack_side if isinstance(ack_side, str) else order_command.side
        volume = float(ack_volume) if isinstance(ack_volume, (int, float)) and not isinstance(ack_volume, bool) else order_command.volume
        fill_price = float(ack_fill) if isinstance(ack_fill, (int, float)) and not isinstance(ack_fill, bool) else entry_price
        open_time_utc = ack_open_time if isinstance(ack_open_time, str) else None
        if side is not None and volume is not None:
            instance_state.update_position(open_ticket=ack_record.ticket, position_side=side, position_volume=volume, fill_price=fill_price, entry_price=entry_price, stop_loss=order_command.stop_loss, take_profit=order_command.take_profit, open_time_utc=open_time_utc, position_last_bar_utc=position_last_bar_utc)
            if reference_take_profit is not None and reference_take_profit > 0:
                instance_state.position_reference_take_profit = reference_take_profit
        return
    if order_command.action == OrderAction.MODIFY.value and order_command.stop_loss is not None and (order_command.take_profit is not None):
        instance_state.update_position_levels(stop_loss=order_command.stop_loss, take_profit=order_command.take_profit)
        return
    if order_command.action == OrderAction.CLOSE.value:
        if order_command.volume is not None and instance_state.position_volume is not None and (order_command.volume < instance_state.position_volume):
            instance_state.reduce_position_volume(volume=order_command.volume)
        else:
            instance_state.clear_position()

def log_ack_failure(paths: SystemPaths, instance: Instance, ack_record: AckRecord) -> None:
    if ack_record.status not in {AckStatus.FAILED.value, AckStatus.REJECTED.value}:
        return
    context: dict[str, object] = {'command_id': ack_record.command_id, 'status': ack_record.status}
    if ack_record.error_code is not None:
        context['error_code'] = ack_record.error_code
    if ack_record.error_message is not None:
        context['error_message'] = ack_record.error_message
    log_error(paths, instance, module=MODULE_NAME, error_type=ErrorType.EXECUTION.value, message=f'execution ack {ack_record.status.lower()}', context=context)

def _requires_trade_execution(order_command: OrderCommand) -> bool:
    return order_command.action in {OrderAction.OPEN.value, OrderAction.MODIFY.value, OrderAction.CLOSE.value}

def run_execution_engine(*, paths: SystemPaths, instance: Instance, instance_state: InstanceState, decision_result: DecisionResult, risk_engine_result: RiskEngineResult, runtime: RuntimeConfig, management_result: TradeManagementResult | None=None, timestamp_utc: str | None=None, started_monotonic: float | None=None, monotonic_fn: Callable[[], float]=time.monotonic, sleep_fn: Callable[[float], None]=time.sleep, poll_interval_ms: int=50, retry_alert_context: RetryAlertContext | None=None, position_last_bar_utc: str | None=None) -> ExecutionResult:
    resolved_timestamp = timestamp_utc or now_utc()
    order_command = resolve_order_command(decision_result, risk_engine_result, management_result, ticket=instance_state.open_ticket, side=instance_state.position_side)
    if instance_state.last_command_id:
        validate_control_command_retry(previous_command_id=instance_state.last_command_id, command_id=order_command.command_id)
    retry_policy = build_retry_policy(runtime)
    from engine.core.recovery import detect_unconfirmed_control, is_control_republish_allowed
    unconfirmed = detect_unconfirmed_control(paths, instance, instance_state)
    if not is_control_republish_allowed(instance_state, unconfirmed, proposed_command_id=order_command.command_id):
        return ExecutionResult(order_command=order_command, control_published=False, trade_intent_logged=False, ack_interpretation=None, trade_journal_entry=None, state_updated=False)
    if not _requires_trade_execution(order_command):
        return ExecutionResult(order_command=order_command, control_published=False, trade_intent_logged=False, ack_interpretation=None, trade_journal_entry=None, state_updated=False)
    publish_control(paths, instance, order_command, timestamp_utc=resolved_timestamp, retry_policy=retry_policy, retry_alert_context=retry_alert_context)
    log_trade_intent(paths, instance, build_trade_intent_params(order_command), timestamp_utc=resolved_timestamp)
    ack_timeout = build_ack_timeout_config(runtime)
    wait_started = started_monotonic if started_monotonic is not None else monotonic_fn()

    def _ack_available_for_command() -> bool:
        ack_path = build_ack_path(paths, instance)
        if not ack_path.exists():
            return False
        try:
            read_ack_for_command(paths, instance, expected_command_id=order_command.command_id, retry_policy=retry_policy, retry_alert_context=retry_alert_context)
        except SystemError:
            return False
        return True
    ack_ready = wait_for_ack(started_monotonic=wait_started, ack_timeout_ms=ack_timeout.ack_timeout_ms, ack_available=_ack_available_for_command, monotonic_fn=monotonic_fn, sleep_fn=sleep_fn, poll_interval_ms=poll_interval_ms)
    if not ack_ready:
        log_ack_timeout(paths, instance, command_id=order_command.command_id)
        instance_state.update_execution(command_id=order_command.command_id, ack_status=AckStatus.TIMEOUT.value)
        # OPEN ACK timeout: keep pending until status/history reconciles. Timeout alone must not clear it.
        # MODIFY/CLOSE timeouts do not set pending — same ticket still open is not proof of outcome.
        if order_command.action == OrderAction.OPEN.value:
            from engine.execution.order_comment import build_open_order_comment
            comment = order_command.order_comment or build_open_order_comment(order_command.command_id)
            instance_state.set_pending_execution(
                command_id=order_command.command_id,
                decision_id=order_command.decision_id,
                since_utc=resolved_timestamp,
                comment=comment,
                symbol=instance.symbol,
                magic=instance.magic,
                side=order_command.side,
                volume=order_command.volume,
                preexisting_tickets=(),
            )
        archive_processed_control(paths, instance)
        archive_processed_ack(paths, instance)
        trade_entry = log_trade_ack_timeout(paths, instance, command_id=order_command.command_id, timestamp_utc=resolved_timestamp)
        return ExecutionResult(order_command=order_command, control_published=True, trade_intent_logged=True, ack_interpretation=build_ack_timeout_interpretation(command_id=order_command.command_id), trade_journal_entry=trade_entry, state_updated=True)
    ack_record = read_ack_for_command(paths, instance, expected_command_id=order_command.command_id, retry_policy=retry_policy, retry_alert_context=retry_alert_context)
    interpretation = interpret_ack(ack_record)
    log_ack_failure(paths, instance, ack_record)
    candidate_entry_price = resolve_entry_price_for_open(decision_result, order_command)
    resolved_entry_price = ack_record.fill_price if ack_record.fill_price is not None else candidate_entry_price
    apply_ack_to_instance_state(instance_state, order_command, ack_record, entry_price=resolved_entry_price, reference_take_profit=resolve_reference_take_profit_for_open(decision_result, order_command), position_last_bar_utc=position_last_bar_utc)
    trade_entry = log_trade_ack(paths, instance, ack_record, timestamp_utc=resolved_timestamp, price=resolved_entry_price if order_command.action == OrderAction.OPEN.value else None)
    archive_processed_control(paths, instance)
    archive_processed_ack(paths, instance)
    return ExecutionResult(order_command=order_command, control_published=True, trade_intent_logged=True, ack_interpretation=interpretation, trade_journal_entry=trade_entry, state_updated=True)

def execution_engine_performs_analysis() -> bool:
    source = inspect.getsource(run_execution_engine)
    return 'engine.analysis' in source or 'run_analysis_engine' in source
