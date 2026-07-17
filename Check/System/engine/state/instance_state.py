from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from engine.core.atomic_io import atomic_read_text, atomic_write_json
from engine.core.instance import Instance
from engine.core.paths import SystemPaths
from engine.protocol.constants import AckStatus, Decision, STATE_SCHEMA_VERSION
from engine.protocol.errors import ValidationError
from engine.protocol.parser import parse_json
MODULE_NAME = 'state.instance_state'

def _validation_error(message: str, **context: object) -> ValidationError:
    return ValidationError(message, module=MODULE_NAME, context=dict(context))

@dataclass
class InstanceState:
    instance: Instance
    last_decision: str = Decision.WAIT.value
    last_reason: str = 'INIT'
    open_ticket: int | None = None
    position_side: str | None = None
    position_volume: float | None = None
    position_entry_price: float | None = None
    position_stop_loss: float | None = None
    position_take_profit: float | None = None
    position_reference_take_profit: float | None = None
    position_bars_open: int = 0
    position_open_time_utc: str | None = None
    position_last_bar_utc: str | None = None
    partial_close_applied: bool = False
    last_command_id: str = ''
    last_ack_status: str = ''
    pending_execution_command_id: str | None = None
    pending_execution_decision_id: str | None = None
    pending_execution_since_utc: str | None = None
    pending_execution_comment: str | None = None
    pending_symbol: str | None = None
    pending_magic_number: int | None = None
    pending_execution_side: str | None = None
    pending_execution_volume: float | None = None
    pending_preexisting_tickets: tuple[int, ...] = ()
    ambiguous_pending_execution: bool = False
    duplicate_position_anomaly: bool = False
    close_pending_reconciliation: bool = False
    close_pending_ticket: int | None = None
    close_pending_side: str | None = None
    close_pending_volume: float | None = None
    close_pending_since_utc: str | None = None
    instrument_digits: int = 0
    instrument_point: float = 0.0
    instrument_pip: float = 0.0
    day_start_balance: float | None = None
    peak_equity: float | None = None
    cycle_count: int = 0
    last_cycle_utc: str = ''
    last_seen_market_bar_utc: str = ''

    def path(self, paths: SystemPaths) -> Path:
        return paths.account_state_dir(self.instance.account_id) / self.instance.instance_state_filename()

    def update_cycle(self, *, decision: str, reason: str, cycle_utc: str) -> None:
        self.last_decision = decision
        self.last_reason = reason
        self.last_cycle_utc = cycle_utc
        self.cycle_count += 1

    def update_execution(self, *, command_id: str, ack_status: str) -> None:
        self.last_command_id = command_id
        self.last_ack_status = ack_status

    def update_position(self, *, open_ticket: int, position_side: str, position_volume: float, entry_price: float | None=None, fill_price: float | None=None, stop_loss: float | None=None, take_profit: float | None=None, open_time_utc: str | None=None, position_last_bar_utc: str | None=None) -> None:
        if open_ticket < 0:
            raise _validation_error('open_ticket must be >= 0', open_ticket=open_ticket)
        if position_volume <= 0:
            raise _validation_error('position_volume must be > 0', position_volume=position_volume)
        self.open_ticket = open_ticket
        self.position_side = position_side
        self.position_volume = position_volume
        resolved_entry = fill_price if fill_price is not None else entry_price
        if resolved_entry is not None:
            self.position_entry_price = resolved_entry
        if stop_loss is not None:
            self.position_stop_loss = stop_loss
        if take_profit is not None:
            self.position_take_profit = take_profit
        if open_time_utc is not None:
            self.position_open_time_utc = open_time_utc
        self.position_bars_open = 1
        self.position_last_bar_utc = position_last_bar_utc
        self.partial_close_applied = False

    def update_position_levels(self, *, stop_loss: float, take_profit: float) -> None:
        self.position_stop_loss = stop_loss
        self.position_take_profit = take_profit

    def reduce_position_volume(self, *, volume: float) -> None:
        if volume <= 0:
            raise _validation_error('close volume must be > 0', volume=volume)
        if self.position_volume is None:
            raise _validation_error('cannot reduce position volume without an open position')
        remaining = self.position_volume - volume
        if remaining <= 0:
            self.clear_position()
            return
        self.position_volume = remaining
        self.partial_close_applied = True

    def increment_position_bars(self) -> None:
        if self.open_ticket is not None:
            self.position_bars_open += 1

    def sync_position_bars_for_market_bar(self, bar_utc: str) -> bool:
        if self.open_ticket is None:
            return False
        if self.position_last_bar_utc == bar_utc:
            return False
        if self.position_last_bar_utc is not None:
            self.position_bars_open += 1
            self.position_last_bar_utc = bar_utc
            return True
        self.position_last_bar_utc = bar_utc
        return False

    def clear_pending_execution(self) -> None:
        self.pending_execution_command_id = None
        self.pending_execution_decision_id = None
        self.pending_execution_since_utc = None
        self.pending_execution_comment = None
        self.pending_symbol = None
        self.pending_magic_number = None
        self.pending_execution_side = None
        self.pending_execution_volume = None
        self.pending_preexisting_tickets = ()
        self.ambiguous_pending_execution = False

    def set_pending_execution(
        self,
        *,
        command_id: str,
        decision_id: str | None=None,
        since_utc: str | None=None,
        comment: str | None=None,
        symbol: str | None=None,
        magic: int | None=None,
        side: str | None=None,
        volume: float | None=None,
        preexisting_tickets: tuple[int, ...]=(),
    ) -> None:
        self.pending_execution_command_id = command_id
        self.pending_execution_decision_id = decision_id
        self.pending_execution_since_utc = since_utc
        self.pending_execution_comment = comment
        self.pending_symbol = symbol
        self.pending_magic_number = magic
        self.pending_execution_side = side
        self.pending_execution_volume = volume
        self.pending_preexisting_tickets = tuple(preexisting_tickets)
        self.ambiguous_pending_execution = False

    def clear_close_pending(self) -> None:
        self.close_pending_reconciliation = False
        self.close_pending_ticket = None
        self.close_pending_side = None
        self.close_pending_volume = None
        self.close_pending_since_utc = None

    def set_close_pending(self, *, ticket: int, side: str | None, volume: float | None, since_utc: str) -> None:
        self.close_pending_reconciliation = True
        self.close_pending_ticket = ticket
        self.close_pending_side = side
        self.close_pending_volume = volume
        self.close_pending_since_utc = since_utc

    def clear_position(self) -> None:
        self.open_ticket = None
        self.position_side = None
        self.position_volume = None
        self.position_entry_price = None
        self.position_stop_loss = None
        self.position_take_profit = None
        self.position_reference_take_profit = None
        self.position_bars_open = 0
        self.position_open_time_utc = None
        self.position_last_bar_utc = None
        self.partial_close_applied = False
        self.duplicate_position_anomaly = False

    def update_instrument(self, *, digits: int, point: float, pip: float) -> None:
        self.instrument_digits = digits
        self.instrument_point = point
        self.instrument_pip = pip

    def update_risk_metrics(self, *, day_start_balance: float | None=None, peak_equity: float | None=None) -> None:
        if day_start_balance is not None:
            if day_start_balance <= 0:
                raise _validation_error('day_start_balance must be > 0', day_start_balance=day_start_balance)
            self.day_start_balance = day_start_balance
        if peak_equity is not None:
            if peak_equity <= 0:
                raise _validation_error('peak_equity must be > 0', peak_equity=peak_equity)
            self.peak_equity = peak_equity

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {'schema_version': STATE_SCHEMA_VERSION, 'account_id': self.instance.account_id, 'symbol': self.instance.symbol, 'magic': self.instance.magic, 'last_decision': self.last_decision, 'last_reason': self.last_reason, 'last_command_id': self.last_command_id, 'last_ack_status': self.last_ack_status, 'instrument_digits': self.instrument_digits, 'instrument_point': self.instrument_point, 'instrument_pip': self.instrument_pip, 'cycle_count': self.cycle_count, 'last_cycle_utc': self.last_cycle_utc}
        if self.open_ticket is not None:
            data['open_ticket'] = self.open_ticket
        if self.position_side is not None:
            data['position_side'] = self.position_side
        if self.position_volume is not None:
            data['position_volume'] = self.position_volume
        if self.position_entry_price is not None:
            data['position_entry_price'] = self.position_entry_price
        if self.position_stop_loss is not None:
            data['position_stop_loss'] = self.position_stop_loss
        if self.position_take_profit is not None:
            data['position_take_profit'] = self.position_take_profit
        if self.position_reference_take_profit is not None:
            data['position_reference_take_profit'] = self.position_reference_take_profit
        if self.open_ticket is not None:
            data['position_bars_open'] = self.position_bars_open
            if self.partial_close_applied:
                data['partial_close_applied'] = True
        if self.position_open_time_utc is not None:
            data['position_open_time_utc'] = self.position_open_time_utc
        if self.position_last_bar_utc is not None:
            data['position_last_bar_utc'] = self.position_last_bar_utc
        if self.pending_execution_command_id is not None:
            data['pending_execution_command_id'] = self.pending_execution_command_id
        if self.pending_execution_decision_id is not None:
            data['pending_execution_decision_id'] = self.pending_execution_decision_id
        if self.pending_execution_since_utc is not None:
            data['pending_execution_since_utc'] = self.pending_execution_since_utc
        if self.pending_execution_comment is not None:
            data['pending_execution_comment'] = self.pending_execution_comment
        if self.pending_symbol is not None:
            data['pending_symbol'] = self.pending_symbol
        if self.pending_magic_number is not None:
            data['pending_magic_number'] = self.pending_magic_number
        if self.pending_execution_side is not None:
            data['pending_execution_side'] = self.pending_execution_side
        if self.pending_execution_volume is not None:
            data['pending_execution_volume'] = self.pending_execution_volume
        if self.pending_preexisting_tickets:
            data['pending_preexisting_tickets'] = list(self.pending_preexisting_tickets)
        if self.ambiguous_pending_execution:
            data['ambiguous_pending_execution'] = True
        if self.duplicate_position_anomaly:
            data['duplicate_position_anomaly'] = True
        if self.close_pending_reconciliation:
            data['close_pending_reconciliation'] = True
            if self.close_pending_ticket is not None:
                data['close_pending_ticket'] = self.close_pending_ticket
            if self.close_pending_side is not None:
                data['close_pending_side'] = self.close_pending_side
            if self.close_pending_volume is not None:
                data['close_pending_volume'] = self.close_pending_volume
            if self.close_pending_since_utc is not None:
                data['close_pending_since_utc'] = self.close_pending_since_utc
        if self.day_start_balance is not None:
            data['day_start_balance'] = self.day_start_balance
        if self.peak_equity is not None:
            data['peak_equity'] = self.peak_equity
        if self.last_seen_market_bar_utc:
            data['last_seen_market_bar_utc'] = self.last_seen_market_bar_utc
        return data

    def save(self, paths: SystemPaths) -> None:
        paths.ensure_account_directories(self.instance.account_id)
        atomic_write_json(self.path(paths), self.to_dict(), pretty=True)

    @classmethod
    def load(cls, paths: SystemPaths, instance: Instance) -> InstanceState:
        state = cls(instance=instance)
        state_path = state.path(paths)
        if not state_path.exists():
            return state
        payload = parse_json(atomic_read_text(state_path))
        if payload.get('account_id') != instance.account_id:
            raise _validation_error('instance_state account_id mismatch', path=str(state_path))
        if payload.get('symbol') != instance.symbol:
            raise _validation_error('instance_state symbol mismatch', path=str(state_path))
        if payload.get('magic') != instance.magic:
            raise _validation_error('instance_state magic mismatch', path=str(state_path))
        state.last_decision = str(payload.get('last_decision', state.last_decision))
        state.last_reason = str(payload.get('last_reason', state.last_reason))
        state.open_ticket = payload.get('open_ticket')
        state.position_side = payload.get('position_side')
        state.position_volume = payload.get('position_volume')
        position_entry_price = payload.get('position_entry_price')
        if position_entry_price is not None:
            state.position_entry_price = float(position_entry_price)
        position_stop_loss = payload.get('position_stop_loss')
        if position_stop_loss is not None:
            state.position_stop_loss = float(position_stop_loss)
        position_take_profit = payload.get('position_take_profit')
        if position_take_profit is not None:
            state.position_take_profit = float(position_take_profit)
        position_reference_take_profit = payload.get('position_reference_take_profit')
        if position_reference_take_profit is not None:
            state.position_reference_take_profit = float(position_reference_take_profit)
        position_bars_open = payload.get('position_bars_open')
        if position_bars_open is not None:
            state.position_bars_open = int(position_bars_open)
        state.partial_close_applied = bool(payload.get('partial_close_applied', False))
        position_open_time_utc = payload.get('position_open_time_utc')
        if position_open_time_utc is not None:
            state.position_open_time_utc = str(position_open_time_utc)
        position_last_bar_utc = payload.get('position_last_bar_utc')
        if position_last_bar_utc is not None:
            state.position_last_bar_utc = str(position_last_bar_utc)
        pending_execution_command_id = payload.get('pending_execution_command_id')
        if pending_execution_command_id is not None:
            state.pending_execution_command_id = str(pending_execution_command_id)
        pending_execution_decision_id = payload.get('pending_execution_decision_id')
        if pending_execution_decision_id is not None:
            state.pending_execution_decision_id = str(pending_execution_decision_id)
        pending_execution_since_utc = payload.get('pending_execution_since_utc')
        if pending_execution_since_utc is not None:
            state.pending_execution_since_utc = str(pending_execution_since_utc)
        pending_execution_comment = payload.get('pending_execution_comment')
        if pending_execution_comment is not None:
            state.pending_execution_comment = str(pending_execution_comment)
        pending_symbol = payload.get('pending_symbol')
        if pending_symbol is not None:
            state.pending_symbol = str(pending_symbol)
        pending_magic_number = payload.get('pending_magic_number')
        if pending_magic_number is not None:
            state.pending_magic_number = int(pending_magic_number)
        pending_execution_side = payload.get('pending_execution_side')
        if pending_execution_side is not None:
            state.pending_execution_side = str(pending_execution_side)
        pending_execution_volume = payload.get('pending_execution_volume')
        if pending_execution_volume is not None:
            state.pending_execution_volume = float(pending_execution_volume)
        preexisting = payload.get('pending_preexisting_tickets')
        if isinstance(preexisting, list):
            state.pending_preexisting_tickets = tuple(int(item) for item in preexisting)
        state.ambiguous_pending_execution = bool(payload.get('ambiguous_pending_execution', False))
        state.duplicate_position_anomaly = bool(payload.get('duplicate_position_anomaly', False))
        state.close_pending_reconciliation = bool(payload.get('close_pending_reconciliation', False))
        close_pending_ticket = payload.get('close_pending_ticket')
        if close_pending_ticket is not None:
            state.close_pending_ticket = int(close_pending_ticket)
        close_pending_side = payload.get('close_pending_side')
        if close_pending_side is not None:
            state.close_pending_side = str(close_pending_side)
        close_pending_volume = payload.get('close_pending_volume')
        if close_pending_volume is not None:
            state.close_pending_volume = float(close_pending_volume)
        close_pending_since_utc = payload.get('close_pending_since_utc')
        if close_pending_since_utc is not None:
            state.close_pending_since_utc = str(close_pending_since_utc)
        state.last_command_id = str(payload.get('last_command_id', state.last_command_id))
        state.last_ack_status = str(payload.get('last_ack_status', state.last_ack_status))
        state.instrument_digits = int(payload.get('instrument_digits', state.instrument_digits))
        state.instrument_point = float(payload.get('instrument_point', state.instrument_point))
        state.instrument_pip = float(payload.get('instrument_pip', state.instrument_pip))
        day_start_balance = payload.get('day_start_balance')
        if day_start_balance is not None:
            state.day_start_balance = float(day_start_balance)
        peak_equity = payload.get('peak_equity')
        if peak_equity is not None:
            state.peak_equity = float(peak_equity)
        state.cycle_count = int(payload.get('cycle_count', state.cycle_count))
        state.last_cycle_utc = str(payload.get('last_cycle_utc', state.last_cycle_utc))
        state.last_seen_market_bar_utc = str(payload.get('last_seen_market_bar_utc', payload.get('last_executed_market_bar_utc', state.last_seen_market_bar_utc)))
        return state
