from __future__ import annotations
from dataclasses import dataclass
from engine.core.instance import Instance
from engine.core.paths import SystemPaths
from engine.journal.error_journal import log_error
from engine.journal.trade_journal import log_external_partial_position_close, log_external_position_close
from engine.protocol.constants import ErrorType, REASON_CLOSE_PENDING_RECONCILIATION
from engine.protocol.models import StatusPositionSnapshot, StatusRecord
from engine.reason import build_reason
from engine.state.instance_state import InstanceState
MODULE_NAME = 'core.position_sync'

@dataclass(frozen=True)
class PositionSyncResult:
    changed: bool
    external_close: bool
    trade_journal_logged: bool = False
    external_partial_close: bool = False
    duplicate_anomaly: bool = False

def find_status_positions(status: StatusRecord, instance: Instance) -> tuple[StatusPositionSnapshot, ...]:
    return tuple((position for position in status.open_positions if position.symbol == instance.symbol and position.magic == instance.magic))

def find_status_position(status: StatusRecord, instance: Instance, *, open_ticket: int | None=None) -> StatusPositionSnapshot | None:
    matches = find_status_positions(status, instance)
    if not matches:
        return None
    ticket = open_ticket
    if ticket is not None:
        for position in matches:
            if position.ticket == ticket:
                return position
    return matches[0]

def _price_tolerance(instance_state: InstanceState) -> float:
    digits = instance_state.instrument_digits
    point = instance_state.instrument_point
    digit_epsilon = 10 ** (-digits) if digits > 0 else 0.0
    candidates = [value for value in (point, digit_epsilon) if value > 0]
    return max(candidates) if candidates else 1e-05

def _prices_differ(left: float | None, right: float | None, *, tolerance: float) -> bool:
    if left is None and right is None:
        return False
    if left is None or right is None:
        return True
    return abs(left - right) > tolerance

def _apply_status_position_to_state(instance_state: InstanceState, position: StatusPositionSnapshot, *, preserve_bars: bool=False) -> bool:
    tolerance = _price_tolerance(instance_state)
    changed = False
    previous_bars = instance_state.position_bars_open
    previous_last_bar = instance_state.position_last_bar_utc
    previous_open_time = instance_state.position_open_time_utc
    if instance_state.open_ticket != position.ticket or instance_state.position_side != position.side or instance_state.position_volume != position.volume:
        instance_state.update_position(open_ticket=position.ticket, position_side=position.side, position_volume=position.volume, entry_price=position.entry_price, stop_loss=position.stop_loss, take_profit=position.take_profit, open_time_utc=position.open_time_utc or previous_open_time, position_last_bar_utc=previous_last_bar if preserve_bars else position.open_time_utc)
        if preserve_bars:
            instance_state.position_bars_open = previous_bars
            instance_state.position_last_bar_utc = previous_last_bar
        changed = True
    else:
        if _prices_differ(instance_state.position_entry_price, position.entry_price, tolerance=tolerance) and position.entry_price is not None:
            instance_state.position_entry_price = position.entry_price
            changed = True
        if position.stop_loss is not None and _prices_differ(instance_state.position_stop_loss, position.stop_loss, tolerance=tolerance):
            instance_state.position_stop_loss = position.stop_loss
            changed = True
        if position.take_profit is not None and _prices_differ(instance_state.position_take_profit, position.take_profit, tolerance=tolerance):
            instance_state.position_take_profit = position.take_profit
            changed = True
        if position.open_time_utc is not None and instance_state.position_open_time_utc != position.open_time_utc:
            instance_state.position_open_time_utc = position.open_time_utc
            changed = True
    if _prices_differ(instance_state.position_entry_price, position.entry_price, tolerance=tolerance) and position.entry_price is not None:
        instance_state.position_entry_price = position.entry_price
        changed = True
    return changed

def _position_is_active_in_status(status: StatusRecord, instance: Instance, *, open_ticket: int) -> bool:
    position = find_status_position(status, instance, open_ticket=open_ticket)
    return position is not None and position.ticket == open_ticket

def reconcile_position_with_status(paths: SystemPaths, instance: Instance, instance_state: InstanceState, status: StatusRecord, *, timestamp_utc: str) -> PositionSyncResult:
    changed = False
    external_close = False
    trade_journal_logged = False
    duplicate_anomaly = False
    if status.balance > 0 and instance_state.day_start_balance is None:
        instance_state.update_risk_metrics(day_start_balance=status.balance)
        changed = True
    if status.equity > 0 and (instance_state.peak_equity is None or status.equity > instance_state.peak_equity):
        instance_state.update_risk_metrics(peak_equity=status.equity)
        changed = True
    matches = find_status_positions(status, instance)
    if len(matches) > 1:
        instance_state.duplicate_position_anomaly = True
        duplicate_anomaly = True
        log_error(paths, instance, module=MODULE_NAME, error_type=ErrorType.PROTOCOL.value, message='duplicate magic positions detected in status', context={'match_count': len(matches), 'tickets': [position.ticket for position in matches], 'symbol': instance.symbol, 'magic': instance.magic})
        ticket_match = None
        if instance_state.open_ticket is not None:
            for position in matches:
                if position.ticket == instance_state.open_ticket:
                    ticket_match = position
                    break
        if ticket_match is not None:
            changed = _apply_status_position_to_state(instance_state, ticket_match, preserve_bars=True) or changed
        return PositionSyncResult(changed=changed, external_close=False, trade_journal_logged=False, duplicate_anomaly=True)
    instance_state.duplicate_position_anomaly = False
    status_position = matches[0] if matches else None
    if instance_state.open_ticket is not None:
        if status_position is None or status_position.ticket != instance_state.open_ticket:
            reason = build_reason(REASON_CLOSE_PENDING_RECONCILIATION, 'external close pending reconciliation; close history unavailable', ticket=instance_state.open_ticket)
            log_external_position_close(paths, instance, ticket=instance_state.open_ticket, side=instance_state.position_side, volume=instance_state.position_volume, timestamp_utc=timestamp_utc, price=None, stop_loss=instance_state.position_stop_loss, reason=reason)
            instance_state.clear_position()
            if instance_state.pending_execution_command_id is not None:
                instance_state.pending_execution_command_id = None
            changed = True
            external_close = True
            trade_journal_logged = True
        elif status_position.volume != instance_state.position_volume:
            if instance_state.position_volume is not None and status_position.volume < instance_state.position_volume:
                closed_volume = instance_state.position_volume - status_position.volume
                instance_state.reduce_position_volume(volume=closed_volume)
                log_external_partial_position_close(paths, instance, ticket=instance_state.open_ticket, side=instance_state.position_side, closed_volume=closed_volume, remaining_volume=status_position.volume, timestamp_utc=timestamp_utc)
                return PositionSyncResult(changed=True, external_close=False, trade_journal_logged=True, external_partial_close=True, duplicate_anomaly=False)
            changed = _apply_status_position_to_state(instance_state, status_position, preserve_bars=True) or changed
        else:
            changed = _apply_status_position_to_state(instance_state, status_position, preserve_bars=True) or changed
            if instance_state.pending_execution_command_id is not None:
                instance_state.pending_execution_command_id = None
                changed = True
    elif status_position is not None:
        changed = _apply_status_position_to_state(instance_state, status_position) or changed
        if instance_state.pending_execution_command_id is not None:
            instance_state.pending_execution_command_id = None
            changed = True
    return PositionSyncResult(changed=changed, external_close=external_close, trade_journal_logged=trade_journal_logged, duplicate_anomaly=duplicate_anomaly)

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
    matches = find_status_positions(status, instance)
    if len(matches) > 1:
        instance_state.duplicate_position_anomaly = True
        return changed
    instance_state.duplicate_position_anomaly = False
    status_position = matches[0] if matches else None
    if instance_state.open_ticket is not None:
        if not _position_is_active_in_status(status, instance, open_ticket=instance_state.open_ticket):
            instance_state.clear_position()
            changed = True
    elif status_position is not None:
        changed = _apply_status_position_to_state(instance_state, status_position) or changed
    return changed
