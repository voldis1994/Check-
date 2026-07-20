from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from engine.core.atomic_io import atomic_write_json
from engine.core.instance import Instance
from engine.core.paths import SystemPaths
from engine.execution.order_comment import order_comment_matches_expected
from engine.journal.error_journal import log_error
from engine.journal.trade_journal import log_external_partial_position_close, log_external_position_close
from engine.loader.closed_trade_loader import find_closed_trade_for_ticket
from engine.protocol.constants import ErrorType, REASON_AMBIGUOUS_PENDING_EXECUTION, REASON_CLOSE_PENDING_RECONCILIATION, REASON_EXECUTION_OUTCOME_UNRESOLVED, REASON_EXTERNAL_POSITION_CLOSE
from engine.protocol.models import StatusPositionSnapshot, StatusRecord
from engine.reason import build_reason
from engine.state.instance_state import InstanceState
MODULE_NAME = 'core.position_sync'
# Allow broker clock skew / file lag vs pending_execution_since_utc.
PENDING_OPEN_TIME_TOLERANCE_MS = 5000
# After ACK timeout, if broker status stays flat this long, abandon pending OPEN
# so live entries are not blocked forever by a stuck pending_command_id.
PENDING_OPEN_FLAT_ABANDON_MS = 60000
VOLUME_MATCH_TOLERANCE = 1e-09

def _parse_utc_timestamp(value: str) -> datetime:
    normalized = value.replace('Z', '+00:00')
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)

def _pending_open_age_ms(instance_state: InstanceState, timestamp_utc: str) -> int | None:
    since = instance_state.pending_execution_since_utc
    if not isinstance(since, str) or not since.strip():
        return None
    try:
        age_seconds = (_parse_utc_timestamp(timestamp_utc) - _parse_utc_timestamp(since)).total_seconds()
    except ValueError:
        return None
    return int(age_seconds * 1000.0)

@dataclass(frozen=True)
class PositionSyncResult:
    changed: bool
    external_close: bool
    trade_journal_logged: bool = False
    external_partial_close: bool = False
    duplicate_anomaly: bool = False
    close_pending: bool = False
    close_reconciled: bool = False
    broker_execution_confirmed: bool = False
    ambiguous_pending: bool = False

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

def _volumes_match(left: float | None, right: float | None, *, tolerance: float=VOLUME_MATCH_TOLERANCE) -> bool:
    if left is None or right is None:
        return False
    return abs(left - right) <= tolerance

def _open_time_not_before_pending(*, open_time_utc: str | None, pending_since_utc: str | None, tolerance_ms: int=PENDING_OPEN_TIME_TOLERANCE_MS) -> bool:
    if pending_since_utc is None:
        return True
    if open_time_utc is None:
        return False
    try:
        open_dt = _parse_utc_timestamp(open_time_utc)
        pending_dt = _parse_utc_timestamp(pending_since_utc)
    except (TypeError, ValueError):
        return False
    delta_ms = (open_dt - pending_dt).total_seconds() * 1000.0
    return delta_ms >= -float(tolerance_ms)

def _status_matches_pending_open(instance_state: InstanceState, position: StatusPositionSnapshot, *, open_time_tolerance_ms: int=PENDING_OPEN_TIME_TOLERANCE_MS) -> bool:
    """Strict OPEN fill match after ACK timeout — never confirm on symbol/magic/side/volume alone."""
    if instance_state.pending_execution_command_id is None:
        return False
    if position.ticket is None or position.ticket <= 0:
        return False
    if instance_state.pending_symbol is not None and position.symbol != instance_state.pending_symbol:
        return False
    if instance_state.pending_magic_number is not None and position.magic != instance_state.pending_magic_number:
        return False
    if instance_state.pending_execution_side is None or position.side != instance_state.pending_execution_side:
        return False
    if not _volumes_match(instance_state.pending_execution_volume, position.volume):
        return False
    if not order_comment_matches_expected(
        order_comment=position.order_comment,
        expected_comment=instance_state.pending_execution_comment,
        command_id=instance_state.pending_execution_command_id,
    ):
        return False
    if not _open_time_not_before_pending(
        open_time_utc=position.open_time_utc,
        pending_since_utc=instance_state.pending_execution_since_utc,
        tolerance_ms=open_time_tolerance_ms,
    ):
        return False
    if position.ticket in instance_state.pending_preexisting_tickets:
        return False
    return True

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
    return changed

def _position_is_active_in_status(status: StatusRecord, instance: Instance, *, open_ticket: int) -> bool:
    position = find_status_position(status, instance, open_ticket=open_ticket)
    return position is not None and position.ticket == open_ticket

def _archive_money_trailing_state(paths: SystemPaths, instance: Instance, instance_state: InstanceState) -> None:
    snapshot = instance_state.money_trailing_snapshot()
    ticket = snapshot.get('ticket')
    if ticket is None and instance_state.open_ticket is None:
        return
    paths.ensure_instance_directories(instance.account_id, instance.symbol, instance.magic)
    archive_dir = paths.instance_history_dir(instance.account_id, instance.symbol, instance.magic)
    archive_path = archive_dir / f'money_trailing_{ticket}.json'
    atomic_write_json(archive_path, snapshot, pretty=True)


def _force_clear_broker_flat_position(
    paths: SystemPaths,
    instance: Instance,
    instance_state: InstanceState,
    *,
    timestamp_utc: str,
) -> None:
    """Broker status has no matching open position — clear ghost Python state.

    Prefer closed-trade reconciliation when available. If history is missing or
    mismatched, still clear so RISK_MAX_POSITIONS / close_pending cannot stick forever
    while MT4 Trade is empty.
    """
    ticket = instance_state.close_pending_ticket or instance_state.open_ticket
    side = instance_state.close_pending_side or instance_state.position_side
    volume = instance_state.close_pending_volume if instance_state.close_pending_volume is not None else instance_state.position_volume
    reason = build_reason(
        REASON_EXTERNAL_POSITION_CLOSE,
        'broker status flat; clearing local position state without confirmed closed-trade history',
        ticket=ticket if ticket is not None else 0,
        symbol=instance.symbol,
        magic=instance.magic,
        ghost_clear=True,
    )
    log_error(
        paths,
        instance,
        module=MODULE_NAME,
        error_type=ErrorType.PROTOCOL.value,
        message='ghost/local position cleared because broker status has no open position',
        context={'reason': reason, 'ticket': ticket, 'close_pending': instance_state.close_pending_reconciliation},
    )
    log_external_position_close(
        paths,
        instance,
        ticket=ticket if ticket is not None else 0,
        side=side,
        volume=volume,
        timestamp_utc=timestamp_utc,
        price=None,
        stop_loss=None,
        reason=reason,
    )
    _archive_money_trailing_state(paths, instance, instance_state)
    instance_state.clear_close_pending()
    instance_state.clear_position()
    instance_state.clear_pending_execution()


def _try_reconcile_closed_trade(paths: SystemPaths, instance: Instance, instance_state: InstanceState, *, timestamp_utc: str) -> bool:
    ticket = instance_state.close_pending_ticket
    if ticket is None:
        return False
    closed = find_closed_trade_for_ticket(paths, instance, ticket=ticket)
    if closed is None:
        return False
    if closed.symbol != instance.symbol or closed.magic != instance.magic or closed.ticket != ticket:
        log_error(
            paths,
            instance,
            module=MODULE_NAME,
            error_type=ErrorType.PROTOCOL.value,
            message='closed trade record identity mismatch; skipping reconciliation',
            context={
                'closed_symbol': closed.symbol,
                'expected_symbol': instance.symbol,
                'closed_magic': closed.magic,
                'expected_magic': instance.magic,
                'closed_ticket': closed.ticket,
                'expected_ticket': ticket,
            },
        )
        return False
    if closed.side is not None and instance_state.close_pending_side is not None and closed.side != instance_state.close_pending_side:
        log_error(
            paths,
            instance,
            module=MODULE_NAME,
            error_type=ErrorType.PROTOCOL.value,
            message='closed trade side mismatch; keeping close_pending_reconciliation',
            context={
                'closed_side': closed.side,
                'expected_side': instance_state.close_pending_side,
                'ticket': ticket,
                'reason': REASON_CLOSE_PENDING_RECONCILIATION,
            },
        )
        return False
    if closed.volume is not None and instance_state.close_pending_volume is not None and not _volumes_match(closed.volume, instance_state.close_pending_volume):
        log_error(
            paths,
            instance,
            module=MODULE_NAME,
            error_type=ErrorType.PROTOCOL.value,
            message='closed trade volume mismatch; keeping close_pending_reconciliation',
            context={
                'closed_volume': closed.volume,
                'expected_volume': instance_state.close_pending_volume,
                'ticket': ticket,
                'reason': REASON_CLOSE_PENDING_RECONCILIATION,
            },
        )
        return False
    side = closed.side if closed.side is not None else instance_state.close_pending_side
    volume = closed.volume if closed.volume is not None else instance_state.close_pending_volume
    reason = build_reason(
        REASON_EXTERNAL_POSITION_CLOSE,
        'position closed on MT4; reconciled from closed trade file',
        ticket=closed.ticket,
        profit=closed.profit,
        commission=closed.commission,
        swap=closed.swap,
        close_time_utc=closed.close_time_utc,
        close_reason=closed.close_reason or '',
        symbol=closed.symbol,
        magic=closed.magic,
        side=side or '',
        volume=volume if volume is not None else 0.0,
    )
    log_external_position_close(
        paths,
        instance,
        ticket=closed.ticket,
        side=side or instance_state.position_side,
        volume=volume,
        timestamp_utc=closed.close_time_utc or timestamp_utc,
        price=closed.close_price,
        stop_loss=None,
        reason=reason,
    )
    _archive_money_trailing_state(paths, instance, instance_state)
    instance_state.clear_close_pending()
    instance_state.clear_position()
    return True

def _mark_position_close_pending(instance_state: InstanceState, *, timestamp_utc: str) -> None:
    if instance_state.open_ticket is None:
        return
    instance_state.set_close_pending(ticket=instance_state.open_ticket, side=instance_state.position_side, volume=instance_state.position_volume, since_utc=timestamp_utc)

def _abandon_stale_flat_pending_open(
    paths: SystemPaths,
    instance: Instance,
    instance_state: InstanceState,
    *,
    timestamp_utc: str,
    age_ms: int,
) -> None:
    reason = build_reason(
        REASON_EXECUTION_OUTCOME_UNRESOLVED,
        'abandoning stale pending OPEN; broker status flat after grace period',
        pending_command_id=instance_state.pending_execution_command_id,
        pending_age_ms=age_ms,
        abandon_after_ms=PENDING_OPEN_FLAT_ABANDON_MS,
    )
    log_error(
        paths,
        instance,
        module=MODULE_NAME,
        error_type=ErrorType.EXECUTION.value,
        message='stale pending OPEN cleared because broker remained flat',
        context={
            'reason': reason,
            'pending_command_id': instance_state.pending_execution_command_id,
            'pending_age_ms': age_ms,
            'abandon_after_ms': PENDING_OPEN_FLAT_ABANDON_MS,
        },
    )
    instance_state.clear_pending_execution()

def _reconcile_pending_open(
    paths: SystemPaths,
    instance: Instance,
    instance_state: InstanceState,
    matches: tuple[StatusPositionSnapshot, ...],
    *,
    timestamp_utc: str,
    broker_connected: bool = True,
) -> tuple[bool, bool, bool]:
    """Returns (changed, broker_execution_confirmed, ambiguous_pending)."""
    candidates = tuple((position for position in matches if _status_matches_pending_open(instance_state, position)))
    if len(candidates) == 1:
        position = candidates[0]
        _apply_status_position_to_state(instance_state, position)
        instance_state.clear_pending_execution()
        return (True, True, False)
    if len(candidates) > 1:
        tickets = [position.ticket for position in candidates]
        instance_state.ambiguous_pending_execution = True
        reason = build_reason(
            REASON_AMBIGUOUS_PENDING_EXECUTION,
            'multiple status positions match pending OPEN; refusing auto-confirm',
            pending_command_id=instance_state.pending_execution_command_id,
            candidate_tickets=tickets,
            candidate_count=len(candidates),
        )
        log_error(
            paths,
            instance,
            module=MODULE_NAME,
            error_type=ErrorType.EXECUTION.value,
            message='ambiguous pending OPEN execution',
            context={'reason': reason, 'candidate_tickets': tickets, 'pending_command_id': instance_state.pending_execution_command_id},
        )
        return (True, False, True)
    # No safe match. If broker is connected and flat long enough, abandon stuck pending
    # so ENTRY is not blocked forever after ACK timeout with no fill.
    if not matches and broker_connected:
        age_ms = _pending_open_age_ms(instance_state, timestamp_utc)
        if age_ms is not None and age_ms >= PENDING_OPEN_FLAT_ABANDON_MS:
            _abandon_stale_flat_pending_open(paths, instance, instance_state, timestamp_utc=timestamp_utc, age_ms=age_ms)
            return (True, False, False)
    # Keep pending / unresolved. Do not adopt by symbol/magic/side/volume alone.
    if matches:
        reason = build_reason(
            REASON_EXECUTION_OUTCOME_UNRESOLVED,
            'status positions present but none match pending OPEN identity (comment/time/side/volume)',
            pending_command_id=instance_state.pending_execution_command_id,
            pending_comment=instance_state.pending_execution_comment or '',
            status_tickets=[position.ticket for position in matches],
            status_comments=[position.order_comment or '' for position in matches],
        )
        log_error(
            paths,
            instance,
            module=MODULE_NAME,
            error_type=ErrorType.EXECUTION.value,
            message='pending OPEN remains unresolved after status reconcile',
            context={'reason': reason, 'pending_command_id': instance_state.pending_execution_command_id},
        )
    return (False, False, False)

def reconcile_position_with_status(paths: SystemPaths, instance: Instance, instance_state: InstanceState, status: StatusRecord, *, timestamp_utc: str) -> PositionSyncResult:
    changed = False
    external_close = False
    trade_journal_logged = False
    duplicate_anomaly = False
    close_pending = False
    close_reconciled = False
    broker_execution_confirmed = False
    ambiguous_pending = False
    if status.balance > 0 and instance_state.day_start_balance is None:
        instance_state.update_risk_metrics(day_start_balance=status.balance)
        changed = True
    if status.equity > 0 and (instance_state.peak_equity is None or status.equity > instance_state.peak_equity):
        instance_state.update_risk_metrics(peak_equity=status.equity)
        changed = True
    matches = find_status_positions(status, instance)
    if len(matches) > 1 and instance_state.pending_execution_command_id is None:
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
        return PositionSyncResult(changed=changed, external_close=False, trade_journal_logged=False, duplicate_anomaly=True, close_pending=instance_state.close_pending_reconciliation, close_reconciled=close_reconciled, broker_execution_confirmed=broker_execution_confirmed, ambiguous_pending=ambiguous_pending)
    if instance_state.pending_execution_command_id is None:
        instance_state.duplicate_position_anomaly = False
    status_position = matches[0] if len(matches) == 1 else None

    if instance_state.close_pending_reconciliation:
        pending_ticket = instance_state.close_pending_ticket
        ticket_reappeared = status_position is not None and (
            (pending_ticket is not None and status_position.ticket == pending_ticket)
            or (instance_state.open_ticket is not None and status_position.ticket == instance_state.open_ticket)
        )
        if ticket_reappeared and status_position is not None:
            instance_state.clear_close_pending()
            changed = _apply_status_position_to_state(instance_state, status_position, preserve_bars=True) or changed
        elif _try_reconcile_closed_trade(paths, instance, instance_state, timestamp_utc=timestamp_utc):
            changed = True
            external_close = True
            trade_journal_logged = True
            close_reconciled = True
            return PositionSyncResult(changed=changed, external_close=external_close, trade_journal_logged=trade_journal_logged, duplicate_anomaly=False, close_pending=False, close_reconciled=True, broker_execution_confirmed=False, ambiguous_pending=False)
        elif status_position is None and len(matches) == 0:
            # Still broker-flat and no usable closed history: force-clear ghost state.
            _force_clear_broker_flat_position(paths, instance, instance_state, timestamp_utc=timestamp_utc)
            return PositionSyncResult(changed=True, external_close=True, trade_journal_logged=True, duplicate_anomaly=False, close_pending=False, close_reconciled=True, broker_execution_confirmed=False, ambiguous_pending=False)
        else:
            close_pending = True
            return PositionSyncResult(changed=changed, external_close=False, trade_journal_logged=False, duplicate_anomaly=False, close_pending=True, close_reconciled=False, broker_execution_confirmed=False, ambiguous_pending=False)

    if instance_state.open_ticket is not None:
        if status_position is None or status_position.ticket != instance_state.open_ticket:
            _mark_position_close_pending(instance_state, timestamp_utc=timestamp_utc)
            if _try_reconcile_closed_trade(paths, instance, instance_state, timestamp_utc=timestamp_utc):
                close_reconciled = True
                trade_journal_logged = True
                external_close = True
            elif status_position is None and len(matches) == 0:
                _force_clear_broker_flat_position(paths, instance, instance_state, timestamp_utc=timestamp_utc)
                close_reconciled = True
                trade_journal_logged = True
                external_close = True
                close_pending = False
            else:
                close_pending = True
                reason = build_reason(REASON_CLOSE_PENDING_RECONCILIATION, 'external close pending reconciliation; waiting for closed trade file', ticket=instance_state.close_pending_ticket)
                log_error(paths, instance, module=MODULE_NAME, error_type=ErrorType.PROTOCOL.value, message='position missing from status; close pending reconciliation', context={'reason': reason, 'ticket': instance_state.close_pending_ticket})
            changed = True
            external_close = True
        elif status_position.volume != instance_state.position_volume:
            if instance_state.position_volume is not None and status_position.volume < instance_state.position_volume:
                closed_volume = instance_state.position_volume - status_position.volume
                instance_state.reduce_position_volume(volume=closed_volume)
                log_external_partial_position_close(paths, instance, ticket=instance_state.open_ticket, side=instance_state.position_side, closed_volume=closed_volume, remaining_volume=status_position.volume, timestamp_utc=timestamp_utc)
                return PositionSyncResult(changed=True, external_close=False, trade_journal_logged=True, external_partial_close=True, duplicate_anomaly=False, close_pending=close_pending, close_reconciled=close_reconciled, broker_execution_confirmed=broker_execution_confirmed, ambiguous_pending=ambiguous_pending)
            changed = _apply_status_position_to_state(instance_state, status_position, preserve_bars=True) or changed
        else:
            # Same ticket still open: update levels only. Do NOT clear pending_execution here.
            changed = _apply_status_position_to_state(instance_state, status_position, preserve_bars=True) or changed
    elif instance_state.pending_execution_command_id is not None:
        pend_changed, broker_execution_confirmed, ambiguous_pending = _reconcile_pending_open(
            paths,
            instance,
            instance_state,
            matches,
            timestamp_utc=timestamp_utc,
            broker_connected=bool(status.connected),
        )
        changed = changed or pend_changed
    elif status_position is not None:
        changed = _apply_status_position_to_state(instance_state, status_position) or changed
    return PositionSyncResult(changed=changed, external_close=external_close, trade_journal_logged=trade_journal_logged, duplicate_anomaly=duplicate_anomaly, close_pending=close_pending, close_reconciled=close_reconciled, broker_execution_confirmed=broker_execution_confirmed, ambiguous_pending=ambiguous_pending)

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
            _mark_position_close_pending(instance_state, timestamp_utc=timestamp_utc or '')
            changed = True
    elif status_position is not None:
        changed = _apply_status_position_to_state(instance_state, status_position) or changed
    return changed
