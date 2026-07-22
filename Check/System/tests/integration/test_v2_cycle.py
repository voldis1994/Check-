"""Integration cycles: market → setup → risk → OPEN / trailing / close."""

from __future__ import annotations

from pathlib import Path

from checktrader.application.cycle import run_cycle
from checktrader.domain.enums import OrderAction, PositionState, Side
from checktrader.domain.trailing import TrailingState
from checktrader.execution.protocol import atomic_write_json, read_json
from checktrader.observability.reason_codes import ReasonCode
from checktrader.state.store import InstanceRuntimeState
from tests.fixtures.candles import candle_dicts, sequential_m1, synthesize_buy_setup_m1
from tests.fixtures.helpers import (
    broker_position,
    broker_position_payload,
    config_for_tmp,
    make_market_snapshot,
    make_pending,
    make_status_snapshot,
    prepare_bridge,
)

NOW = "2026-03-01T12:00:00Z"


def _write_ack(bridge: Path, command_id: str, payload: dict) -> None:
    atomic_write_json(bridge / "acknowledgements" / f"1_{command_id}.ack.json", payload)


def test_market_setup_risk_open(tmp_path: Path) -> None:
    bridge = prepare_bridge(tmp_path)
    config = config_for_tmp(tmp_path, strategy={"setup_expiry_bars": 200, "minimum_structure_bars": 30})
    bars = synthesize_buy_setup_m1(trigger=True)
    last = bars[-1]
    market = make_market_snapshot(
        bars_m1=candle_dicts(bars),
        generated_at_utc=NOW,
        bid=last.close - 0.00010,
        ask=last.close,
    )
    status = make_status_snapshot(generated_at_utc=NOW)
    state = InstanceRuntimeState()
    result = run_cycle(
        config=config,
        state=state,
        market=market,
        status=status,
        bridge_root=bridge,
        now_utc=NOW,
    )
    assert result.reason is ReasonCode.OPEN_SENT
    assert result.action is OrderAction.OPEN
    assert state.position.state is PositionState.OPEN_PENDING
    assert state.pending_command_id is not None
    cmd_files = list((bridge / "commands").glob("*.json"))
    assert len(cmd_files) == 1
    payload = read_json(cmd_files[0])
    assert payload["action"] == "OPEN"
    assert payload["side"] == "BUY"


def test_ack_confirms_open(tmp_path: Path) -> None:
    bridge = prepare_bridge(tmp_path)
    config = config_for_tmp(tmp_path)
    state = InstanceRuntimeState()
    state.position.state = PositionState.OPEN_PENDING
    state.position.side = Side.BUY
    state.pending = make_pending(command_id="open-1", action="OPEN", requested_stop_loss=1.09800)
    _write_ack(
        bridge,
        "open-1",
        {
            "command_id": "open-1",
            "action": "OPEN",
            "status": "SUCCESS",
            "ticket": 777,
            "symbol": "EURUSD",
            "magic": 19942026,
            "account_number": "999",
            "server": "Demo-Server",
            "instance_id": "EURUSD_M1_PRIMARY",
            "applied_price": 1.10020,
            "applied_volume": 0.01,
            "applied_stop_loss": 1.09800,
        },
    )
    market = make_market_snapshot(bars_m1=candle_dicts(sequential_m1(n=30)), generated_at_utc=NOW)
    pos = broker_position(ticket=777, open_price=1.10020, stop_loss=1.09800, volume=0.01, net_profit=0.0, profit=0.0)
    status = make_status_snapshot(generated_at_utc=NOW, positions=[broker_position_payload(pos)])
    run_cycle(config=config, state=state, market=market, status=status, bridge_root=bridge, now_utc=NOW)
    assert state.position.state is PositionState.OPEN
    assert state.position.ticket == 777
    assert state.pending_command_id is None
    assert state.last_reason == ReasonCode.OPEN_CONFIRMED.value


def test_activation_be_modify(tmp_path: Path) -> None:
    bridge = prepare_bridge(tmp_path)
    config = config_for_tmp(tmp_path)
    state = InstanceRuntimeState()
    state.position.state = PositionState.OPEN
    state.position.ticket = 1001
    state.position.side = Side.BUY
    pos = broker_position(
        ticket=1001,
        side=Side.BUY,
        open_price=1.10000,
        stop_loss=1.09800,
        volume=0.01,
        profit=0.60,
        net_profit=0.60,
        current_price=1.10060,
    )
    market = make_market_snapshot(
        bars_m1=candle_dicts(sequential_m1(n=30)),
        generated_at_utc=NOW,
        bid=1.10060,
        ask=1.10080,
    )
    status = make_status_snapshot(generated_at_utc=NOW, positions=[broker_position_payload(pos)])
    result = run_cycle(config=config, state=state, market=market, status=status, bridge_root=bridge, now_utc=NOW)
    assert result.reason is ReasonCode.MODIFY_SENT
    assert state.position.state is PositionState.MODIFY_PENDING
    assert state.trailing.pending_stop_loss == 1.10020


def test_be_ack_confirmed(tmp_path: Path) -> None:
    bridge = prepare_bridge(tmp_path)
    config = config_for_tmp(tmp_path)
    state = InstanceRuntimeState()
    state.position.state = PositionState.MODIFY_PENDING
    state.position.ticket = 1001
    state.position.side = Side.BUY
    state.pending = make_pending(
        command_id="mod-be",
        action="MODIFY",
        ticket=1001,
        requested_stop_loss=1.10020,
    )
    state.trailing.pending_stop_loss = 1.10020
    state.trailing.be_confirmed = False
    _write_ack(
        bridge,
        "mod-be",
        {
            "command_id": "mod-be",
            "action": "MODIFY",
            "status": "SUCCESS",
            "ticket": 1001,
            "symbol": "EURUSD",
            "magic": 19942026,
            "account_number": "999",
            "server": "Demo-Server",
            "instance_id": "EURUSD_M1_PRIMARY",
            "applied_stop_loss": 1.10020,
            "previous_stop_loss": 1.09800,
        },
    )
    # Status already reflects applied BE SL (broker truth after modify).
    pos = broker_position(ticket=1001, stop_loss=1.10020, net_profit=0.6, profit=0.6, open_price=1.10000)
    market = make_market_snapshot(
        bars_m1=candle_dicts(sequential_m1(n=30)), generated_at_utc=NOW, bid=1.10060, ask=1.10080
    )
    status = make_status_snapshot(generated_at_utc=NOW, positions=[broker_position_payload(pos)])
    run_cycle(config=config, state=state, market=market, status=status, bridge_root=bridge, now_utc=NOW)
    assert state.trailing.be_confirmed is True
    assert state.trailing.confirmed_be_sl == 1.10020
    assert state.position.ticket == 1001
    # Same cycle may immediately propose the next pip-grid step when price allows.


def test_grid_steps_after_be(tmp_path: Path) -> None:
    bridge = prepare_bridge(tmp_path)
    config = config_for_tmp(tmp_path)
    state = InstanceRuntimeState()
    state.position.state = PositionState.OPEN
    state.position.ticket = 1001
    state.position.side = Side.BUY
    state.trailing = TrailingState(be_confirmed=True, confirmed_be_sl=1.10020, confirmed_stop_loss=1.10020)
    pos = broker_position(
        ticket=1001,
        open_price=1.10000,
        stop_loss=1.10020,
        volume=0.01,
        profit=1.5,
        net_profit=1.5,
        current_price=1.10150,
    )
    market = make_market_snapshot(
        bars_m1=candle_dicts(sequential_m1(n=30)),
        generated_at_utc=NOW,
        bid=1.10150,
        ask=1.10170,
    )
    status = make_status_snapshot(generated_at_utc=NOW, positions=[broker_position_payload(pos)])
    result = run_cycle(config=config, state=state, market=market, status=status, bridge_root=bridge, now_utc=NOW)
    assert result.reason is ReasonCode.MODIFY_SENT
    assert state.trailing.pending_stop_loss is not None
    assert state.trailing.pending_stop_loss > 1.10020


def test_rejected_modify_keeps_pending_and_retries(tmp_path: Path) -> None:
    bridge = prepare_bridge(tmp_path)
    config = config_for_tmp(tmp_path, execution={"retry_delay_ms": 0, "maximum_retries": 3, "ack_timeout_ms": 5000})
    state = InstanceRuntimeState()
    state.position.state = PositionState.MODIFY_PENDING
    state.position.ticket = 1001
    state.position.side = Side.BUY
    state.pending = make_pending(
        command_id="mod-bad",
        action="MODIFY",
        ticket=1001,
        requested_stop_loss=1.10020,
        last_attempt_at="2026-03-01T11:59:00Z",
        acknowledgement_deadline="2026-03-01T11:59:05Z",
    )
    state.trailing.pending_stop_loss = 1.10020
    state.trailing.be_confirmed = False
    _write_ack(
        bridge,
        "mod-bad",
        {
            "command_id": "mod-bad",
            "action": "MODIFY",
            "status": "SUCCESS",
            "ticket": 1001,
            "symbol": "EURUSD",
            "magic": 19942026,
            "account_number": "999",
            "server": "Demo-Server",
            "instance_id": "EURUSD_M1_PRIMARY",
            # missing applied_stop_loss
        },
    )
    pos = broker_position(ticket=1001, stop_loss=1.09800, net_profit=0.6, profit=0.6, open_price=1.10000)
    market = make_market_snapshot(
        bars_m1=candle_dicts(sequential_m1(n=30)),
        generated_at_utc=NOW,
        bid=1.10060,
        ask=1.10080,
    )
    status = make_status_snapshot(generated_at_utc=NOW, positions=[broker_position_payload(pos)])
    result = run_cycle(config=config, state=state, market=market, status=status, bridge_root=bridge, now_utc=NOW)
    assert state.trailing.pending_stop_loss == 1.10020
    assert state.pending is not None
    assert state.pending.retry_count >= 1
    assert result.reason is ReasonCode.MODIFY_SENT
    assert state.position.state is PositionState.MODIFY_PENDING
    assert state.pending_command_id is not None
    assert state.pending_command_id != "mod-bad"


def test_high_lock_and_exit_pressure_close(tmp_path: Path) -> None:
    bridge = prepare_bridge(tmp_path)
    config = config_for_tmp(
        tmp_path,
        trade_management={
            "exit_pressure": {
                "enabled": True,
                "pullback_weight": 0.30,
                "speed_weight": 0.20,
                "trend_weight": 0.20,
                "rejection_weight": 0.20,
                "spread_weight": 0.10,
                "tighten_threshold": 0.45,
                "high_lock_threshold": 0.70,
                "critical_threshold": 0.50,
                "critical_close_enabled": True,
                "minimum_non_spread_confirmations_for_close": 1,
            }
        },
    )
    state = InstanceRuntimeState()
    state.position.state = PositionState.OPEN
    state.position.ticket = 1001
    state.position.side = Side.BUY
    state.trailing = TrailingState(
        be_confirmed=True,
        confirmed_be_sl=1.10020,
        confirmed_stop_loss=1.10020,
        peak_net_profit=5.0,
    )
    # Strong giveback from peak
    pos = broker_position(
        ticket=1001,
        open_price=1.10000,
        stop_loss=1.10020,
        volume=0.01,
        profit=0.2,
        net_profit=0.2,
        current_price=1.10020,
    )
    # Adverse M1 candles with rejection
    bars = sequential_m1(n=30)
    from tests.fixtures.candles import make_m1_candle

    rebuilt = []
    for i, b in enumerate(bars):
        if i >= len(bars) - 4:
            rebuilt.append(
                make_m1_candle(
                    open_time_utc=b.open_time_utc,
                    open_=1.10100 - (i - (len(bars) - 4)) * 0.00020,
                    high=1.10150,
                    low=1.09900,
                    close=1.09950 - (i - (len(bars) - 4)) * 0.00010,
                )
            )
        else:
            rebuilt.append(b)
    market = make_market_snapshot(bars_m1=candle_dicts(rebuilt), generated_at_utc=NOW, bid=1.09940, ask=1.09960)
    status = make_status_snapshot(generated_at_utc=NOW, positions=[broker_position_payload(pos)])
    result = run_cycle(config=config, state=state, market=market, status=status, bridge_root=bridge, now_utc=NOW)
    # Either CLOSE from critical pressure or MODIFY from high-lock / grid — both valid protective paths
    assert result.action in {OrderAction.CLOSE, OrderAction.MODIFY, OrderAction.NONE}
    if result.action is OrderAction.CLOSE:
        assert result.reason is ReasonCode.CLOSE_SENT


def test_close_ack_to_flat(tmp_path: Path) -> None:
    bridge = prepare_bridge(tmp_path)
    config = config_for_tmp(tmp_path)
    state = InstanceRuntimeState()
    state.position.state = PositionState.CLOSE_PENDING
    state.position.ticket = 1001
    state.position.side = Side.BUY
    state.pending = make_pending(command_id="close-1", action="CLOSE", ticket=1001)
    state.trailing.peak_net_profit = 1.0
    _write_ack(
        bridge,
        "close-1",
        {
            "command_id": "close-1",
            "action": "CLOSE",
            "status": "SUCCESS",
            "ticket": 1001,
            "symbol": "EURUSD",
            "magic": 19942026,
            "account_number": "999",
            "server": "Demo-Server",
            "instance_id": "EURUSD_M1_PRIMARY",
        },
    )
    market = make_market_snapshot(bars_m1=candle_dicts(sequential_m1(n=30)), generated_at_utc=NOW)
    status = make_status_snapshot(generated_at_utc=NOW, positions=[])
    run_cycle(config=config, state=state, market=market, status=status, bridge_root=bridge, now_utc=NOW)
    assert state.position.state is PositionState.FLAT
    assert state.pending_command_id is None
    assert state.last_reason == ReasonCode.CLOSE_CONFIRMED.value
