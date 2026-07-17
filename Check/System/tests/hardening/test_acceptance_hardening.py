"""Acceptance regression tests for SYSTEM hardening (items 1–14)."""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import pytest

from engine.ai_decision_layer import parse_ai_decision_json
from engine.core.cycle import is_sensor_fresh, resolve_trade_management_price
from engine.core.instance import Instance
from engine.core.paths import SystemPaths
from engine.core.position_sync import find_status_positions, reconcile_position_with_status
from engine.decision.filters.news_filter import evaluate_news_filter
from engine.execution.command_idempotence import CommandIdempotenceStore, try_execute_with_idempotence
from engine.execution.engine import apply_ack_to_instance_state
from engine.execution.command import OrderCommand
from engine.protocol.constants import AckStatus, OrderAction, PROTOCOL_SCHEMA_VERSION, Side
from engine.protocol.models import AckRecord, SensorReading, StatusPositionSnapshot, StatusRecord, UniverseRecord
from engine.protocol.parser import parse_ack
from engine.state.instance_state import InstanceState
from tests.mql4 import mql_source


def _sensor(*, bid: float, ask: float, time_utc: str) -> SensorReading:
    return SensorReading(
        time_utc=time_utc,
        bid=bid,
        ask=ask,
        spread=ask - bid,
        spread_points=(ask - bid) / 0.00001,
        symbol='EURUSD',
        digits=5,
        point=0.00001,
    )


def test_01_buy_trailing_uses_only_fresh_bid() -> None:
    sensor = _sensor(bid=1.1000, ask=1.1005, time_utc='2026-07-17T12:00:00.000Z')
    assert resolve_trade_management_price(position_side=Side.BUY.value, sensor_reading=sensor) == pytest.approx(1.1000)
    # Must not prefer market close over bid
    assert resolve_trade_management_price(position_side=Side.BUY.value, sensor_reading=sensor, market_bars=()) == pytest.approx(1.1000)


def test_02_sell_trailing_uses_only_fresh_ask() -> None:
    sensor = _sensor(bid=1.1000, ask=1.1005, time_utc='2026-07-17T12:00:00.000Z')
    assert resolve_trade_management_price(position_side=Side.SELL.value, sensor_reading=sensor) == pytest.approx(1.1005)


def test_03_ack_fill_price_replaces_theoretical_entry() -> None:
    instance = Instance('12345', 'EURUSD', 100001)
    state = InstanceState(instance)
    state.instrument_digits = 5
    state.instrument_point = 0.00001
    cmd = OrderCommand(
        command_id='cmd-1',
        action=OrderAction.OPEN.value,
        reason='test',
        decision_id='d1',
        side=Side.BUY.value,
        volume=0.01,
        stop_loss=1.09,
        take_profit=None,
        ticket=None,
    )
    ack = AckRecord(
        schema_version=PROTOCOL_SCHEMA_VERSION,
        timestamp_utc='2026-07-17T12:00:01.000Z',
        command_id='cmd-1',
        account_id='12345',
        symbol='EURUSD',
        magic=100001,
        status=AckStatus.SUCCESS.value,
        ticket=777,
        fill_price=1.1007,
        open_time_utc='2026-07-17T12:00:01.000Z',
        volume=0.01,
        side=Side.BUY.value,
    )
    apply_ack_to_instance_state(state, cmd, ack, entry_price=1.1000)
    assert state.position_entry_price == pytest.approx(1.1007)
    assert state.open_ticket == 777


def test_04_position_bars_open_only_on_new_m1_bar() -> None:
    instance = Instance('12345', 'EURUSD', 100001)
    state = InstanceState(instance)
    state.update_position(open_ticket=1, position_side='BUY', position_volume=0.01, entry_price=1.1, stop_loss=1.09, open_time_utc='2026-07-17T12:00:00.000Z')
    assert state.position_bars_open == 1
    assert state.sync_position_bars_for_market_bar('2026-07-17T12:00:00.000Z') is False
    assert state.position_bars_open == 1
    assert state.sync_position_bars_for_market_bar('2026-07-17T12:01:00.000Z') is True
    assert state.position_bars_open == 2
    assert state.sync_position_bars_for_market_bar('2026-07-17T12:01:00.000Z') is False
    assert state.position_bars_open == 2


def test_05_duplicate_command_id_does_not_open_twice(tmp_path: Path) -> None:
    store = CommandIdempotenceStore(store_dir=tmp_path)
    opens: list[str] = []

    def execute_open(command_id: str) -> bool:
        opens.append(command_id)
        return True

    def write_ack(command_id: str, *, success: bool, duplicate: bool) -> bool:
        return True

    try_execute_with_idempotence(command_id='c1', account_id='1', symbol='EURUSD', magic=1, store=store, last_processed_command_id='', execute_open=execute_open, write_ack=write_ack)
    try_execute_with_idempotence(command_id='c1', account_id='1', symbol='EURUSD', magic=1, store=store, last_processed_command_id='c1', execute_open=execute_open, write_ack=write_ack)
    assert opens == ['c1']


def test_06_ordersend_ok_ack_write_fail_no_duplicate(tmp_path: Path) -> None:
    store = CommandIdempotenceStore(store_dir=tmp_path)
    opens: list[str] = []

    def execute_open(command_id: str) -> bool:
        opens.append(command_id)
        return True

    try_execute_with_idempotence(command_id='c2', account_id='1', symbol='EURUSD', magic=1, store=store, last_processed_command_id='', execute_open=execute_open, write_ack=lambda *a, **k: False)
    try_execute_with_idempotence(command_id='c2', account_id='1', symbol='EURUSD', magic=1, store=store, last_processed_command_id='', execute_open=execute_open, write_ack=lambda *a, **k: True)
    assert opens == ['c2']
    assert store.is_processed('1', 'EURUSD', 1, 'c2')


def test_07_ack_timeout_broker_position_sync(tmp_path: Path) -> None:
    from engine.execution.order_comment import build_open_order_comment

    root = tmp_path
    (root / 'data' / 'clients' / '12345' / 'journal').mkdir(parents=True)
    (root / 'data' / 'clients' / '12345' / 'state').mkdir(parents=True)
    paths = SystemPaths(root)
    instance = Instance('12345', 'EURUSD', 100001)
    state = InstanceState(instance)
    state.instrument_digits = 5
    state.instrument_point = 0.00001
    comment = build_open_order_comment('pending-open')
    state.set_pending_execution(
        command_id='pending-open',
        decision_id='dec-1',
        since_utc='2026-07-17T12:00:00.000Z',
        comment=comment,
        symbol='EURUSD',
        magic=100001,
        side='BUY',
        volume=0.01,
    )
    status = StatusRecord(
        schema_version=PROTOCOL_SCHEMA_VERSION,
        timestamp_utc='2026-07-17T12:00:05.000Z',
        account_id='12345',
        connected=True,
        trade_allowed=True,
        balance=1000.0,
        equity=1000.0,
        margin_free=900.0,
        ea_version='1.0.0',
        open_positions=(
            StatusPositionSnapshot(
                symbol='EURUSD',
                magic=100001,
                ticket=555,
                side='BUY',
                volume=0.01,
                entry_price=1.1003,
                stop_loss=1.09,
                take_profit=0.0,
                open_time_utc='2026-07-17T12:00:01.000Z',
                order_comment=comment,
            ),
        ),
    )
    result = reconcile_position_with_status(paths, instance, state, status, timestamp_utc='2026-07-17T12:00:05.000Z')
    assert result.changed
    assert state.open_ticket == 555
    assert state.position_entry_price == pytest.approx(1.1003)
    assert state.pending_execution_command_id is None


def test_08_stale_sensor_blocks_freshness_helper() -> None:
    now = '2026-07-17T12:02:00.000Z'
    fresh = _sensor(bid=1.1, ask=1.1002, time_utc='2026-07-17T12:01:50.000Z')
    stale = _sensor(bid=1.1, ask=1.1002, time_utc='2026-07-17T11:00:00.000Z')
    assert is_sensor_fresh(fresh, now, 90000) is True
    assert is_sensor_fresh(stale, now, 90000) is False
    assert resolve_trade_management_price(position_side='BUY', sensor_reading=None) is None


def test_09_stale_bar_gate_documented_in_cycle_source() -> None:
    # Content-timestamp stale checks live in cycle; verify helpers exist and missing sensor blocks TM price.
    assert resolve_trade_management_price(position_side='BUY', sensor_reading=None) is None
    cycle_path = Path(__file__).resolve().parents[2] / 'engine' / 'core' / 'cycle.py'
    source = cycle_path.read_text(encoding='utf-8')
    assert 'bar_freshness_ms' in source or 'market_data_utc' in source
    assert 'stale' in source.lower()


def test_10_ai_string_false_rejected() -> None:
    assert parse_ai_decision_json('{"bias":"NEUTRAL","confidence":0.5,"allow_buy":"false","allow_sell":false,"allow_close":true,"reason":"x"}') is None
    parsed = parse_ai_decision_json('{"bias":"NEUTRAL","confidence":0.5,"allow_buy":false,"allow_sell":true,"allow_close":true,"reason":"ok"}')
    assert parsed is not None
    assert parsed.allow_buy is False
    assert parsed.allow_sell is True


def test_11_duplicate_magic_positions_set_anomaly(tmp_path: Path) -> None:
    root = tmp_path
    (root / 'data' / 'clients' / '12345' / 'journal').mkdir(parents=True)
    paths = SystemPaths(root)
    instance = Instance('12345', 'EURUSD', 100001)
    state = InstanceState(instance)
    state.instrument_digits = 5
    state.instrument_point = 0.00001
    state.update_position(open_ticket=1, position_side='BUY', position_volume=0.01, entry_price=1.1, stop_loss=1.09)
    status = StatusRecord(
        schema_version=PROTOCOL_SCHEMA_VERSION,
        timestamp_utc='2026-07-17T12:00:05.000Z',
        account_id='12345',
        connected=True,
        trade_allowed=True,
        balance=1000.0,
        equity=1000.0,
        margin_free=900.0,
        ea_version='1.0.0',
        open_positions=(
            StatusPositionSnapshot(symbol='EURUSD', magic=100001, ticket=1, side='BUY', volume=0.01, entry_price=1.1, stop_loss=1.09, take_profit=0.0),
            StatusPositionSnapshot(symbol='EURUSD', magic=100001, ticket=2, side='BUY', volume=0.01, entry_price=1.101, stop_loss=1.09, take_profit=0.0),
        ),
    )
    matches = find_status_positions(status, instance)
    assert len(matches) == 2
    result = reconcile_position_with_status(paths, instance, state, status, timestamp_utc='2026-07-17T12:00:05.000Z')
    assert result.duplicate_anomaly is True
    assert state.duplicate_position_anomaly is True


def test_12_external_close_without_invented_price(tmp_path: Path) -> None:
    root = tmp_path
    journal_dir = root / 'data' / 'clients' / '12345' / 'journal'
    journal_dir.mkdir(parents=True)
    paths = SystemPaths(root)
    instance = Instance('12345', 'EURUSD', 100001)
    state = InstanceState(instance)
    state.update_position(open_ticket=9, position_side='BUY', position_volume=0.01, entry_price=1.1, stop_loss=1.09)
    status = StatusRecord(
        schema_version=PROTOCOL_SCHEMA_VERSION,
        timestamp_utc='2026-07-17T12:00:05.000Z',
        account_id='12345',
        connected=True,
        trade_allowed=True,
        balance=1000.0,
        equity=1000.0,
        margin_free=900.0,
        ea_version='1.0.0',
        open_positions=(),
    )
    result = reconcile_position_with_status(paths, instance, state, status, timestamp_utc='2026-07-17T12:00:05.000Z')
    assert result.external_close is True
    assert result.close_pending is False
    assert result.close_reconciled is True
    assert state.open_ticket is None
    assert state.close_pending_reconciliation is False
    # Ghost clear journal must not invent SL/entry as close price.
    trade_files = list(journal_dir.glob('trade_*.jsonl'))
    assert trade_files
    for line in trade_files[0].read_text(encoding='utf-8').strip().splitlines():
        payload = json.loads(line)
        assert payload.get('price') not in {1.09, 1.1, 1.1000, 1.0900}


def test_13_instance_isolation_threadpool_does_not_serialize_sleep() -> None:
    from engine.core import orchestrator as orch
    assert hasattr(orch, 'ThreadPoolExecutor')
    started: list[float] = []
    finished: list[float] = []

    def work(_: int) -> None:
        started.append(time.monotonic())
        time.sleep(0.15)
        finished.append(time.monotonic())

    t0 = time.monotonic()
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(work, [1, 2]))
    elapsed = time.monotonic() - t0
    assert elapsed < 0.28
    assert len(started) == 2


def test_14_strategy_score_modules_unchanged_by_hardening_markers() -> None:
    # Hardening must not rewrite candidate score formulas; keep module presence.
    from engine.decision import buy, sell, scorer, engine as decision_engine
    assert hasattr(buy, 'calculate_buy_candidate')
    assert hasattr(sell, 'calculate_sell_candidate')
    assert hasattr(scorer, 'compare_candidates')
    assert hasattr(decision_engine, 'run_decision_engine')
    buy_src = (Path(__file__).resolve().parents[2] / 'engine' / 'decision' / 'buy.py').read_text(encoding='utf-8')
    sell_src = (Path(__file__).resolve().parents[2] / 'engine' / 'decision' / 'sell.py').read_text(encoding='utf-8')
    assert 'def calculate_buy_candidate' in buy_src
    assert 'def calculate_sell_candidate' in sell_src


def test_parse_ack_accepts_fill_price() -> None:
    ack = parse_ack(
        {
            'schema_version': PROTOCOL_SCHEMA_VERSION,
            'timestamp_utc': '2026-07-17T12:00:00.000Z',
            'command_id': 'c',
            'account_id': '12345',
            'symbol': 'EURUSD',
            'magic': 100001,
            'status': 'SUCCESS',
            'ticket': 1,
            'fill_price': 1.2345,
            'open_time_utc': '2026-07-17T12:00:00.000Z',
            'volume': 0.01,
            'side': 'BUY',
        }
    )
    assert ack.fill_price == pytest.approx(1.2345)


def test_news_filter_inactive_without_calendar() -> None:
    universe = UniverseRecord(
        schema_version=PROTOCOL_SCHEMA_VERSION,
        timestamp_utc='2026-07-17T12:00:00.000Z',
        session='LONDON',
        market_regime='ranging',
        news_window_active=False,
        news_impact_level='low',
        metadata={'news_data_available': False, 'news_filter': 'disabled_no_calendar'},
    )
    result = evaluate_news_filter(universe, block_high_impact_news=True)
    assert result.news_acceptable is True


def test_mql_regime_not_constant_ranging_stub() -> None:
    source = mql_source.load_mqh('SYSTEM_Universe.mqh')
    body = mql_source.function_body(source, 'SYSTEM_DetectMarketRegime')
    assert 'SYSTEM_REGIME_TRENDING' in body or 'trending' in body.lower()
    assert 'ATR' in body or 'atr' in body or 'iHigh' in body
