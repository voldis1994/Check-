from __future__ import annotations

import json
from pathlib import Path

import pytest

from checktrader.market_data.loader import parse_market_snapshot
from checktrader.market_data.status import parse_status_snapshot
from tests.protocol.mt4_bridge_simulator import MT4V2BridgeSimulator
from tests.protocol.mt4_v2_shapes import (
    ProtocolShapeError,
    ack_filename,
    command_filename,
    validate_acknowledgement,
    validate_command,
    validate_market_snapshot,
    validate_modify_success,
    validate_status_snapshot,
)


def test_command_and_ack_filenames() -> None:
    assert command_filename(12, "abc") == "12_abc.json"
    assert ack_filename(12, "abc") == "12_abc.ack.json"


def test_modify_success_rule() -> None:
    assert validate_modify_success(
        side="BUY",
        previous_sl=1.1000,
        requested_sl=1.1010,
        applied_sl=1.1010,
        tolerance=0.00001,
        order_modify_ok=True,
    )
    assert not validate_modify_success(
        side="BUY",
        previous_sl=1.1010,
        requested_sl=1.1000,
        applied_sl=1.1000,
        tolerance=0.00001,
        order_modify_ok=True,
    )
    assert validate_modify_success(
        side="SELL",
        previous_sl=1.1020,
        requested_sl=1.1010,
        applied_sl=1.1010,
        tolerance=0.00001,
        order_modify_ok=True,
    )


def test_simulator_exports_parseable_snapshots(tmp_path: Path) -> None:
    sim = MT4V2BridgeSimulator(root=tmp_path)
    market_path, status_path = sim.export_snapshots()
    market = json.loads(market_path.read_text(encoding="utf-8"))
    status = json.loads(status_path.read_text(encoding="utf-8"))
    validate_market_snapshot(market)
    validate_status_snapshot(status)
    parsed_market = parse_market_snapshot(market)
    parsed_status = parse_status_snapshot(status)
    assert parsed_market.protocol_version == "2.0.0"
    assert parsed_status.account_number == "100001"
    assert len(parsed_market.bars_m1) >= 1


def test_simulator_open_modify_close_roundtrip(tmp_path: Path) -> None:
    sim = MT4V2BridgeSimulator(root=tmp_path)
    open_cmd = {
        "protocol_version": "2.0.0",
        "message_type": "command",
        "message_id": "m1",
        "generated_at_utc": "2026-07-22T12:00:00.000Z",
        "source": "python",
        "sequence": 1,
        "command_id": "cmd-open-1",
        "action": "OPEN",
        "symbol": "EURUSD",
        "magic": 19942026,
        "side": "BUY",
        "volume": 0.01,
        "requested_price": 1.10020,
        "stop_loss": 1.09900,
        "take_profit": 1.10300,
        "slippage_points": 3,
        "created_at_utc": "2026-07-22T12:00:00.000Z",
    }
    validate_command(open_cmd)
    sim.write_command(open_cmd)
    acks = sim.process_pending_commands()
    assert len(acks) == 1
    open_ack = json.loads(acks[0].read_text(encoding="utf-8"))
    validate_acknowledgement(open_ack)
    assert open_ack["status"] == "SUCCESS"
    ticket = int(open_ack["ticket"])

    modify_cmd = {
        "protocol_version": "2.0.0",
        "message_type": "command",
        "message_id": "m2",
        "generated_at_utc": "2026-07-22T12:00:01.000Z",
        "source": "python",
        "sequence": 2,
        "command_id": "cmd-mod-1",
        "action": "MODIFY",
        "symbol": "EURUSD",
        "magic": 19942026,
        "ticket": ticket,
        "requested_stop_loss": 1.09950,
        "requested_take_profit": 1.10300,
        "previous_broker_stop_loss": 1.09900,
        "trailing_reason": "be",
        "trailing_step": 0.0,
        "created_at_utc": "2026-07-22T12:00:01.000Z",
        "slippage_points": 3,
    }
    sim.write_command(modify_cmd)
    mod_acks = sim.process_pending_commands()
    mod_ack = json.loads(mod_acks[0].read_text(encoding="utf-8"))
    validate_acknowledgement(mod_ack)
    assert mod_ack["status"] == "SUCCESS"
    assert "requested_stop_loss" in mod_ack and "applied_stop_loss" in mod_ack

    close_cmd = {
        "protocol_version": "2.0.0",
        "message_type": "command",
        "message_id": "m3",
        "generated_at_utc": "2026-07-22T12:00:02.000Z",
        "source": "python",
        "sequence": 3,
        "command_id": "cmd-close-1",
        "action": "CLOSE",
        "symbol": "EURUSD",
        "magic": 19942026,
        "ticket": ticket,
        "volume": 0.01,
        "requested_price": 1.10000,
        "close_reason": "exit",
        "created_at_utc": "2026-07-22T12:00:02.000Z",
        "slippage_points": 3,
    }
    sim.write_command(close_cmd)
    close_acks = sim.process_pending_commands()
    close_ack = json.loads(close_acks[0].read_text(encoding="utf-8"))
    assert close_ack["status"] == "SUCCESS"
    assert ticket not in sim.positions

    # Idempotence: re-writing same command id must not re-open.
    sim.write_command(open_cmd)
    again = sim.process_pending_commands()
    again_ack = json.loads(again[0].read_text(encoding="utf-8"))
    assert again_ack["status"] == "ALREADY_PROCESSED"


def test_close_already_closed_is_reconciled(tmp_path: Path) -> None:
    sim = MT4V2BridgeSimulator(root=tmp_path)
    close_cmd = {
        "protocol_version": "2.0.0",
        "message_type": "command",
        "message_id": "m4",
        "generated_at_utc": "2026-07-22T12:00:00.000Z",
        "source": "python",
        "sequence": 9,
        "command_id": "cmd-close-missing",
        "action": "CLOSE",
        "symbol": "EURUSD",
        "magic": 19942026,
        "ticket": 999999,
        "volume": 0.01,
        "requested_price": 1.1,
        "close_reason": "exit",
        "created_at_utc": "2026-07-22T12:00:00.000Z",
        "slippage_points": 3,
    }
    sim.write_command(close_cmd)
    ack_path = sim.process_pending_commands()[0]
    ack = json.loads(ack_path.read_text(encoding="utf-8"))
    assert ack["status"] == "SUCCESS"
    assert "already closed" in str(ack.get("broker_error_text", "")).lower()


def test_market_missing_field_rejected() -> None:
    with pytest.raises(ProtocolShapeError):
        validate_market_snapshot({"protocol_version": "2.0.0"})
