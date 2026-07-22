"""Strict acceptance tests for pending command, identity, snapshots, TP, aggregation."""

from __future__ import annotations

from pathlib import Path

from checktrader.application.cycle import run_cycle
from checktrader.domain.enums import PositionState, Side
from checktrader.domain.market import Candle
from checktrader.execution.command_factory import build_open_command, command_to_payload
from checktrader.execution.protocol import atomic_write_json, read_json
from checktrader.execution.snapshot_select import select_latest_snapshot
from checktrader.market_data.aggregator import aggregate_timeframe
from checktrader.observability.reason_codes import ReasonCode
from checktrader.risk.engine import approve_order
from checktrader.state.store import InstanceRuntimeState, load_instance_state, save_instance_state
from checktrader.strategy.engine import run_strategy
from tests.fixtures.candles import candle_dicts, make_m1_candle, sequential_m1, synthesize_buy_setup_m1
from tests.fixtures.helpers import (
    EURUSD_SPECS,
    broker_position,
    broker_position_payload,
    config_for_tmp,
    load_test_config,
    make_market_snapshot,
    make_pending,
    make_status_snapshot,
    prepare_bridge,
)

NOW = "2026-03-01T12:00:00Z"
LATER = "2026-03-01T12:00:10Z"


def _ack(bridge: Path, command_id: str, payload: dict) -> None:
    atomic_write_json(bridge / "acknowledgements" / f"1_{command_id}.ack.json", payload)


def test_failed_close_ack_does_not_leave_flat(tmp_path: Path) -> None:
    bridge = prepare_bridge(tmp_path)
    config = config_for_tmp(tmp_path)
    state = InstanceRuntimeState()
    state.position.state = PositionState.CLOSE_PENDING
    state.position.ticket = 1001
    state.position.side = Side.BUY
    state.pending = make_pending(command_id="c-fail", action="CLOSE", ticket=1001)
    _ack(
        bridge,
        "c-fail",
        {
            "command_id": "c-fail",
            "action": "CLOSE",
            "status": "FAILED",
            "ticket": 1001,
            "symbol": "EURUSD",
            "magic": 19942026,
            "account_number": "999",
            "server": "Demo-Server",
            "instance_id": "EURUSD_M1_PRIMARY",
        },
    )
    pos = broker_position(ticket=1001)
    market = make_market_snapshot(bars_m1=candle_dicts(sequential_m1(n=30)), generated_at_utc=NOW)
    status = make_status_snapshot(generated_at_utc=NOW, positions=[broker_position_payload(pos)])
    result = run_cycle(config=config, state=state, market=market, status=status, bridge_root=bridge, now_utc=NOW)
    assert result.reason is ReasonCode.CLOSE_REJECTED
    assert state.position.state is PositionState.OPEN
    assert state.position.ticket == 1001


def test_open_success_without_broker_status_not_fully_confirmed(tmp_path: Path) -> None:
    bridge = prepare_bridge(tmp_path)
    config = config_for_tmp(tmp_path)
    state = InstanceRuntimeState()
    state.position.state = PositionState.OPEN_PENDING
    state.position.side = Side.BUY
    state.pending = make_pending(command_id="o1", action="OPEN", setup_fingerprint="fp-a")
    _ack(
        bridge,
        "o1",
        {
            "command_id": "o1",
            "action": "OPEN",
            "status": "SUCCESS",
            "ticket": 42,
            "symbol": "EURUSD",
            "magic": 19942026,
            "account_number": "999",
            "server": "Demo-Server",
            "instance_id": "EURUSD_M1_PRIMARY",
            "applied_price": 1.1,
            "applied_volume": 0.01,
            "applied_stop_loss": 1.098,
        },
    )
    market = make_market_snapshot(bars_m1=candle_dicts(sequential_m1(n=30)), generated_at_utc=NOW)
    status = make_status_snapshot(generated_at_utc=NOW, positions=[])
    result = run_cycle(config=config, state=state, market=market, status=status, bridge_root=bridge, now_utc=NOW)
    assert result.reason is ReasonCode.RECONCILIATION_REQUIRED
    assert state.position.state is PositionState.RECONCILING
    assert "fp-a" not in state.known_setup_fingerprints


def test_failed_open_does_not_consume_fingerprint(tmp_path: Path) -> None:
    bridge = prepare_bridge(tmp_path)
    config = config_for_tmp(tmp_path)
    state = InstanceRuntimeState()
    state.position.state = PositionState.OPEN_PENDING
    state.position.setup_fingerprint = "fp-retry"
    state.pending = make_pending(command_id="o2", action="OPEN", setup_fingerprint="fp-retry")
    _ack(
        bridge,
        "o2",
        {
            "command_id": "o2",
            "action": "OPEN",
            "status": "REJECTED",
            "ticket": None,
            "symbol": "EURUSD",
            "magic": 19942026,
            "account_number": "999",
            "server": "Demo-Server",
            "instance_id": "EURUSD_M1_PRIMARY",
        },
    )
    market = make_market_snapshot(bars_m1=candle_dicts(sequential_m1(n=30)), generated_at_utc=NOW)
    status = make_status_snapshot(generated_at_utc=NOW)
    result = run_cycle(config=config, state=state, market=market, status=status, bridge_root=bridge, now_utc=NOW)
    assert result.reason is ReasonCode.OPEN_REJECTED
    assert state.pending is None
    assert "fp-retry" not in state.known_setup_fingerprints


def test_ack_timeout_controlled_retry(tmp_path: Path) -> None:
    bridge = prepare_bridge(tmp_path)
    config = config_for_tmp(tmp_path, execution={"ack_timeout_ms": 1000, "retry_delay_ms": 0, "maximum_retries": 3})
    state = InstanceRuntimeState()
    state.position.state = PositionState.MODIFY_PENDING
    state.position.ticket = 9
    state.position.side = Side.BUY
    state.pending = make_pending(
        command_id="old",
        action="MODIFY",
        ticket=9,
        requested_stop_loss=1.10020,
        created_at="2026-03-01T12:00:00Z",
        last_attempt_at="2026-03-01T12:00:00Z",
        acknowledgement_deadline="2026-03-01T12:00:01Z",
    )
    state.trailing.pending_stop_loss = 1.10020
    pos = broker_position(ticket=9, stop_loss=1.09800, open_price=1.10000, net_profit=0.6)
    market = make_market_snapshot(
        bars_m1=candle_dicts(sequential_m1(n=30)), generated_at_utc=LATER, bid=1.1006, ask=1.1008
    )
    status = make_status_snapshot(generated_at_utc=LATER, positions=[broker_position_payload(pos)])
    result = run_cycle(config=config, state=state, market=market, status=status, bridge_root=bridge, now_utc=LATER)
    assert result.reason is ReasonCode.MODIFY_SENT
    assert state.pending is not None
    assert state.pending.command_id != "old"
    assert state.pending.retry_count == 1
    assert len(list((bridge / "commands").glob("*.json"))) == 1


def test_sequence_10_preferred_over_9(tmp_path: Path) -> None:
    d = tmp_path / "market"
    d.mkdir()
    atomic_write_json(d / "zzz_seq9.json", {"sequence": 9, "generated_at_utc": "2026-03-01T12:00:09Z"})
    atomic_write_json(d / "aaa_seq10.json", {"sequence": 10, "generated_at_utc": "2026-03-01T12:00:01Z"})
    choice = select_latest_snapshot(d)
    assert choice is not None
    assert choice.sequence == 10
    assert choice.path.name == "aaa_seq10.json"


def test_fingerprint_stable_across_m1_same_structure() -> None:
    from checktrader.config.models import StrategyConfig

    cfg = StrategyConfig(
        minimum_structure_bars=30,
        setup_expiry_bars=200,
        pullback_min_atr=0.0,
        pullback_max_atr=2.0,
        maximum_stop_atr=5.0,
    )
    base = synthesize_buy_setup_m1(trigger=False)
    d1 = run_strategy(symbol="EURUSD", specs=EURUSD_SPECS, bars_m1=base, config=cfg, now_utc=NOW)
    assert d1.setup is not None
    # Extra incomplete-bucket M1 should not change HTF origin/fingerprint
    last = base[-1]
    from datetime import datetime, timedelta

    start = datetime.fromisoformat(last.open_time_utc.replace("Z", "+00:00")) + timedelta(minutes=1)
    extra = make_m1_candle(
        open_time_utc=start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        open_=last.close,
        high=last.close + 0.00005,
        low=last.close - 0.00005,
        close=last.close,
    )
    d2 = run_strategy(symbol="EURUSD", specs=EURUSD_SPECS, bars_m1=base + [extra], config=cfg, now_utc=NOW)
    assert d2.setup is not None
    assert d1.setup.fingerprint == d2.setup.fingerprint
    assert d1.setup.setup_origin_timestamp == d2.setup.setup_origin_timestamp


def test_fixed_take_profit_disabled_sends_zero_tp(tmp_path: Path) -> None:
    config = load_test_config()
    assert config.trade_management.fixed_take_profit_enabled is False
    risk = approve_order(
        side=Side.BUY,
        entry=1.10000,
        stop_loss=1.09800,
        specs=EURUSD_SPECS,
        sizing=config.position_sizing,
        atr=0.001,
        maximum_stop_atr=config.strategy.maximum_stop_atr,
        free_margin=5_000,
        fixed_take_profit_enabled=False,
    )
    assert risk.take_profit is None
    cmd = build_open_command(
        symbol="EURUSD",
        magic=19942026,
        side=Side.BUY,
        volume=0.01,
        requested_price=1.1,
        stop_loss=1.098,
        take_profit=0.0 if risk.take_profit is None else risk.take_profit,
        setup_id="s",
        setup_fingerprint="f",
        created_at_utc=NOW,
        account_number="999",
        server="Demo-Server",
        instance_id="EURUSD_M1_PRIMARY",
    )
    payload = command_to_payload(cmd, sequence=1)
    assert payload["take_profit"] == 0.0
    assert "account_number" in payload and "server" in payload and "instance_id" in payload


def test_irregular_m1_does_not_form_m5() -> None:
    bars = sequential_m1(n=10, start_utc="2026-03-01T00:00:00Z")
    # Drop minute 2 → gap inside first M5 bucket
    gapped = [b for i, b in enumerate(bars) if i != 2]
    m5 = aggregate_timeframe(gapped, minutes=5, timeframe="M5")
    # First bucket incomplete/gapped → skipped; later full buckets may still form
    assert all(_bucket_ok(c) for c in m5)
    # Explicit incomplete group of 4 consecutive should not form
    four = sequential_m1(n=4, start_utc="2026-03-01T01:00:00Z")
    assert aggregate_timeframe(four, minutes=5, timeframe="M5") == []


def _bucket_ok(c: Candle) -> bool:
    return c.complete and c.timeframe == "M5"


def test_buy_path_open_be_grid_close(tmp_path: Path) -> None:
    bridge = prepare_bridge(tmp_path)
    config = config_for_tmp(tmp_path, strategy={"setup_expiry_bars": 200})
    state = InstanceRuntimeState()
    bars = synthesize_buy_setup_m1(trigger=True)
    last = bars[-1]
    market = make_market_snapshot(
        bars_m1=candle_dicts(bars), generated_at_utc=NOW, bid=last.close - 0.0001, ask=last.close
    )
    status = make_status_snapshot(generated_at_utc=NOW)
    r = run_cycle(config=config, state=state, market=market, status=status, bridge_root=bridge, now_utc=NOW)
    assert r.reason is ReasonCode.OPEN_SENT
    cmd = read_json(next((bridge / "commands").glob("*.json")))
    assert cmd["take_profit"] == 0.0
    assert cmd["account_number"] == "999"
    ticket = 7001
    _ack(
        bridge,
        cmd["command_id"],
        {
            "command_id": cmd["command_id"],
            "action": "OPEN",
            "status": "SUCCESS",
            "ticket": ticket,
            "symbol": "EURUSD",
            "magic": 19942026,
            "account_number": "999",
            "server": "Demo-Server",
            "instance_id": config.runtime.instance_id,
            "applied_price": cmd["requested_price"],
            "applied_volume": 0.01,
            "applied_stop_loss": cmd["stop_loss"],
        },
    )
    pos = broker_position(
        ticket=ticket,
        open_price=float(cmd["requested_price"]),
        stop_loss=float(cmd["stop_loss"]),
        net_profit=0.0,
        profit=0.0,
    )
    status = make_status_snapshot(generated_at_utc=NOW, positions=[broker_position_payload(pos)])
    r2 = run_cycle(config=config, state=state, market=market, status=status, bridge_root=bridge, now_utc=NOW)
    assert r2.reason is ReasonCode.OPEN_CONFIRMED
    assert state.position.state is PositionState.OPEN
    assert cmd["setup_fingerprint"] in state.known_setup_fingerprints

    # BE on the actual fill price (tick_value=1.0, 0.01 lot → +0.00020 for +0.20 money)
    open_px = float(state.position.open_price or cmd["requested_price"])
    be_sl = round(open_px + 0.00020, 5)
    pos = broker_position(
        ticket=ticket,
        open_price=open_px,
        stop_loss=float(cmd["stop_loss"]),
        net_profit=0.60,
        profit=0.60,
        current_price=open_px + 0.00060,
    )
    market = make_market_snapshot(
        bars_m1=candle_dicts(bars), generated_at_utc=NOW, bid=open_px + 0.00060, ask=open_px + 0.00080
    )
    status = make_status_snapshot(generated_at_utc=NOW, positions=[broker_position_payload(pos)])
    r3 = run_cycle(config=config, state=state, market=market, status=status, bridge_root=bridge, now_utc=NOW)
    assert r3.reason is ReasonCode.MODIFY_SENT
    assert state.trailing.pending_stop_loss == be_sl
    assert state.pending is not None
    be_cid = state.pending.command_id
    _ack(
        bridge,
        be_cid,
        {
            "command_id": be_cid,
            "action": "MODIFY",
            "status": "SUCCESS",
            "ticket": ticket,
            "symbol": "EURUSD",
            "magic": 19942026,
            "account_number": "999",
            "server": "Demo-Server",
            "instance_id": config.runtime.instance_id,
            "applied_stop_loss": be_sl,
            "previous_stop_loss": float(cmd["stop_loss"]),
        },
    )
    pos = broker_position(
        ticket=ticket,
        open_price=open_px,
        stop_loss=be_sl,
        net_profit=0.60,
        profit=0.60,
        current_price=open_px + 0.00060,
    )
    status = make_status_snapshot(generated_at_utc=NOW, positions=[broker_position_payload(pos)])
    r_be = run_cycle(config=config, state=state, market=market, status=status, bridge_root=bridge, now_utc=NOW)
    assert r_be.reason is ReasonCode.BE_CONFIRMED
    assert state.trailing.be_confirmed is True
    assert state.pending is None

    # After BE: ATR grid MODIFY (jump steps allowed).
    from checktrader.application.cycle import _current_atr
    from checktrader.position_management.atr_grid_trailing import atr_step_price, compute_grid_stop_loss

    atr_value = _current_atr(market, atr_period=config.strategy.atr_period)
    step = atr_step_price(
        atr=atr_value,
        trailing_step_atr=config.trade_management.trailing_step_atr,
        specs=market.specs,
    )
    # Ensure price is far enough for several ATR steps
    bid = be_sl + max(step * 5, 0.00100)
    grid_sl, steps = compute_grid_stop_loss(
        side=Side.BUY,
        confirmed_be_sl=be_sl,
        current_price=bid,
        atr=atr_value,
        trailing_step_atr=config.trade_management.trailing_step_atr,
        specs=market.specs,
    )
    assert steps >= 1
    assert grid_sl is not None
    assert grid_sl == round(be_sl + steps * step, 5) or abs(float(grid_sl) - (be_sl + steps * step)) < 1e-8
    pos = broker_position(
        ticket=ticket,
        open_price=open_px,
        stop_loss=be_sl,
        net_profit=3.0,
        profit=3.0,
        current_price=bid,
    )
    market = make_market_snapshot(bars_m1=candle_dicts(bars), generated_at_utc=NOW, bid=bid, ask=bid + 0.00020)
    status = make_status_snapshot(generated_at_utc=NOW, positions=[broker_position_payload(pos)])
    r_send = run_cycle(config=config, state=state, market=market, status=status, bridge_root=bridge, now_utc=NOW)
    assert r_send.reason is ReasonCode.MODIFY_SENT
    assert state.pending is not None
    pending_sl = float(state.trailing.pending_stop_loss or 0.0)
    # Protective selector may choose grid or a stronger high-lock on the same grid.
    assert pending_sl >= float(grid_sl) - 1e-9
    assert pending_sl > be_sl
    cid = state.pending.command_id
    _ack(
        bridge,
        cid,
        {
            "command_id": cid,
            "action": "MODIFY",
            "status": "SUCCESS",
            "ticket": ticket,
            "symbol": "EURUSD",
            "magic": 19942026,
            "account_number": "999",
            "server": "Demo-Server",
            "instance_id": config.runtime.instance_id,
            "applied_stop_loss": pending_sl,
            "previous_stop_loss": be_sl,
        },
    )
    pos = broker_position(
        ticket=ticket, open_price=open_px, stop_loss=pending_sl, net_profit=3.0, profit=3.0, current_price=bid
    )
    status = make_status_snapshot(generated_at_utc=NOW, positions=[broker_position_payload(pos)])
    r_conf = run_cycle(config=config, state=state, market=market, status=status, bridge_root=bridge, now_utc=NOW)
    assert r_conf.reason in {ReasonCode.TRAILING_GRID_CONFIRMED, ReasonCode.BE_CONFIRMED, ReasonCode.MODIFY_CONFIRMED}
    # Reason after BE is TRAILING_GRID_CONFIRMED when be_confirmed was already true.
    assert state.last_reason == ReasonCode.TRAILING_GRID_CONFIRMED.value
    assert state.trailing.confirmed_stop_loss == pending_sl
    assert state.trailing.confirmed_grid_step >= 1


def test_restart_open_pending_no_double_open(tmp_path: Path) -> None:
    bridge = prepare_bridge(tmp_path)
    config = config_for_tmp(tmp_path)
    state = InstanceRuntimeState()
    state.position.state = PositionState.OPEN_PENDING
    state.position.side = Side.BUY
    state.pending = make_pending(command_id="pending-open", action="OPEN", setup_fingerprint="fp-x")
    path = tmp_path / "runtime" / "state" / "instance.json"
    save_instance_state(path, state, now_utc=NOW)
    loaded = load_instance_state(path)
    assert loaded.pending_command_id == "pending-open"
    market = make_market_snapshot(bars_m1=candle_dicts(sequential_m1(n=30)), generated_at_utc=NOW)
    status = make_status_snapshot(generated_at_utc=NOW)
    result = run_cycle(config=config, state=loaded, market=market, status=status, bridge_root=bridge, now_utc=NOW)
    assert result.reason is ReasonCode.COMMAND_ALREADY_PENDING
    assert list((bridge / "commands").glob("*.json")) == []
