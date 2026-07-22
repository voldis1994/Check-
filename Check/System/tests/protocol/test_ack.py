"""ACK parser / validator tests."""

from __future__ import annotations

from checktrader.domain.enums import ExecutionStatus, OrderAction, Side
from checktrader.domain.execution import PendingCommandState
from checktrader.domain.orders import BrokerPosition
from checktrader.execution.ack_parser import (
    parse_acknowledgement,
    validate_close_ack,
    validate_modify_ack,
    validate_open_ack,
)
from checktrader.execution.command_factory import build_modify_command, build_open_command
from checktrader.observability.reason_codes import ReasonCode


def _pending_modify(**kwargs: object) -> PendingCommandState:
    base = dict(
        command_id="mod-1",
        action=OrderAction.MODIFY,
        account_number="999",
        server="Demo-Server",
        instance_id="EURUSD_M1_PRIMARY",
        symbol="EURUSD",
        magic=19942026,
        ticket=1001,
        requested_stop_loss=1.10020,
    )
    base.update(kwargs)
    return PendingCommandState(**base)  # type: ignore[arg-type]


def _pending_open(**kwargs: object) -> PendingCommandState:
    base = dict(
        command_id="cmd-1",
        action=OrderAction.OPEN,
        account_number="999",
        server="Demo-Server",
        instance_id="EURUSD_M1_PRIMARY",
        symbol="EURUSD",
        magic=19942026,
        requested_volume=0.01,
        requested_stop_loss=1.09800,
    )
    base.update(kwargs)
    return PendingCommandState(**base)  # type: ignore[arg-type]


def _broker(**kwargs: object) -> BrokerPosition:
    base = dict(
        ticket=1001,
        symbol="EURUSD",
        magic=19942026,
        side=Side.BUY,
        volume=0.01,
        open_time_utc="2026-03-01T11:00:00Z",
        open_price=1.10020,
        stop_loss=1.10020,
        take_profit=0.0,
        current_price=1.10050,
        profit=0.5,
        swap=0.0,
        commission=0.0,
        net_profit=0.5,
    )
    base.update(kwargs)
    return BrokerPosition(**base)  # type: ignore[arg-type]


def test_open_success_requires_broker_position() -> None:
    pending = _pending_open()
    ack = parse_acknowledgement(
        {
            "command_id": "cmd-1",
            "action": "OPEN",
            "status": "SUCCESS",
            "ticket": 42,
            "symbol": "EURUSD",
            "magic": 19942026,
            "account_number": "999",
            "server": "Demo-Server",
            "instance_id": "EURUSD_M1_PRIMARY",
            "applied_price": 1.10020,
            "applied_volume": 0.01,
            "applied_stop_loss": 1.09800,
        }
    )
    assert ack.status is ExecutionStatus.ACCEPTED
    assert validate_open_ack(ack, pending, broker_pos=None) is ReasonCode.RECONCILIATION_REQUIRED
    pos = _broker(ticket=42, stop_loss=1.09800)
    assert validate_open_ack(ack, pending, broker_pos=pos) is None


def test_open_missing_fill_rejected() -> None:
    pending = _pending_open()
    ack = parse_acknowledgement(
        {
            "command_id": "cmd-1",
            "action": "OPEN",
            "status": "SUCCESS",
            "ticket": 42,
            "symbol": "EURUSD",
            "magic": 19942026,
            "account_number": "999",
        }
    )
    assert validate_open_ack(ack, pending, broker_pos=_broker(ticket=42)) is ReasonCode.OPEN_REJECTED


def test_modify_success_with_applied_sl() -> None:
    pending = _pending_modify()
    ack = parse_acknowledgement(
        {
            "command_id": "mod-1",
            "action": "MODIFY",
            "status": "SUCCESS",
            "ticket": 1001,
            "symbol": "EURUSD",
            "magic": 19942026,
            "account_number": "999",
            "applied_stop_loss": 1.10020,
            "previous_stop_loss": 1.09800,
        }
    )
    assert (
        validate_modify_ack(ack, pending, side=Side.BUY, broker_pos=_broker(stop_loss=1.10020), tolerance=0.00002)
        is None
    )


def test_modify_without_applied_sl_rejected() -> None:
    pending = _pending_modify()
    ack = parse_acknowledgement(
        {
            "command_id": "mod-1",
            "action": "MODIFY",
            "status": "SUCCESS",
            "ticket": 1001,
            "symbol": "EURUSD",
            "magic": 19942026,
            "account_number": "999",
        }
    )
    assert (
        validate_modify_ack(ack, pending, side=Side.BUY, broker_pos=_broker(), tolerance=0.00002)
        is ReasonCode.TRAILING_ACK_SL_MISMATCH
    )


def test_wrong_identity_rejected() -> None:
    pending = _pending_modify()
    ack = parse_acknowledgement(
        {
            "command_id": "other",
            "action": "MODIFY",
            "status": "SUCCESS",
            "ticket": 999,
            "symbol": "EURUSD",
            "magic": 1,
            "account_number": "111",
            "applied_stop_loss": 1.10020,
        }
    )
    assert (
        validate_modify_ack(ack, pending, side=Side.BUY, broker_pos=_broker(), tolerance=0.00002)
        is ReasonCode.TRAILING_ACK_SL_MISMATCH
    )


def test_failed_close_ack_does_not_validate_flat() -> None:
    pending = PendingCommandState(
        command_id="c1",
        action=OrderAction.CLOSE,
        account_number="999",
        server="Demo-Server",
        instance_id="EURUSD_M1_PRIMARY",
        symbol="EURUSD",
        magic=19942026,
        ticket=1001,
    )
    ack = parse_acknowledgement(
        {
            "command_id": "c1",
            "action": "CLOSE",
            "status": "FAILED",
            "ticket": 1001,
            "symbol": "EURUSD",
            "magic": 19942026,
            "account_number": "999",
        }
    )
    assert validate_close_ack(ack, pending, broker_pos=_broker()) is ReasonCode.CLOSE_REJECTED
    ack_ok = parse_acknowledgement(
        {
            "command_id": "c1",
            "action": "CLOSE",
            "status": "SUCCESS",
            "ticket": 1001,
            "symbol": "EURUSD",
            "magic": 19942026,
            "account_number": "999",
        }
    )
    assert validate_close_ack(ack_ok, pending, broker_pos=_broker()) is ReasonCode.RECONCILIATION_REQUIRED
    assert validate_close_ack(ack_ok, pending, broker_pos=None) is None


def test_open_command_includes_identity_and_zero_tp() -> None:
    cmd = build_open_command(
        symbol="EURUSD",
        magic=19942026,
        side=Side.BUY,
        volume=0.01,
        requested_price=1.10020,
        stop_loss=1.09800,
        take_profit=0.0,
        setup_id="s1",
        setup_fingerprint="fp",
        created_at_utc="2026-03-01T12:00:00Z",
        account_number="999",
        server="Demo-Server",
        instance_id="EURUSD_M1_PRIMARY",
    )
    assert cmd.action is OrderAction.OPEN
    assert cmd.take_profit == 0.0
    assert cmd.account_number == "999"
    assert cmd.server == "Demo-Server"


def test_modify_command_includes_identity() -> None:
    cmd = build_modify_command(
        ticket=1001,
        symbol="EURUSD",
        magic=19942026,
        requested_stop_loss=1.10020,
        requested_take_profit=0.0,
        previous_broker_stop_loss=1.09800,
        trailing_reason="BE",
        trailing_step=3.0,
        created_at_utc="2026-03-01T12:00:00Z",
        account_number="999",
        server="Demo-Server",
        instance_id="EURUSD_M1_PRIMARY",
    )
    assert cmd.instance_id == "EURUSD_M1_PRIMARY"
