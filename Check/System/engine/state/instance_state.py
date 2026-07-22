from __future__ import annotations
from dataclasses import dataclass, field
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
    peak_net_profit_money: float = 0.0
    money_trailing_step_index: int = -1
    locked_profit_money: float = 0.0
    last_money_trailing_sl: float | None = None
    money_trailing_ticket: int | None = None
    money_trailing_state_missing: bool = False
    be_plus_confirmed: bool = False
    confirmed_protective_sl: float | None = None
    pending_protective_sl: float | None = None
    pending_trailing_reason: str | None = None
    pending_trailing_step_pips: float | None = None
    pip_trail_confirmed_steps: int = 0
    computed_be_plus_sl: float | None = None
    next_pip_trail_sl: float | None = None
    last_trailing_modify_status: str | None = None
    last_trailing_broker_error: str | None = None
    trailing_reason_code: str | None = None
    current_net_profit_money: float | None = None
    cooldown_remaining_bars: int = 0
    cooldown_last_counted_bar_utc: str = ''
    last_trade_result: str | None = None
    last_trade_close_time_utc: str | None = None
    last_trade_close_bar_utc: str | None = None
    signal_fingerprints: dict[str, int] = field(default_factory=dict)
    fingerprint_last_counted_bar_utc: str = ''
    last_signal_fingerprint: str | None = None

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
        if self.money_trailing_ticket is not None and self.money_trailing_ticket != open_ticket:
            self.clear_money_trailing_state()
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
        if self.money_trailing_ticket is None:
            self.money_trailing_ticket = open_ticket

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

    def money_trailing_snapshot(self) -> dict[str, Any]:
        return {
            'ticket': self.money_trailing_ticket if self.money_trailing_ticket is not None else self.open_ticket,
            'peak_net_profit_money': self.peak_net_profit_money,
            'money_trailing_step_index': self.money_trailing_step_index,
            'locked_profit_money': self.locked_profit_money,
            'last_money_trailing_sl': self.last_money_trailing_sl,
            'be_plus_confirmed': self.be_plus_confirmed,
            'confirmed_protective_sl': self.confirmed_protective_sl,
            'pending_protective_sl': self.pending_protective_sl,
            'pending_trailing_reason': self.pending_trailing_reason,
            'pending_trailing_step_pips': self.pending_trailing_step_pips,
            'pip_trail_confirmed_steps': self.pip_trail_confirmed_steps,
            'computed_be_plus_sl': self.computed_be_plus_sl,
            'next_pip_trail_sl': self.next_pip_trail_sl,
            'last_trailing_modify_status': self.last_trailing_modify_status,
            'last_trailing_broker_error': self.last_trailing_broker_error,
            'trailing_reason_code': self.trailing_reason_code,
            'current_net_profit_money': self.current_net_profit_money,
            'broker_stop_loss': self.position_stop_loss,
        }

    def clear_money_trailing_state(self) -> None:
        self.peak_net_profit_money = 0.0
        self.money_trailing_step_index = -1
        self.locked_profit_money = 0.0
        self.last_money_trailing_sl = None
        self.money_trailing_ticket = None
        self.money_trailing_state_missing = False
        self.be_plus_confirmed = False
        self.confirmed_protective_sl = None
        self.pending_protective_sl = None
        self.pending_trailing_reason = None
        self.pending_trailing_step_pips = None
        self.pip_trail_confirmed_steps = 0
        self.computed_be_plus_sl = None
        self.next_pip_trail_sl = None
        self.last_trailing_modify_status = None
        self.last_trailing_broker_error = None
        self.trailing_reason_code = None
        self.current_net_profit_money = None

    def apply_money_trailing_state(
        self,
        *,
        peak_net_profit_money: float,
        money_trailing_step_index: int,
        locked_profit_money: float,
        last_money_trailing_sl: float | None,
        ticket: int | None = None,
        be_plus_confirmed: bool | None = None,
        confirmed_protective_sl: float | None = None,
        pending_protective_sl: float | None = None,
        pending_trailing_reason: str | None = None,
        pending_trailing_step_pips: float | None = None,
        pip_trail_confirmed_steps: int | None = None,
        computed_be_plus_sl: float | None = None,
        next_pip_trail_sl: float | None = None,
        last_trailing_modify_status: str | None = None,
        last_trailing_broker_error: str | None = None,
        trailing_reason_code: str | None = None,
        current_net_profit_money: float | None = None,
        sync_pending: bool = False,
    ) -> None:
        self.peak_net_profit_money = peak_net_profit_money
        self.money_trailing_step_index = money_trailing_step_index
        self.locked_profit_money = locked_profit_money
        self.last_money_trailing_sl = last_money_trailing_sl
        if ticket is not None:
            self.money_trailing_ticket = ticket
        elif self.open_ticket is not None:
            self.money_trailing_ticket = self.open_ticket
        self.money_trailing_state_missing = False
        if be_plus_confirmed is not None:
            self.be_plus_confirmed = be_plus_confirmed
        if confirmed_protective_sl is not None:
            self.confirmed_protective_sl = confirmed_protective_sl
        if sync_pending or pending_protective_sl is not None:
            self.pending_protective_sl = pending_protective_sl
        if sync_pending or pending_trailing_reason is not None:
            self.pending_trailing_reason = pending_trailing_reason
        if sync_pending or pending_trailing_step_pips is not None:
            self.pending_trailing_step_pips = pending_trailing_step_pips
        if pip_trail_confirmed_steps is not None:
            self.pip_trail_confirmed_steps = pip_trail_confirmed_steps
        if computed_be_plus_sl is not None:
            self.computed_be_plus_sl = computed_be_plus_sl
        if next_pip_trail_sl is not None:
            self.next_pip_trail_sl = next_pip_trail_sl
        if last_trailing_modify_status is not None:
            self.last_trailing_modify_status = last_trailing_modify_status
        if last_trailing_broker_error is not None:
            self.last_trailing_broker_error = last_trailing_broker_error
        if trailing_reason_code is not None:
            self.trailing_reason_code = trailing_reason_code
        if current_net_profit_money is not None:
            self.current_net_profit_money = current_net_profit_money

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
        self.clear_money_trailing_state()

    def register_trade_close(self, *, close_bar_utc: str, close_time_utc: str, was_loss: bool, cooldown_bars_after_trade: int, cooldown_bars_after_loss: int) -> None:
        """Start bar-based cooldown after a position is flattened."""
        bars = int(cooldown_bars_after_loss if was_loss else cooldown_bars_after_trade)
        self.last_trade_result = 'loss' if was_loss else 'win'
        self.last_trade_close_time_utc = close_time_utc
        self.last_trade_close_bar_utc = close_bar_utc
        self.cooldown_remaining_bars = max(0, bars)
        self.cooldown_last_counted_bar_utc = close_bar_utc

    def cooldown_bars_remaining(self, *, current_bar_utc: str) -> int:
        """Return remaining cooldown bars, decrementing once per new closed bar."""
        if self.cooldown_remaining_bars <= 0:
            return 0
        if current_bar_utc and self.cooldown_last_counted_bar_utc and current_bar_utc > self.cooldown_last_counted_bar_utc:
            self.cooldown_remaining_bars = max(0, self.cooldown_remaining_bars - 1)
            self.cooldown_last_counted_bar_utc = current_bar_utc
        elif current_bar_utc and not self.cooldown_last_counted_bar_utc:
            self.cooldown_last_counted_bar_utc = current_bar_utc
        return max(0, int(self.cooldown_remaining_bars))

    def register_signal_fingerprint(self, fingerprint: str, *, expiry_bars: int) -> None:
        if not fingerprint or expiry_bars <= 0:
            return
        self.signal_fingerprints[fingerprint] = int(expiry_bars)
        self.last_signal_fingerprint = fingerprint

    def expire_signal_fingerprints(self, *, current_bar_utc: str) -> None:
        if not self.signal_fingerprints:
            return
        if current_bar_utc and self.fingerprint_last_counted_bar_utc and current_bar_utc > self.fingerprint_last_counted_bar_utc:
            for key in list(self.signal_fingerprints):
                remaining = int(self.signal_fingerprints[key]) - 1
                if remaining <= 0:
                    del self.signal_fingerprints[key]
                else:
                    self.signal_fingerprints[key] = remaining
            self.fingerprint_last_counted_bar_utc = current_bar_utc
        elif current_bar_utc and not self.fingerprint_last_counted_bar_utc:
            self.fingerprint_last_counted_bar_utc = current_bar_utc

    @property
    def active_signal_fingerprints(self) -> dict[str, str]:
        """Compatibility map fingerprint -> remaining bars as string for quality checks."""
        return {key: str(value) for key, value in self.signal_fingerprints.items()}

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
        if self.peak_net_profit_money != 0.0:
            data['peak_net_profit_money'] = self.peak_net_profit_money
        if self.money_trailing_step_index != -1:
            data['money_trailing_step_index'] = self.money_trailing_step_index
        if self.locked_profit_money != 0.0:
            data['locked_profit_money'] = self.locked_profit_money
        if self.last_money_trailing_sl is not None:
            data['last_money_trailing_sl'] = self.last_money_trailing_sl
        if self.money_trailing_ticket is not None:
            data['money_trailing_ticket'] = self.money_trailing_ticket
        if self.money_trailing_state_missing:
            data['money_trailing_state_missing'] = True
        if self.be_plus_confirmed:
            data['be_plus_confirmed'] = True
        if self.confirmed_protective_sl is not None:
            data['confirmed_protective_sl'] = self.confirmed_protective_sl
        if self.pending_protective_sl is not None:
            data['pending_protective_sl'] = self.pending_protective_sl
        if self.pending_trailing_reason is not None:
            data['pending_trailing_reason'] = self.pending_trailing_reason
        if self.pending_trailing_step_pips is not None:
            data['pending_trailing_step_pips'] = self.pending_trailing_step_pips
        if self.pip_trail_confirmed_steps:
            data['pip_trail_confirmed_steps'] = self.pip_trail_confirmed_steps
        if self.computed_be_plus_sl is not None:
            data['computed_be_plus_sl'] = self.computed_be_plus_sl
        if self.next_pip_trail_sl is not None:
            data['next_pip_trail_sl'] = self.next_pip_trail_sl
        if self.last_trailing_modify_status is not None:
            data['last_trailing_modify_status'] = self.last_trailing_modify_status
        if self.last_trailing_broker_error is not None:
            data['last_trailing_broker_error'] = self.last_trailing_broker_error
        if self.trailing_reason_code is not None:
            data['trailing_reason_code'] = self.trailing_reason_code
        if self.current_net_profit_money is not None:
            data['current_net_profit_money'] = self.current_net_profit_money
        if self.cooldown_remaining_bars > 0:
            data['cooldown_remaining_bars'] = self.cooldown_remaining_bars
        if self.cooldown_last_counted_bar_utc:
            data['cooldown_last_counted_bar_utc'] = self.cooldown_last_counted_bar_utc
        if self.last_trade_result is not None:
            data['last_trade_result'] = self.last_trade_result
        if self.last_trade_close_time_utc is not None:
            data['last_trade_close_time_utc'] = self.last_trade_close_time_utc
        if self.last_trade_close_bar_utc is not None:
            data['last_trade_close_bar_utc'] = self.last_trade_close_bar_utc
        if self.signal_fingerprints:
            data['signal_fingerprints'] = dict(self.signal_fingerprints)
        if self.fingerprint_last_counted_bar_utc:
            data['fingerprint_last_counted_bar_utc'] = self.fingerprint_last_counted_bar_utc
        if self.last_signal_fingerprint is not None:
            data['last_signal_fingerprint'] = self.last_signal_fingerprint
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
        peak_net_profit_money = payload.get('peak_net_profit_money')
        if peak_net_profit_money is not None:
            state.peak_net_profit_money = float(peak_net_profit_money)
        money_trailing_step_index = payload.get('money_trailing_step_index')
        if money_trailing_step_index is not None:
            state.money_trailing_step_index = int(money_trailing_step_index)
        locked_profit_money = payload.get('locked_profit_money')
        if locked_profit_money is not None:
            state.locked_profit_money = float(locked_profit_money)
        last_money_trailing_sl = payload.get('last_money_trailing_sl')
        if last_money_trailing_sl is not None:
            state.last_money_trailing_sl = float(last_money_trailing_sl)
        money_trailing_ticket = payload.get('money_trailing_ticket')
        if money_trailing_ticket is not None:
            state.money_trailing_ticket = int(money_trailing_ticket)
        elif state.open_ticket is not None and (
            state.peak_net_profit_money != 0.0
            or state.money_trailing_step_index != -1
            or state.locked_profit_money != 0.0
            or state.last_money_trailing_sl is not None
        ):
            state.money_trailing_ticket = state.open_ticket
        state.money_trailing_state_missing = bool(payload.get('money_trailing_state_missing', False))
        state.be_plus_confirmed = bool(payload.get('be_plus_confirmed', False))
        confirmed_protective_sl = payload.get('confirmed_protective_sl')
        if confirmed_protective_sl is not None:
            state.confirmed_protective_sl = float(confirmed_protective_sl)
        pending_protective_sl = payload.get('pending_protective_sl')
        if pending_protective_sl is not None:
            state.pending_protective_sl = float(pending_protective_sl)
        pending_trailing_reason = payload.get('pending_trailing_reason')
        if pending_trailing_reason is not None:
            state.pending_trailing_reason = str(pending_trailing_reason)
        pending_trailing_step_pips = payload.get('pending_trailing_step_pips')
        if pending_trailing_step_pips is not None:
            state.pending_trailing_step_pips = float(pending_trailing_step_pips)
        pip_trail_confirmed_steps = payload.get('pip_trail_confirmed_steps')
        if pip_trail_confirmed_steps is not None:
            state.pip_trail_confirmed_steps = int(pip_trail_confirmed_steps)
        computed_be_plus_sl = payload.get('computed_be_plus_sl')
        if computed_be_plus_sl is not None:
            state.computed_be_plus_sl = float(computed_be_plus_sl)
        next_pip_trail_sl = payload.get('next_pip_trail_sl')
        if next_pip_trail_sl is not None:
            state.next_pip_trail_sl = float(next_pip_trail_sl)
        last_trailing_modify_status = payload.get('last_trailing_modify_status')
        if last_trailing_modify_status is not None:
            state.last_trailing_modify_status = str(last_trailing_modify_status)
        last_trailing_broker_error = payload.get('last_trailing_broker_error')
        if last_trailing_broker_error is not None:
            state.last_trailing_broker_error = str(last_trailing_broker_error)
        trailing_reason_code = payload.get('trailing_reason_code')
        if trailing_reason_code is not None:
            state.trailing_reason_code = str(trailing_reason_code)
        current_net_profit_money = payload.get('current_net_profit_money')
        if current_net_profit_money is not None:
            state.current_net_profit_money = float(current_net_profit_money)
        if state.open_ticket is not None and state.money_trailing_ticket is not None and state.money_trailing_ticket != state.open_ticket:
            state.clear_money_trailing_state()
            state.money_trailing_ticket = state.open_ticket
            state.money_trailing_state_missing = True
        state.cooldown_remaining_bars = int(payload.get('cooldown_remaining_bars', 0) or 0)
        state.cooldown_last_counted_bar_utc = str(payload.get('cooldown_last_counted_bar_utc', '') or '')
        last_trade_result = payload.get('last_trade_result')
        if last_trade_result is not None:
            state.last_trade_result = str(last_trade_result)
        last_trade_close_time_utc = payload.get('last_trade_close_time_utc')
        if last_trade_close_time_utc is not None:
            state.last_trade_close_time_utc = str(last_trade_close_time_utc)
        last_trade_close_bar_utc = payload.get('last_trade_close_bar_utc')
        if last_trade_close_bar_utc is not None:
            state.last_trade_close_bar_utc = str(last_trade_close_bar_utc)
        fingerprints = payload.get('signal_fingerprints')
        if isinstance(fingerprints, dict):
            cleaned: dict[str, int] = {}
            for key, value in fingerprints.items():
                try:
                    remaining = int(value)
                except (TypeError, ValueError):
                    continue
                if remaining > 0 and isinstance(key, str) and key:
                    cleaned[key] = remaining
            state.signal_fingerprints = cleaned
        state.fingerprint_last_counted_bar_utc = str(payload.get('fingerprint_last_counted_bar_utc', '') or '')
        last_signal_fingerprint = payload.get('last_signal_fingerprint')
        if last_signal_fingerprint is not None:
            state.last_signal_fingerprint = str(last_signal_fingerprint)
        return state
