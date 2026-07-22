"""Lightweight MT4 v2 bridge simulator for unit tests (no MetaTrader required)."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from checktrader.execution.protocol import atomic_write_json
from tests.protocol.mt4_v2_shapes import (
    PROTOCOL_VERSION,
    ack_filename,
    command_filename,
    validate_acknowledgement,
    validate_command,
    validate_market_snapshot,
    validate_modify_success,
    validate_status_snapshot,
)


def _utc_now() -> str:
    return "2026-07-22T12:00:00.000Z"


def _message_id() -> str:
    return str(uuid.uuid4())


@dataclass
class SimulatedPosition:
    ticket: int
    symbol: str
    magic: int
    side: str
    volume: float
    open_price: float
    stop_loss: float
    take_profit: float
    open_time: str = "2026-07-22T11:59:00.000Z"
    current_price: float = 0.0
    profit: float = 0.0
    swap: float = 0.0
    commission: float = 0.0
    comment: str = ""

    @property
    def net_profit(self) -> float:
        return self.profit + self.swap + self.commission

    def as_dict(self) -> dict[str, Any]:
        current = self.current_price or self.open_price
        return {
            "ticket": self.ticket,
            "symbol": self.symbol,
            "magic": self.magic,
            "side": self.side,
            "volume": self.volume,
            "open_time": self.open_time,
            "open_price": self.open_price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "current_price": current,
            "profit": self.profit,
            "swap": self.swap,
            "commission": self.commission,
            "net_profit": self.net_profit,
            "comment": self.comment,
        }


@dataclass
class MT4V2BridgeSimulator:
    """Writes market/status and consumes commands like CHECK_SYSTEM_V2."""

    root: Path
    symbol: str = "EURUSD"
    magic: int = 19942026
    account_number: str = "100001"
    bid: float = 1.10000
    ask: float = 1.10020
    sequence: int = 0
    ticket_seed: int = 50000
    positions: dict[int, SimulatedPosition] = field(default_factory=dict)
    processed_ids: set[str] = field(default_factory=set)
    price_tolerance: float = 0.00001

    def __post_init__(self) -> None:
        for leaf in ("market", "status", "commands", "acknowledgements", "archive", "archive/commands"):
            (self.bridge / leaf).mkdir(parents=True, exist_ok=True)

    @property
    def bridge(self) -> Path:
        return self.root / "runtime" / "bridge"

    def _next_sequence(self) -> int:
        self.sequence += 1
        return self.sequence

    def build_market_payload(self, *, bars: int = 3) -> dict[str, Any]:
        seq = self._next_sequence()
        point = 0.00001
        pip_size = 0.0001
        spread = self.ask - self.bid
        bars_m1: list[dict[str, Any]] = []
        base = 1.1000
        for i in range(bars):
            o = base + i * 0.0001
            bars_m1.append(
                {
                    "open_time_utc": f"2026-07-22T11:{i:02d}:00.000Z",
                    "close_time_utc": f"2026-07-22T11:{i:02d}:59.000Z",
                    "open": round(o, 5),
                    "high": round(o + 0.0003, 5),
                    "low": round(o - 0.0002, 5),
                    "close": round(o + 0.0001, 5),
                    "tick_volume": 100 + i,
                    "complete": True,
                }
            )
        return {
            "protocol_version": PROTOCOL_VERSION,
            "message_type": "market_snapshot",
            "message_id": _message_id(),
            "generated_at_utc": _utc_now(),
            "source": "mt4",
            "sequence": seq,
            "account_number": self.account_number,
            "server": "Demo-Server",
            "symbol": self.symbol,
            "digits": 5,
            "point": point,
            "pip_size": pip_size,
            "bid": self.bid,
            "ask": self.ask,
            "spread_points": spread / point,
            "spread_pips": spread / pip_size,
            "tick_size": point,
            "tick_value": 1.0,
            "minimum_lot": 0.01,
            "maximum_lot": 100.0,
            "lot_step": 0.01,
            "stop_level_points": 0,
            "freeze_level_points": 0,
            "trade_allowed": True,
            "market_open": True,
            "bars_m1": bars_m1,
        }

    def build_status_payload(self) -> dict[str, Any]:
        seq = self._next_sequence()
        positions = [pos.as_dict() for pos in self.positions.values()]
        return {
            "protocol_version": PROTOCOL_VERSION,
            "message_type": "status_snapshot",
            "message_id": _message_id(),
            "generated_at_utc": _utc_now(),
            "source": "mt4",
            "sequence": seq,
            "account_number": self.account_number,
            "balance": 10000.0,
            "equity": 10000.0 + sum(p.profit for p in self.positions.values()),
            "margin": 50.0 if self.positions else 0.0,
            "free_margin": 9950.0,
            "margin_level": 20000.0 if self.positions else 0.0,
            "trade_allowed": True,
            "expert_enabled": True,
            "positions": positions,
            "open_positions": positions,
        }

    def export_snapshots(self) -> tuple[Path, Path]:
        market = self.build_market_payload()
        status = self.build_status_payload()
        validate_market_snapshot(market)
        validate_status_snapshot(status)
        market_path = self.bridge / "market" / f"market_{self.symbol}_{self.magic}.json"
        status_path = self.bridge / "status" / f"status_{self.account_number}.json"
        atomic_write_json(market_path, market)
        atomic_write_json(status_path, status)
        return market_path, status_path

    def write_command(self, command: dict[str, Any]) -> Path:
        validate_command(command)
        path = self.bridge / "commands" / command_filename(int(command["sequence"]), str(command["command_id"]))
        atomic_write_json(path, command)
        return path

    def _ack_path(self, command: dict[str, Any]) -> Path:
        return self.bridge / "acknowledgements" / ack_filename(int(command["sequence"]), str(command["command_id"]))

    def _write_ack(self, command: dict[str, Any], ack: dict[str, Any]) -> Path:
        validate_acknowledgement(ack)
        path = self._ack_path(command)
        atomic_write_json(path, ack)
        cmd_path = self.bridge / "commands" / command_filename(int(command["sequence"]), str(command["command_id"]))
        if cmd_path.exists():
            archive = self.bridge / "archive" / "commands" / cmd_path.name
            archive.parent.mkdir(parents=True, exist_ok=True)
            cmd_path.replace(archive)
        self.processed_ids.add(str(command["command_id"]))
        return path

    def _base_ack(self, command: dict[str, Any], *, status: str, **extra: Any) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "protocol_version": PROTOCOL_VERSION,
            "message_type": "acknowledgement",
            "message_id": _message_id(),
            "generated_at_utc": _utc_now(),
            "processed_at_utc": _utc_now(),
            "source": "mt4",
            "sequence": int(command["sequence"]),
            "command_id": command["command_id"],
            "action": command["action"],
            "status": status,
            "symbol": command["symbol"],
            "magic": command["magic"],
            "broker_error_code": 0,
            "broker_error_text": "",
        }
        payload.update(extra)
        return payload

    def process_pending_commands(self) -> list[Path]:
        written: list[Path] = []
        commands_dir = self.bridge / "commands"
        for path in sorted(commands_dir.glob("*.json")):
            if path.name.endswith(".tmp"):
                continue
            command = json.loads(path.read_text(encoding="utf-8"))
            validate_command(command)
            command_id = str(command["command_id"])
            if command_id in self.processed_ids:
                ack = self._base_ack(
                    command, status="ALREADY_PROCESSED", broker_error_text="command_id already processed"
                )
                written.append(self._write_ack(command, ack))
                continue
            if command["symbol"] != self.symbol or int(command["magic"]) != self.magic:
                ack = self._base_ack(command, status="REJECTED", broker_error_text="symbol/magic mismatch")
                written.append(self._write_ack(command, ack))
                continue
            action = str(command["action"])
            if action == "OPEN":
                written.append(self._process_open(command))
            elif action == "MODIFY":
                written.append(self._process_modify(command))
            elif action == "CLOSE":
                written.append(self._process_close(command))
        return written

    def _process_open(self, command: dict[str, Any]) -> Path:
        self.ticket_seed += 1
        side = str(command["side"])
        price = self.ask if side == "BUY" else self.bid
        sl = float(command.get("stop_loss", 0.0))
        tp = float(command.get("take_profit", 0.0) or 0.0)
        volume = float(command["volume"])
        pos = SimulatedPosition(
            ticket=self.ticket_seed,
            symbol=self.symbol,
            magic=self.magic,
            side=side,
            volume=volume,
            open_price=price,
            stop_loss=sl,
            take_profit=tp,
            current_price=price,
            comment=str(command["command_id"])[:31],
        )
        self.positions[pos.ticket] = pos
        ack = self._base_ack(
            command,
            status="SUCCESS",
            ticket=pos.ticket,
            side=side,
            requested_price=float(command.get("requested_price", price)),
            applied_price=price,
            requested_volume=volume,
            applied_volume=volume,
            requested_stop_loss=sl,
            applied_stop_loss=sl,
            requested_take_profit=tp,
            applied_take_profit=tp,
        )
        return self._write_ack(command, ack)

    def _process_modify(self, command: dict[str, Any]) -> Path:
        ticket = int(command["ticket"])
        pos = self.positions.get(ticket)
        requested_sl = float(command["requested_stop_loss"])
        requested_tp = float(command.get("requested_take_profit", pos.take_profit if pos else 0.0))
        if pos is None:
            ack = self._base_ack(
                command,
                status="REJECTED",
                broker_error_text="MODIFY ticket not found",
                requested_stop_loss=requested_sl,
                applied_stop_loss=0.0,
            )
            return self._write_ack(command, ack)
        previous_sl = pos.stop_loss
        # Reject worsening before apply.
        if pos.side == "BUY" and previous_sl > 0 and requested_sl < previous_sl - self.price_tolerance:
            ack = self._base_ack(
                command,
                status="REJECTED",
                ticket=ticket,
                requested_stop_loss=requested_sl,
                applied_stop_loss=previous_sl,
                broker_error_text="MODIFY would worsen stop loss protection",
            )
            return self._write_ack(command, ack)
        if pos.side == "SELL" and previous_sl > 0 and requested_sl > previous_sl + self.price_tolerance:
            ack = self._base_ack(
                command,
                status="REJECTED",
                ticket=ticket,
                requested_stop_loss=requested_sl,
                applied_stop_loss=previous_sl,
                broker_error_text="MODIFY would worsen stop loss protection",
            )
            return self._write_ack(command, ack)

        pos.stop_loss = requested_sl
        pos.take_profit = requested_tp
        ok = validate_modify_success(
            side=pos.side,
            previous_sl=previous_sl,
            requested_sl=requested_sl,
            applied_sl=pos.stop_loss,
            tolerance=self.price_tolerance,
            order_modify_ok=True,
        )
        status = "SUCCESS" if ok else "FAILED"
        ack = self._base_ack(
            command,
            status=status,
            ticket=ticket,
            side=pos.side,
            requested_stop_loss=requested_sl,
            applied_stop_loss=pos.stop_loss,
            requested_take_profit=requested_tp,
            applied_take_profit=pos.take_profit,
            broker_error_text="" if ok else "applied stop loss failed protection/tolerance check",
        )
        return self._write_ack(command, ack)

    def _process_close(self, command: dict[str, Any]) -> Path:
        ticket = int(command["ticket"])
        pos = self.positions.get(ticket)
        if pos is None:
            ack = self._base_ack(
                command,
                status="SUCCESS",
                ticket=ticket,
                broker_error_text="already closed (reconciled)",
                requested_volume=float(command.get("volume", 0.0)),
                applied_volume=float(command.get("volume", 0.0)),
            )
            return self._write_ack(command, ack)
        price = self.bid if pos.side == "BUY" else self.ask
        volume = float(command.get("volume", pos.volume))
        del self.positions[ticket]
        ack = self._base_ack(
            command,
            status="SUCCESS",
            ticket=ticket,
            side=pos.side,
            requested_price=float(command.get("requested_price", price)),
            applied_price=price,
            requested_volume=volume,
            applied_volume=volume,
        )
        return self._write_ack(command, ack)
