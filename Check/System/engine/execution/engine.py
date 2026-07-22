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
from engine.protocol.models import AckRecord, RuntimeConfig, SignalQualityConfig, TradeJournalEntry
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

def is_valid_open_fill_ack(ack_record: AckRecord) -> bool:
    if ack_record.status != AckStatus.SUCCESS.value:
        return False
    if ack_record.ticket is None or ack_record.ticket <= 0:
        return False
    fill_price = ack_record.fill_price
    if fill_price is None or isinstance(fill_price, bool) or not isinstance(fill_price, (int, float)):
        return False
    side = ack_record.side
    if not isinstance(side, str) or side not in {Side.BUY.value, Side.SELL.value}:
        return False
    volume = ack_record.volume
    if volume is None or isinstance(volume, bool) or not isinstance(volume, (int, float)) or volume <= 0:
        return False
    return True

def apply_ack_to_instance_state(
    instance_state: InstanceState,
    order_command: OrderCommand,
    ack_record: AckRecord,
    *,
    entry_price: float | None = None,
    reference_take_profit: float | None = None,
    position_last_bar_utc: str | None = None,
    trailing_step_pips: float | None = None,
) -> None:
    instance_state.update_execution(command_id=ack_record.command_id, ack_status=ack_record.status)
    if order_command.action == OrderAction.OPEN.value:
        if is_valid_open_fill_ack(ack_record):
            instance_state.clear_pending_execution()
            ack_side = ack_record.side
            ack_volume = ack_record.volume
            ack_fill = ack_record.fill_price
            ack_open_time = ack_record.open_time_utc
            side = ack_side if isinstance(ack_side, str) else order_command.side
            volume = float(ack_volume) if isinstance(ack_volume, (int, float)) and not isinstance(ack_volume, bool) else order_command.volume
            fill_price = float(ack_fill) if isinstance(ack_fill, (int, float)) and not isinstance(ack_fill, bool) else entry_price
            open_time_utc = ack_open_time if isinstance(ack_open_time, str) else None
            if side is not None and volume is not None:
                instance_state.update_position(open_ticket=ack_record.ticket, position_side=side, position_volume=volume, fill_price=fill_price, entry_price=entry_price, stop_loss=order_command.stop_loss, take_profit=order_command.take_profit, open_time_utc=open_time_utc, position_last_bar_utc=position_last_bar_utc)
                if reference_take_profit is not None and reference_take_profit > 0:
                    instance_state.position_reference_take_profit = reference_take_profit
        elif ack_record.status in {AckStatus.FAILED.value, AckStatus.REJECTED.value}:
            instance_state.clear_pending_execution()
        # ALREADY_PROCESSED or SUCCESS with invalid/zero fill: keep pending
    elif order_command.action == OrderAction.CLOSE.value:
        instance_state.clear_pending_execution()
        if ack_record.status == AckStatus.SUCCESS.value:
            if order_command.volume is not None and instance_state.position_volume is not None and (order_command.volume < instance_state.position_volume):
                instance_state.reduce_position_volume(volume=order_command.volume)
            else:
                instance_state.clear_position()
    elif order_command.action == OrderAction.MODIFY.value:
        # Never clear a pending OPEN identity just because trailing MODIFY acked.
        from engine.risk.money_step_trailing import (
            MoneyStepTrailingState,
            REASON_TRAILING_ACK_SL_MISMATCH,
            confirm_protective_sl,
            mark_protective_ack_sl_mismatch,
            mark_protective_modify_rejected,
        )

        def _as_optional_float(value: object) -> float | None:
            if value is None or isinstance(value, bool):
                return None
            if isinstance(value, (int, float)):
                return float(value)
            return None

        def _money_state_from_instance(*, pending_fallback: float | None) -> MoneyStepTrailingState:
            return MoneyStepTrailingState(
                peak_net_profit_money=instance_state.peak_net_profit_money,
                money_trailing_step_index=instance_state.money_trailing_step_index,
                locked_profit_money=instance_state.locked_profit_money,
                last_money_trailing_sl=instance_state.last_money_trailing_sl,
                be_plus_confirmed=instance_state.be_plus_confirmed,
                confirmed_protective_sl=instance_state.confirmed_protective_sl,
                pending_protective_sl=instance_state.pending_protective_sl if instance_state.pending_protective_sl is not None else pending_fallback,
                pending_trailing_reason=instance_state.pending_trailing_reason,
                pip_trail_confirmed_steps=instance_state.pip_trail_confirmed_steps,
                computed_be_plus_sl=instance_state.computed_be_plus_sl,
                next_pip_trail_sl=instance_state.next_pip_trail_sl,
                last_trailing_modify_status=instance_state.last_trailing_modify_status,
                last_trailing_broker_error=instance_state.last_trailing_broker_error,
                trailing_reason_code=instance_state.trailing_reason_code,
            )

        if ack_record.status == AckStatus.SUCCESS.value:
            digits = instance_state.instrument_digits or 5
            point = instance_state.instrument_point or (10 ** (-digits))
            pip = instance_state.instrument_pip or (point * 10.0)
            price_tolerance = max(point, 10 ** (-digits), 1e-05)
            resolved_step = trailing_step_pips
            if resolved_step is None:
                resolved_step = instance_state.pending_trailing_step_pips
            if resolved_step is None:
                resolved_step = 0.0

            applied_sl = _as_optional_float(getattr(ack_record, 'applied_stop_loss', None))
            applied_tp = _as_optional_float(getattr(ack_record, 'applied_take_profit', None))
            pending_sl = instance_state.pending_protective_sl
            if pending_sl is None:
                pending_sl = _as_optional_float(order_command.stop_loss)

            identity_ok = (
                ack_record.command_id == order_command.command_id
                and (ack_record.action is None or ack_record.action == OrderAction.MODIFY.value)
                and ack_record.ticket is not None
                and order_command.ticket is not None
                and int(ack_record.ticket) == int(order_command.ticket)
                and instance_state.open_ticket is not None
                and int(ack_record.ticket) == int(instance_state.open_ticket)
                and ack_record.symbol == instance_state.instance.symbol
                and int(ack_record.magic) == int(instance_state.instance.magic)
                and applied_sl is not None
                and pending_sl is not None
                and abs(float(applied_sl) - float(pending_sl)) <= price_tolerance
            )

            if identity_ok and applied_sl is not None:
                stop_loss = applied_sl
                take_profit = applied_tp if applied_tp is not None else order_command.take_profit
                if take_profit is not None:
                    instance_state.update_position_levels(stop_loss=stop_loss, take_profit=take_profit)
                else:
                    instance_state.update_position_levels(stop_loss=stop_loss, take_profit=instance_state.position_take_profit or 0.0)
                money_state = _money_state_from_instance(pending_fallback=pending_sl)
                confirmed = confirm_protective_sl(
                    money_state,
                    broker_sl=float(applied_sl),
                    price_tolerance=price_tolerance,
                    trailing_step_pips=float(resolved_step),
                    pip=pip,
                    digits=digits,
                    side=instance_state.position_side or Side.BUY.value,
                )
                instance_state.apply_money_trailing_state(
                    peak_net_profit_money=confirmed.peak_net_profit_money,
                    money_trailing_step_index=confirmed.money_trailing_step_index,
                    locked_profit_money=confirmed.locked_profit_money,
                    last_money_trailing_sl=confirmed.last_money_trailing_sl,
                    ticket=instance_state.open_ticket,
                    be_plus_confirmed=confirmed.be_plus_confirmed,
                    confirmed_protective_sl=confirmed.confirmed_protective_sl,
                    pending_protective_sl=None,
                    pending_trailing_reason=None,
                    pip_trail_confirmed_steps=confirmed.pip_trail_confirmed_steps,
                    computed_be_plus_sl=confirmed.computed_be_plus_sl,
                    next_pip_trail_sl=confirmed.next_pip_trail_sl,
                    last_trailing_modify_status='SUCCESS',
                    last_trailing_broker_error=None,
                    trailing_reason_code=confirmed.trailing_reason_code,
                    pending_trailing_step_pips=None,
                    sync_pending=True,
                )
            else:
                money_state = _money_state_from_instance(pending_fallback=_as_optional_float(order_command.stop_loss))
                mismatched = mark_protective_ack_sl_mismatch(money_state, status=REASON_TRAILING_ACK_SL_MISMATCH)
                instance_state.apply_money_trailing_state(
                    peak_net_profit_money=mismatched.peak_net_profit_money,
                    money_trailing_step_index=mismatched.money_trailing_step_index,
                    locked_profit_money=mismatched.locked_profit_money,
                    last_money_trailing_sl=mismatched.last_money_trailing_sl,
                    ticket=instance_state.open_ticket,
                    be_plus_confirmed=mismatched.be_plus_confirmed,
                    confirmed_protective_sl=mismatched.confirmed_protective_sl,
                    pending_protective_sl=mismatched.pending_protective_sl,
                    pending_trailing_reason=mismatched.pending_trailing_reason,
                    pip_trail_confirmed_steps=mismatched.pip_trail_confirmed_steps,
                    computed_be_plus_sl=mismatched.computed_be_plus_sl,
                    next_pip_trail_sl=mismatched.next_pip_trail_sl,
                    last_trailing_modify_status=mismatched.last_trailing_modify_status,
                    last_trailing_broker_error=mismatched.last_trailing_broker_error,
                    trailing_reason_code=mismatched.trailing_reason_code,
                    sync_pending=True,
                )
        elif ack_record.status in {AckStatus.FAILED.value, AckStatus.REJECTED.value}:
            money_state = _money_state_from_instance(pending_fallback=_as_optional_float(order_command.stop_loss))
            broker_code = ack_record.broker_error_code if ack_record.broker_error_code is not None else ack_record.error_code
            rejected = mark_protective_modify_rejected(
                money_state,
                status=str(ack_record.status),
                error_code=str(broker_code) if broker_code is not None else None,
            )
            instance_state.apply_money_trailing_state(
                peak_net_profit_money=rejected.peak_net_profit_money,
                money_trailing_step_index=rejected.money_trailing_step_index,
                locked_profit_money=rejected.locked_profit_money,
                last_money_trailing_sl=rejected.last_money_trailing_sl,
                ticket=instance_state.open_ticket,
                be_plus_confirmed=rejected.be_plus_confirmed,
                confirmed_protective_sl=rejected.confirmed_protective_sl,
                pending_protective_sl=rejected.pending_protective_sl,
                pending_trailing_reason=rejected.pending_trailing_reason,
                pip_trail_confirmed_steps=rejected.pip_trail_confirmed_steps,
                computed_be_plus_sl=rejected.computed_be_plus_sl,
                next_pip_trail_sl=rejected.next_pip_trail_sl,
                last_trailing_modify_status=rejected.last_trailing_modify_status,
                last_trailing_broker_error=rejected.last_trailing_broker_error,
                trailing_reason_code=rejected.trailing_reason_code,
                sync_pending=True,
            )
    else:
        instance_state.clear_pending_execution()

def _is_full_close_ack(instance_state: InstanceState, order_command: OrderCommand, ack_record: AckRecord) -> bool:
    if order_command.action != OrderAction.CLOSE.value:
        return False
    if ack_record.status != AckStatus.SUCCESS.value:
        return False
    if order_command.volume is not None and instance_state.position_volume is not None and order_command.volume < instance_state.position_volume:
        return False
    return True

def _register_open_fingerprint(*, instance_state: InstanceState, decision_result: DecisionResult, signal_quality_config: SignalQualityConfig | None) -> None:
    if signal_quality_config is None:
        return
    quality = decision_result.signal_quality
    if quality is None or not quality.fingerprint:
        return
    instance_state.register_signal_fingerprint(quality.fingerprint, expiry_bars=signal_quality_config.duplicate_signal_expiry_bars)

def _register_close_cooldown(*, instance_state: InstanceState, signal_quality_config: SignalQualityConfig | None, close_bar_utc: str, close_time_utc: str, was_loss: bool=False) -> None:
    if signal_quality_config is None:
        return
    instance_state.register_trade_close(close_bar_utc=close_bar_utc or close_time_utc, close_time_utc=close_time_utc, was_loss=was_loss, cooldown_bars_after_trade=signal_quality_config.cooldown_bars_after_trade, cooldown_bars_after_loss=signal_quality_config.cooldown_bars_after_loss)
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

def run_execution_engine(*, paths: SystemPaths, instance: Instance, instance_state: InstanceState, decision_result: DecisionResult, risk_engine_result: RiskEngineResult, runtime: RuntimeConfig, management_result: TradeManagementResult | None=None, timestamp_utc: str | None=None, started_monotonic: float | None=None, monotonic_fn: Callable[[], float]=time.monotonic, sleep_fn: Callable[[float], None]=time.sleep, poll_interval_ms: int=50, retry_alert_context: RetryAlertContext | None=None, position_last_bar_utc: str | None=None, preexisting_tickets: tuple[int, ...]=(), signal_quality_config: SignalQualityConfig | None=None, trailing_step_pips: float | None=None) -> ExecutionResult:
    resolved_timestamp = timestamp_utc or now_utc()
    order_command = resolve_order_command(decision_result, risk_engine_result, management_result, ticket=instance_state.open_ticket, side=instance_state.position_side)
    if instance_state.last_command_id:
        validate_control_command_retry(previous_command_id=instance_state.last_command_id, command_id=order_command.command_id)
    retry_policy = build_retry_policy(runtime)
    from engine.core.recovery import detect_unconfirmed_control, is_control_republish_allowed
    unconfirmed = detect_unconfirmed_control(paths, instance, instance_state)
    if not is_control_republish_allowed(instance_state, unconfirmed, proposed_command_id=order_command.command_id, proposed_action=order_command.action):
        return ExecutionResult(order_command=order_command, control_published=False, trade_intent_logged=False, ack_interpretation=None, trade_journal_entry=None, state_updated=False)
    if not _requires_trade_execution(order_command):
        return ExecutionResult(order_command=order_command, control_published=False, trade_intent_logged=False, ack_interpretation=None, trade_journal_entry=None, state_updated=False)
    if order_command.action == OrderAction.OPEN.value:
        from engine.execution.order_comment import build_open_order_comment
        _pending_comment = order_command.order_comment or build_open_order_comment(order_command.command_id)
        instance_state.set_pending_execution(
            command_id=order_command.command_id,
            decision_id=order_command.decision_id,
            since_utc=resolved_timestamp,
            comment=_pending_comment,
            symbol=instance.symbol,
            magic=instance.magic,
            side=order_command.side,
            volume=order_command.volume,
            preexisting_tickets=preexisting_tickets,
        )
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
                preexisting_tickets=preexisting_tickets,
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
    if order_command.action == OrderAction.CLOSE.value and interpretation.is_success:
        from engine.core.position_sync import _archive_money_trailing_state
        _archive_money_trailing_state(paths, instance, instance_state)
    if _is_full_close_ack(instance_state, order_command, ack_record):
        _register_close_cooldown(instance_state=instance_state, signal_quality_config=signal_quality_config, close_bar_utc=position_last_bar_utc or resolved_timestamp, close_time_utc=resolved_timestamp, was_loss=False)
    apply_ack_to_instance_state(instance_state, order_command, ack_record, entry_price=resolved_entry_price, reference_take_profit=resolve_reference_take_profit_for_open(decision_result, order_command), position_last_bar_utc=position_last_bar_utc, trailing_step_pips=trailing_step_pips)
    if order_command.action == OrderAction.OPEN.value and is_valid_open_fill_ack(ack_record):
        _register_open_fingerprint(instance_state=instance_state, decision_result=decision_result, signal_quality_config=signal_quality_config)
    trade_entry = log_trade_ack(paths, instance, ack_record, timestamp_utc=resolved_timestamp, price=resolved_entry_price if order_command.action == OrderAction.OPEN.value else None)
    archive_processed_control(paths, instance)
    archive_processed_ack(paths, instance)
    return ExecutionResult(order_command=order_command, control_published=True, trade_intent_logged=True, ack_interpretation=interpretation, trade_journal_entry=trade_entry, state_updated=True)

def execution_engine_performs_analysis() -> bool:
    source = inspect.getsource(run_execution_engine)
    return 'engine.analysis' in source or 'run_analysis_engine' in source
