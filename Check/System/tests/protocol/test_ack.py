"""ACK parser / validator tests."""

from __future__ import annotations

import pytest

from checktrader.domain.enums import ExecutionStatus, OrderAction, Side
from checktrader.domain.errors import ValidationError
from checktrader.execution.ack_parser import parse_acknowledgement, require_open_fill, validate_modify_ack
from checktrader.execution.command_factory import build_modify_command, build_open_command
from checktrader.observability.reason_codes import ReasonCode


def test_open_success_requires_fill_fields() -> None:
    ack = parse_acknowledgement(
        {
            "command_id": "cmd-1",
            "action": "OPEN",
            "status": "SUCCESS",
            "ticket": 42,
            "symbol": "EURUSD",
            "magic": 19942026,
            "applied_price": 1.10020,
            "applied_volume": 0.01,
            "applied_stop_loss": 1.09800,
        }
    )
    assert ack.status is ExecutionStatus.ACCEPTED
    require_open_fill(ack)


def test_open_missing_fill_rejected() -> None:
    ack = parse_acknowledgement(
        {
            "command_id": "cmd-1",
            "action": "OPEN",
            "status": "SUCCESS",
            "ticket": 42,
            "symbol": "EURUSD",
            "magic": 19942026,
        }
    )
    with pytest.raises(ValidationError):
        require_open_fill(ack)


def _modify_cmd(command_id: str = "mod-1"):
    from dataclasses import replace

    cmd = build_modify_command(
        ticket=1001,
        symbol="EURUSD",
        magic=19942026,
        requested_stop_loss=1.10020,
        requested_take_profit=0.0,
        previous_broker_stop_loss=1.09800,
        trailing_reason="BE_CALCULATED",
        trailing_step=3.0,
        created_at_utc="2026-03-01T12:00:00Z",
    )
    return replace(cmd, command_id=command_id)


def test_modify_success_with_applied_sl() -> None:
    cmd = _modify_cmd()
    ack = parse_acknowledgement(
        {
            "command_id": cmd.command_id,
            "action": "MODIFY",
            "status": "SUCCESS",
            "ticket": 1001,
            "symbol": "EURUSD",
            "magic": 19942026,
            "applied_stop_loss": 1.10020,
        }
    )
    assert (
        validate_modify_ack(
            ack, cmd, open_ticket=1001, symbol="EURUSD", magic=19942026, pending_sl=1.10020, tolerance=0.00002
        )
        is None
    )


def test_modify_without_applied_sl_rejected() -> None:
    cmd = _modify_cmd()
    ack = parse_acknowledgement(
        {
            "command_id": cmd.command_id,
            "action": "MODIFY",
            "status": "SUCCESS",
            "ticket": 1001,
            "symbol": "EURUSD",
            "magic": 19942026,
        }
    )
    assert (
        validate_modify_ack(
            ack, cmd, open_ticket=1001, symbol="EURUSD", magic=19942026, pending_sl=1.10020, tolerance=0.00002
        )
        is ReasonCode.TRAILING_ACK_SL_MISMATCH
    )


def test_wrong_ticket_command_magic() -> None:
    cmd = _modify_cmd("mod-x")
    ack = parse_acknowledgement(
        {
            "command_id": "other",
            "action": "MODIFY",
            "status": "SUCCESS",
            "ticket": 999,
            "symbol": "EURUSD",
            "magic": 1,
            "applied_stop_loss": 1.10020,
        }
    )
    assert (
        validate_modify_ack(
            ack, cmd, open_ticket=1001, symbol="EURUSD", magic=19942026, pending_sl=1.10020, tolerance=0.00002
        )
        is ReasonCode.TRAILING_ACK_SL_MISMATCH
    )


def test_sl_mismatch() -> None:
    cmd = _modify_cmd()
    ack = parse_acknowledgement(
        {
            "command_id": cmd.command_id,
            "action": "MODIFY",
            "status": "SUCCESS",
            "ticket": 1001,
            "symbol": "EURUSD",
            "magic": 19942026,
            "applied_stop_loss": 1.10050,
        }
    )
    assert (
        validate_modify_ack(
            ack, cmd, open_ticket=1001, symbol="EURUSD", magic=19942026, pending_sl=1.10020, tolerance=0.00002
        )
        is ReasonCode.TRAILING_ACK_SL_MISMATCH
    )


def test_close_ack_parses() -> None:
    ack = parse_acknowledgement(
        {
            "command_id": "c1",
            "action": "CLOSE",
            "status": "SUCCESS",
            "ticket": 1001,
            "symbol": "EURUSD",
            "magic": 19942026,
        }
    )
    assert ack.action is OrderAction.CLOSE
    assert ack.status is ExecutionStatus.ACCEPTED


def test_open_command_factory_fields() -> None:
    cmd = build_open_command(
        symbol="EURUSD",
        magic=19942026,
        side=Side.BUY,
        volume=0.01,
        requested_price=1.10020,
        stop_loss=1.09800,
        take_profit=1.10300,
        setup_id="s1",
        setup_fingerprint="fp",
        created_at_utc="2026-03-01T12:00:00Z",
    )
    assert cmd.action is OrderAction.OPEN
    assert cmd.volume == 0.01
