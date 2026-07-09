from __future__ import annotations
from dataclasses import dataclass
from engine.core.instance import Instance
from engine.core.paths import SystemPaths
from engine.journal.trade_journal import log_external_partial_position_close, log_external_position_close
from engine.protocol.models import StatusPositionSnapshot, StatusRecord
from engine.state.instance_state import InstanceState
MODULE_NAME = 'core.position_sync'

@dataclass(frozen=True)
class PositionSyncResult:
    changed: bool
    external_close: bool
    trade_journal_logged: bool = False
    external_partial_close: bool = False

def find_status_position(status: StatusRecord, instance: Instance) -> StatusPositionSnapshot | None:
    for position in status.open_positions:
        if position.symbol == instance.symbol and position.magic == instance.magic:
            return position
    return None

def _position_is_active_in_status(status: StatusRecord, instance: Instance, *, open_ticket: int) -> bool:
    position = find_status_position(status, instance)
    return position is not None and position.ticket == open_ticket

def _apply_status_position_to_state(instance_state: InstanceState, position: StatusPositionSnapshot) -> bool:
    if instance_state.open_ticket == position.ticket and instance_state.position_side == position.side and (instance_state.position_volume == position.volume):
        return False
    instance_state.update_position(open_ticket=position.ticket, position_side=position.side, position_volume=position.volume, entry_price=position.entry_price, stop_loss=position.stop_loss, take_profit=position.take_profit)
    return True

def reconcile_position_with_status(paths: SystemPaths, instance: Instance, instance_state: InstanceState, status: StatusRecord, *, timestamp_utc: str) -> PositionSyncResult:
    changed = False
    external_close = False
    trade_journal_logged = False
    if status.balance > 0 and instance_state.day_start_balance is None:
        instance_state.update_risk_metrics(day_start_balance=status.balance)
        changed = True
    if status.equity > 0 and (instance_state.peak_equity is None or status.equity > instance_state.peak_equity):
        instance_state.update_risk_metrics(peak_equity=status.equity)
        changed = True
    status_position = find_status_position(status, instance)
    if instance_state.open_ticket is not None:
        if status_position is None or status_position.ticket != instance_state.open_ticket:
            log_external_position_close(paths, instance, ticket=instance_state.open_ticket, side=instance_state.position_side, volume=instance_state.position_volume, timestamp_utc=timestamp_utc)
            instance_state.clear_position()
            changed = True
            external_close = True
            trade_journal_logged = True
        elif status_position.volume != instance_state.position_volume:
            if status_position.volume < instance_state.position_volume:
                closed_volume = instance_state.position_volume - status_position.volume
                instance_state.reduce_position_volume(volume=closed_volume)
                log_external_partial_position_close(paths, instance, ticket=instance_state.open_ticket, side=instance_state.position_side, closed_volume=closed_volume, remaining_volume=status_position.volume, timestamp_utc=timestamp_utc)
                external_close = False
                trade_journal_logged = True
                changed = True
                return PositionSyncResult(changed=changed, external_close=external_close, trade_journal_logged=trade_journal_logged, external_partial_close=True)
            else:
                instance_state.update_position(open_ticket=status_position.ticket, position_side=status_position.side, position_volume=status_position.volume, entry_price=status_position.entry_price, stop_loss=status_position.stop_loss, take_profit=status_position.take_profit)
            changed = True
        elif status_position.stop_loss is not None and status_position.take_profit is not None and (status_position.stop_loss != instance_state.position_stop_loss or status_position.take_profit != instance_state.position_take_profit):
            instance_state.update_position_levels(stop_loss=status_position.stop_loss, take_profit=status_position.take_profit)
            changed = True
    elif status_position is not None:
        changed = _apply_status_position_to_state(instance_state, status_position) or changed
    return PositionSyncResult(changed=changed, external_close=external_close, trade_journal_logged=trade_journal_logged)

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
    status_position = find_status_position(status, instance)
    if instance_state.open_ticket is not None:
        if not _position_is_active_in_status(status, instance, open_ticket=instance_state.open_ticket):
            instance_state.clear_position()
            changed = True
    elif status_position is not None:
        changed = _apply_status_position_to_state(instance_state, status_position) or changed
    return changed
