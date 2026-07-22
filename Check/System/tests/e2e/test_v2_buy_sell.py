"""End-to-end BUY/SELL scenarios with file-bridge mock broker under tmp_path."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from checktrader.application.cycle import run_cycle
from checktrader.domain.enums import OrderAction, PositionState, Side
from checktrader.execution.command_factory import build_close_command, write_command
from checktrader.execution.protocol import atomic_write_json, read_json
from checktrader.observability.reason_codes import ReasonCode
from checktrader.state.store import InstanceRuntimeState, load_instance_state
from tests.fixtures.candles import candle_dicts, sequential_m1, synthesize_buy_setup_m1, synthesize_sell_setup_m1
from tests.fixtures.helpers import (
    config_for_tmp,
    make_market_snapshot,
    make_pending,
    make_status_snapshot,
    prepare_bridge,
)

NOW = "2026-03-01T12:00:00Z"


@dataclass
class MockBroker:
    ticket_seq: int = 5000
    position: dict | None = None

    def process_commands(self, bridge: Path) -> None:
        ack_dir = bridge / "acknowledgements"
        for path in sorted((bridge / "commands").glob("*.json")):
            cmd = read_json(path)
            cid = str(cmd["command_id"])
            action = cmd["action"]
            if action == "OPEN":
                self.ticket_seq += 1
                self.position = {
                    "ticket": self.ticket_seq,
                    "symbol": cmd["symbol"],
                    "magic": cmd["magic"],
                    "side": cmd["side"],
                    "volume": cmd["volume"],
                    "open_time_utc": NOW,
                    "open_price": float(cmd["requested_price"]),
                    "stop_loss": float(cmd["stop_loss"]),
                    "take_profit": float(cmd.get("take_profit") or 0.0),
                    "current_price": float(cmd["requested_price"]),
                    "profit": 0.0,
                    "swap": 0.0,
                    "commission": 0.0,
                    "net_profit": 0.0,
                }
                atomic_write_json(
                    ack_dir / f"{cmd['sequence']}_{cid}.ack.json",
                    {
                        "command_id": cid,
                        "action": "OPEN",
                        "status": "SUCCESS",
                        "ticket": self.ticket_seq,
                        "symbol": cmd["symbol"],
                        "magic": cmd["magic"],
                        "account_number": cmd.get("account_number", "999"),
                        "server": cmd.get("server", "Demo-Server"),
                        "instance_id": cmd.get("instance_id", "EURUSD_M1_PRIMARY"),
                        "applied_price": cmd["requested_price"],
                        "applied_volume": cmd["volume"],
                        "applied_stop_loss": cmd["stop_loss"],
                        "applied_take_profit": cmd.get("take_profit"),
                    },
                )
            elif action == "MODIFY" and self.position is not None:
                applied = float(cmd["requested_stop_loss"])
                previous = float(self.position["stop_loss"])
                self.position["stop_loss"] = applied
                atomic_write_json(
                    ack_dir / f"{cmd['sequence']}_{cid}.ack.json",
                    {
                        "command_id": cid,
                        "action": "MODIFY",
                        "status": "SUCCESS",
                        "ticket": self.position["ticket"],
                        "symbol": cmd["symbol"],
                        "magic": cmd["magic"],
                        "account_number": cmd.get("account_number", "999"),
                        "server": cmd.get("server", "Demo-Server"),
                        "instance_id": cmd.get("instance_id", "EURUSD_M1_PRIMARY"),
                        "applied_stop_loss": applied,
                        "requested_stop_loss": applied,
                        "previous_stop_loss": previous,
                    },
                )
            elif action == "CLOSE":
                ticket = self.position["ticket"] if self.position else cmd.get("ticket")
                self.position = None
                atomic_write_json(
                    ack_dir / f"{cmd['sequence']}_{cid}.ack.json",
                    {
                        "command_id": cid,
                        "action": "CLOSE",
                        "status": "SUCCESS",
                        "ticket": ticket,
                        "symbol": cmd["symbol"],
                        "magic": cmd["magic"],
                        "account_number": cmd.get("account_number", "999"),
                        "server": cmd.get("server", "Demo-Server"),
                        "instance_id": cmd.get("instance_id", "EURUSD_M1_PRIMARY"),
                    },
                )
            path.unlink()


def test_e2e_buy_open_be_grid(tmp_path: Path) -> None:
    bridge = prepare_bridge(tmp_path)
    config = config_for_tmp(tmp_path, strategy={"setup_expiry_bars": 200})
    broker = MockBroker()
    state = InstanceRuntimeState()

    bars = synthesize_buy_setup_m1(trigger=True)
    last = bars[-1]
    market = make_market_snapshot(
        bars_m1=candle_dicts(bars),
        generated_at_utc=NOW,
        bid=last.close - 0.00010,
        ask=last.close,
    )
    status = make_status_snapshot(generated_at_utc=NOW)
    r1 = run_cycle(config=config, state=state, market=market, status=status, bridge_root=bridge, now_utc=NOW)
    assert r1.reason is ReasonCode.OPEN_SENT
    broker.process_commands(bridge)

    # Confirm OPEN with broker position present in status
    assert broker.position is not None
    status2 = make_status_snapshot(generated_at_utc=NOW, positions=[dict(broker.position)])
    run_cycle(config=config, state=state, market=market, status=status2, bridge_root=bridge, now_utc=NOW)
    assert state.position.state is PositionState.OPEN
    assert state.position.ticket is not None

    # Broker shows profitable position → BE modify
    broker.position["profit"] = 0.70
    broker.position["net_profit"] = 0.70
    broker.position["current_price"] = last.close + 0.00050
    market_be = make_market_snapshot(
        bars_m1=candle_dicts(sequential_m1(n=40)),
        generated_at_utc=NOW,
        bid=broker.position["open_price"] + 0.00060,
        ask=broker.position["open_price"] + 0.00080,
    )
    status_be = make_status_snapshot(generated_at_utc=NOW, positions=[dict(broker.position)])
    r_be = run_cycle(config=config, state=state, market=market_be, status=status_be, bridge_root=bridge, now_utc=NOW)
    assert r_be.action is OrderAction.MODIFY
    broker.process_commands(bridge)
    status_be2 = make_status_snapshot(generated_at_utc=NOW, positions=[dict(broker.position)])
    run_cycle(config=config, state=state, market=market_be, status=status_be2, bridge_root=bridge, now_utc=NOW)
    assert state.trailing.be_confirmed is True

    # If BE confirm cycle already queued a grid MODIFY, settle it first.
    if state.pending_command_id is not None:
        broker.process_commands(bridge)
        status_settle = make_status_snapshot(generated_at_utc=NOW, positions=[dict(broker.position)])
        run_cycle(config=config, state=state, market=market_be, status=status_settle, bridge_root=bridge, now_utc=NOW)

    # Move price for an additional grid step
    broker.position["stop_loss"] = float(
        state.trailing.confirmed_stop_loss or state.trailing.confirmed_be_sl or broker.position["stop_loss"]
    )
    broker.position["profit"] = 2.0
    broker.position["net_profit"] = 2.0
    prev_sl = float(broker.position["stop_loss"])
    market_grid = make_market_snapshot(
        bars_m1=candle_dicts(sequential_m1(n=40)),
        generated_at_utc=NOW,
        bid=broker.position["open_price"] + 0.00200,
        ask=broker.position["open_price"] + 0.00220,
    )
    status_grid = make_status_snapshot(generated_at_utc=NOW, positions=[dict(broker.position)])
    r_grid = run_cycle(
        config=config, state=state, market=market_grid, status=status_grid, bridge_root=bridge, now_utc=NOW
    )
    assert r_grid.action is OrderAction.MODIFY
    broker.process_commands(bridge)
    status_grid2 = make_status_snapshot(generated_at_utc=NOW, positions=[dict(broker.position)])
    run_cycle(config=config, state=state, market=market_grid, status=status_grid2, bridge_root=bridge, now_utc=NOW)
    assert state.trailing.confirmed_stop_loss is not None
    assert state.trailing.confirmed_stop_loss > prev_sl

    # Persist across "restart"
    state_path = tmp_path / "runtime" / "state" / "instance.json"
    loaded = load_instance_state(state_path)
    assert loaded.trailing.be_confirmed is True
    assert loaded.position.ticket == state.position.ticket


def test_e2e_sell_open_and_close(tmp_path: Path) -> None:
    bridge = prepare_bridge(tmp_path)
    config = config_for_tmp(tmp_path, strategy={"setup_expiry_bars": 200})
    broker = MockBroker()
    state = InstanceRuntimeState()

    bars = synthesize_sell_setup_m1(trigger=True)
    last = bars[-1]
    market = make_market_snapshot(
        bars_m1=candle_dicts(bars),
        generated_at_utc=NOW,
        bid=last.close,
        ask=last.close + 0.00010,
    )
    status = make_status_snapshot(generated_at_utc=NOW)
    r1 = run_cycle(config=config, state=state, market=market, status=status, bridge_root=bridge, now_utc=NOW)
    assert r1.reason is ReasonCode.OPEN_SENT
    assert r1.action is OrderAction.OPEN
    cmd = read_json(next((bridge / "commands").glob("*.json")))
    assert cmd["side"] == "SELL"
    broker.process_commands(bridge)
    assert broker.position is not None
    status_open = make_status_snapshot(generated_at_utc=NOW, positions=[dict(broker.position)])
    run_cycle(config=config, state=state, market=market, status=status_open, bridge_root=bridge, now_utc=NOW)
    assert state.position.side is Side.SELL
    assert state.position.state is PositionState.OPEN

    # Force close via synthetic CLOSE command path: mark CLOSE_PENDING manually after writing close
    close_cmd = build_close_command(
        ticket=broker.position["ticket"],
        symbol="EURUSD",
        magic=19942026,
        volume=0.01,
        requested_price=last.close,
        close_reason="TEST",
        created_at_utc=NOW,
        account_number="999",
        server="Demo-Server",
        instance_id=config.runtime.instance_id,
    )
    write_command(bridge / "commands", close_cmd, sequence=state.next_sequence())
    state.pending = make_pending(
        command_id=close_cmd.command_id,
        action="CLOSE",
        ticket=close_cmd.ticket,
        instance_id=config.runtime.instance_id,
    )
    state.position.state = PositionState.CLOSE_PENDING
    broker.process_commands(bridge)
    status_flat = make_status_snapshot(generated_at_utc=NOW, positions=[])
    run_cycle(config=config, state=state, market=market, status=status_flat, bridge_root=bridge, now_utc=NOW)
    assert state.position.state is PositionState.FLAT
    assert state.last_reason == ReasonCode.CLOSE_CONFIRMED.value
