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

MODULE_NAME = "state.instance_state"


def _validation_error(message: str, **context: object) -> ValidationError:
    return ValidationError(message, module=MODULE_NAME, context=dict(context))


@dataclass
class InstanceState:
    instance: Instance
    last_decision: str = Decision.WAIT.value
    last_reason: str = "INIT"
    open_ticket: int | None = None
    position_side: str | None = None
    position_volume: float | None = None
    position_entry_price: float | None = None
    position_stop_loss: float | None = None
    position_take_profit: float | None = None
    position_bars_open: int = 0
    partial_close_applied: bool = False
    last_command_id: str = ""
    last_ack_status: str = ""
    instrument_digits: int = 0
    instrument_point: float = 0.0
    instrument_pip: float = 0.0
    day_start_balance: float | None = None
    peak_equity: float | None = None
    cycle_count: int = 0
    last_cycle_utc: str = ""

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

    def update_position(
        self,
        *,
        open_ticket: int,
        position_side: str,
        position_volume: float,
        entry_price: float | None = None,
        stop_loss: float | None = None,
        take_profit: float | None = None,
    ) -> None:
        if open_ticket < 0:
            raise _validation_error("open_ticket must be >= 0", open_ticket=open_ticket)
        if position_volume <= 0:
            raise _validation_error("position_volume must be > 0", position_volume=position_volume)
        self.open_ticket = open_ticket
        self.position_side = position_side
        self.position_volume = position_volume
        if entry_price is not None:
            self.position_entry_price = entry_price
        if stop_loss is not None:
            self.position_stop_loss = stop_loss
        if take_profit is not None:
            self.position_take_profit = take_profit
        self.position_bars_open = 1
        self.partial_close_applied = False

    def update_position_levels(self, *, stop_loss: float, take_profit: float) -> None:
        self.position_stop_loss = stop_loss
        self.position_take_profit = take_profit

    def reduce_position_volume(self, *, volume: float) -> None:
        if volume <= 0:
            raise _validation_error("close volume must be > 0", volume=volume)
        if self.position_volume is None:
            raise _validation_error("cannot reduce position volume without an open position")
        remaining = self.position_volume - volume
        if remaining <= 0:
            self.clear_position()
            return
        self.position_volume = remaining
        self.partial_close_applied = True

    def increment_position_bars(self) -> None:
        if self.open_ticket is not None:
            self.position_bars_open += 1

    def clear_position(self) -> None:
        self.open_ticket = None
        self.position_side = None
        self.position_volume = None
        self.position_entry_price = None
        self.position_stop_loss = None
        self.position_take_profit = None
        self.position_bars_open = 0
        self.partial_close_applied = False

    def update_instrument(self, *, digits: int, point: float, pip: float) -> None:
        self.instrument_digits = digits
        self.instrument_point = point
        self.instrument_pip = pip

    def update_risk_metrics(
        self,
        *,
        day_start_balance: float | None = None,
        peak_equity: float | None = None,
    ) -> None:
        if day_start_balance is not None:
            if day_start_balance <= 0:
                raise _validation_error("day_start_balance must be > 0", day_start_balance=day_start_balance)
            self.day_start_balance = day_start_balance
        if peak_equity is not None:
            if peak_equity <= 0:
                raise _validation_error("peak_equity must be > 0", peak_equity=peak_equity)
            self.peak_equity = peak_equity

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "schema_version": STATE_SCHEMA_VERSION,
            "account_id": self.instance.account_id,
            "symbol": self.instance.symbol,
            "magic": self.instance.magic,
            "last_decision": self.last_decision,
            "last_reason": self.last_reason,
            "last_command_id": self.last_command_id,
            "last_ack_status": self.last_ack_status,
            "instrument_digits": self.instrument_digits,
            "instrument_point": self.instrument_point,
            "instrument_pip": self.instrument_pip,
            "cycle_count": self.cycle_count,
            "last_cycle_utc": self.last_cycle_utc,
        }
        if self.open_ticket is not None:
            data["open_ticket"] = self.open_ticket
        if self.position_side is not None:
            data["position_side"] = self.position_side
        if self.position_volume is not None:
            data["position_volume"] = self.position_volume
        if self.position_entry_price is not None:
            data["position_entry_price"] = self.position_entry_price
        if self.position_stop_loss is not None:
            data["position_stop_loss"] = self.position_stop_loss
        if self.position_take_profit is not None:
            data["position_take_profit"] = self.position_take_profit
        if self.open_ticket is not None:
            data["position_bars_open"] = self.position_bars_open
            if self.partial_close_applied:
                data["partial_close_applied"] = True
        if self.day_start_balance is not None:
            data["day_start_balance"] = self.day_start_balance
        if self.peak_equity is not None:
            data["peak_equity"] = self.peak_equity
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
        if payload.get("account_id") != instance.account_id:
            raise _validation_error("instance_state account_id mismatch", path=str(state_path))
        if payload.get("symbol") != instance.symbol:
            raise _validation_error("instance_state symbol mismatch", path=str(state_path))
        if payload.get("magic") != instance.magic:
            raise _validation_error("instance_state magic mismatch", path=str(state_path))

        state.last_decision = str(payload.get("last_decision", state.last_decision))
        state.last_reason = str(payload.get("last_reason", state.last_reason))
        state.open_ticket = payload.get("open_ticket")
        state.position_side = payload.get("position_side")
        state.position_volume = payload.get("position_volume")
        position_entry_price = payload.get("position_entry_price")
        if position_entry_price is not None:
            state.position_entry_price = float(position_entry_price)
        position_stop_loss = payload.get("position_stop_loss")
        if position_stop_loss is not None:
            state.position_stop_loss = float(position_stop_loss)
        position_take_profit = payload.get("position_take_profit")
        if position_take_profit is not None:
            state.position_take_profit = float(position_take_profit)
        position_bars_open = payload.get("position_bars_open")
        if position_bars_open is not None:
            state.position_bars_open = int(position_bars_open)
        state.partial_close_applied = bool(payload.get("partial_close_applied", False))
        state.last_command_id = str(payload.get("last_command_id", state.last_command_id))
        state.last_ack_status = str(payload.get("last_ack_status", state.last_ack_status))
        state.instrument_digits = int(payload.get("instrument_digits", state.instrument_digits))
        state.instrument_point = float(payload.get("instrument_point", state.instrument_point))
        state.instrument_pip = float(payload.get("instrument_pip", state.instrument_pip))
        day_start_balance = payload.get("day_start_balance")
        if day_start_balance is not None:
            state.day_start_balance = float(day_start_balance)
        peak_equity = payload.get("peak_equity")
        if peak_equity is not None:
            state.peak_equity = float(peak_equity)
        state.cycle_count = int(payload.get("cycle_count", state.cycle_count))
        state.last_cycle_utc = str(payload.get("last_cycle_utc", state.last_cycle_utc))
        return state
