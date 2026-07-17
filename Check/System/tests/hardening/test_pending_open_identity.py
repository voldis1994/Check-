"""Strict ACK-timeout pending OPEN identity + idempotence regressions."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine.core.instance import Instance
from engine.core.paths import SystemPaths
from engine.core.position_sync import _status_matches_pending_open, reconcile_position_with_status
from engine.execution.command_idempotence import CommandIdempotenceStore, try_execute_with_idempotence
from engine.execution.order_comment import MT4_ORDER_COMMENT_MAX_LEN, build_open_order_comment
from engine.protocol.constants import (
    PROTOCOL_SCHEMA_VERSION,
    REASON_AMBIGUOUS_PENDING_EXECUTION,
)
from engine.protocol.models import StatusPositionSnapshot, StatusRecord
from engine.state.instance_state import InstanceState
from tests.mql4 import mql_source

SYSTEM_ROOT = Path(__file__).resolve().parents[2]


def _status(*, positions=(), timestamp_utc: str = '2026-07-17T12:00:05.000Z') -> StatusRecord:
    return StatusRecord(
        schema_version=PROTOCOL_SCHEMA_VERSION,
        timestamp_utc=timestamp_utc,
        account_id='12345',
        connected=True,
        trade_allowed=True,
        balance=1000.0,
        equity=1000.0,
        margin_free=900.0,
        ea_version='1.0.0',
        open_positions=positions,
    )


def _pos(
    *,
    ticket: int = 555,
    side: str = 'BUY',
    volume: float = 0.01,
    comment: str | None = 'cmd-open-1',
    open_time_utc: str | None = '2026-07-17T12:00:01.000Z',
    entry_price: float = 1.1003,
) -> StatusPositionSnapshot:
    return StatusPositionSnapshot(
        symbol='EURUSD',
        magic=100001,
        ticket=ticket,
        side=side,
        volume=volume,
        entry_price=entry_price,
        stop_loss=1.09,
        take_profit=0.0,
        open_time_utc=open_time_utc,
        order_comment=comment,
    )


def _pending_state(**overrides) -> InstanceState:
    instance = Instance('12345', 'EURUSD', 100001)
    state = InstanceState(instance)
    state.instrument_digits = 5
    state.instrument_point = 0.00001
    comment = build_open_order_comment('cmd-open-1')
    state.set_pending_execution(
        command_id='cmd-open-1',
        decision_id='dec-1',
        since_utc='2026-07-17T12:00:00.000Z',
        comment=comment,
        symbol='EURUSD',
        magic=100001,
        side='BUY',
        volume=0.01,
        preexisting_tickets=(),
    )
    for key, value in overrides.items():
        setattr(state, key, value)
    return state


def test_01_pending_with_correct_command_comment_is_confirmed(tmp_path: Path) -> None:
    paths = SystemPaths(tmp_path)
    state = _pending_state()
    paths.ensure_account_directories(state.instance.account_id)
    comment = build_open_order_comment('cmd-open-1')
    result = reconcile_position_with_status(
        paths,
        state.instance,
        state,
        _status(positions=(_pos(comment=comment),)),
        timestamp_utc='2026-07-17T12:00:05.000Z',
    )
    assert result.broker_execution_confirmed is True
    assert state.open_ticket == 555
    assert state.position_entry_price == pytest.approx(1.1003)
    assert state.pending_execution_command_id is None


def test_02_wrong_command_comment_not_accepted(tmp_path: Path) -> None:
    paths = SystemPaths(tmp_path)
    state = _pending_state()
    paths.ensure_account_directories(state.instance.account_id)
    result = reconcile_position_with_status(
        paths,
        state.instance,
        state,
        _status(positions=(_pos(comment='other-cmd'),)),
        timestamp_utc='2026-07-17T12:00:05.000Z',
    )
    assert result.broker_execution_confirmed is False
    assert state.open_ticket is None
    assert state.pending_execution_command_id == 'cmd-open-1'


def test_03_missing_order_comment_not_accepted(tmp_path: Path) -> None:
    paths = SystemPaths(tmp_path)
    state = _pending_state()
    paths.ensure_account_directories(state.instance.account_id)
    result = reconcile_position_with_status(
        paths,
        state.instance,
        state,
        _status(positions=(_pos(comment=None),)),
        timestamp_utc='2026-07-17T12:00:05.000Z',
    )
    assert result.broker_execution_confirmed is False
    assert state.pending_execution_command_id == 'cmd-open-1'


def test_04_open_time_before_pending_since_not_accepted() -> None:
    state = _pending_state()
    comment = build_open_order_comment('cmd-open-1')
    position = _pos(comment=comment, open_time_utc='2026-07-17T11:59:50.000Z')
    assert _status_matches_pending_open(state, position) is False


def test_05_wrong_side_not_accepted() -> None:
    state = _pending_state()
    comment = build_open_order_comment('cmd-open-1')
    assert _status_matches_pending_open(state, _pos(comment=comment, side='SELL')) is False


def test_06_wrong_volume_not_accepted() -> None:
    state = _pending_state()
    comment = build_open_order_comment('cmd-open-1')
    assert _status_matches_pending_open(state, _pos(comment=comment, volume=0.02)) is False


def test_07_correct_symbol_magic_wrong_comment_not_accepted(tmp_path: Path) -> None:
    paths = SystemPaths(tmp_path)
    state = _pending_state()
    paths.ensure_account_directories(state.instance.account_id)
    # Same symbol/magic/side/volume — still rejected without comment match.
    result = reconcile_position_with_status(
        paths,
        state.instance,
        state,
        _status(positions=(_pos(comment='cmd-other'),)),
        timestamp_utc='2026-07-17T12:00:05.000Z',
    )
    assert result.broker_execution_confirmed is False
    assert state.pending_execution_command_id == 'cmd-open-1'


def test_08_two_candidates_ambiguous(tmp_path: Path) -> None:
    paths = SystemPaths(tmp_path)
    state = _pending_state()
    paths.ensure_account_directories(state.instance.account_id)
    comment = build_open_order_comment('cmd-open-1')
    result = reconcile_position_with_status(
        paths,
        state.instance,
        state,
        _status(
            positions=(
                _pos(ticket=555, comment=comment),
                _pos(ticket=556, comment=comment, entry_price=1.1004),
            )
        ),
        timestamp_utc='2026-07-17T12:00:05.000Z',
    )
    assert result.ambiguous_pending is True
    assert result.broker_execution_confirmed is False
    assert state.ambiguous_pending_execution is True
    assert state.pending_execution_command_id == 'cmd-open-1'
    assert state.open_ticket is None
    journal = list(paths.account_journal_dir(state.instance.account_id).glob('error_*.jsonl'))
    assert journal
    payload = json.loads(journal[0].read_text(encoding='utf-8').strip().splitlines()[-1])
    assert REASON_AMBIGUOUS_PENDING_EXECUTION in str(payload)


def test_09_pending_blocks_new_open_in_cycle_source() -> None:
    cycle_src = (SYSTEM_ROOT / 'engine' / 'core' / 'cycle.py').read_text(encoding='utf-8')
    assert 'pending_execution_command_id is not None' in cycle_src
    assert 'execution_outcome_unresolved' in cycle_src or 'REASON_EXECUTION_OUTCOME_UNRESOLVED' in cycle_src
    assert 'ambiguous_pending_execution' in cycle_src


def test_10_after_precise_reconcile_pending_cleared(tmp_path: Path) -> None:
    paths = SystemPaths(tmp_path)
    state = _pending_state()
    paths.ensure_account_directories(state.instance.account_id)
    comment = build_open_order_comment('cmd-open-1')
    reconcile_position_with_status(
        paths,
        state.instance,
        state,
        _status(positions=(_pos(comment=comment),)),
        timestamp_utc='2026-07-17T12:00:05.000Z',
    )
    assert state.pending_execution_command_id is None
    assert state.pending_execution_comment is None
    assert state.ambiguous_pending_execution is False


def test_11_reconcile_stores_actual_fill_and_ticket(tmp_path: Path) -> None:
    paths = SystemPaths(tmp_path)
    state = _pending_state()
    paths.ensure_account_directories(state.instance.account_id)
    comment = build_open_order_comment('cmd-open-1')
    reconcile_position_with_status(
        paths,
        state.instance,
        state,
        _status(
            positions=(
                _pos(
                    ticket=777,
                    comment=comment,
                    entry_price=1.1011,
                    open_time_utc='2026-07-17T12:00:02.000Z',
                ),
            )
        ),
        timestamp_utc='2026-07-17T12:00:05.000Z',
    )
    assert state.open_ticket == 777
    assert state.position_entry_price == pytest.approx(1.1011)
    assert state.position_open_time_utc == '2026-07-17T12:00:02.000Z'


def test_12_duplicate_command_id_does_not_open_twice(tmp_path: Path) -> None:
    store = CommandIdempotenceStore(store_dir=tmp_path)
    opens: list[str] = []

    def execute_open(command_id: str) -> bool:
        opens.append(command_id)
        return True

    try_execute_with_idempotence(
        command_id='c1',
        account_id='1',
        symbol='EURUSD',
        magic=1,
        store=store,
        last_processed_command_id='',
        execute_open=execute_open,
        write_ack=lambda *a, **k: True,
    )
    try_execute_with_idempotence(
        command_id='c1',
        account_id='1',
        symbol='EURUSD',
        magic=1,
        store=store,
        last_processed_command_id='c1',
        execute_open=execute_open,
        write_ack=lambda *a, **k: True,
    )
    assert opens == ['c1']


def test_13_ordersend_ok_ack_write_fail_blocks_second_open(tmp_path: Path) -> None:
    store = CommandIdempotenceStore(store_dir=tmp_path)
    opens: list[str] = []

    def execute_open(command_id: str) -> bool:
        opens.append(command_id)
        return True

    try_execute_with_idempotence(
        command_id='c2',
        account_id='1',
        symbol='EURUSD',
        magic=1,
        store=store,
        last_processed_command_id='',
        execute_open=execute_open,
        write_ack=lambda *a, **k: False,
    )
    try_execute_with_idempotence(
        command_id='c2',
        account_id='1',
        symbol='EURUSD',
        magic=1,
        store=store,
        last_processed_command_id='',
        execute_open=execute_open,
        write_ack=lambda *a, **k: True,
    )
    assert opens == ['c2']
    assert store.is_processed('1', 'EURUSD', 1, 'c2')


def test_14_ea_restart_loads_processed_command_id() -> None:
    ea_source = mql_source.load_mq4('SYSTEM_EA.mq4')
    assert 'SYSTEM_LoadProcessedCommandId' in ea_source
    assert 'g_last_processed_command_id' in ea_source
    exec_source = mql_source.load_mqh('SYSTEM_Execution.mqh')
    body = mql_source.function_body(exec_source, 'SYSTEM_TryExecutePendingControl')
    assert 'SYSTEM_IsCommandProcessed' in body
    assert 'SYSTEM_MarkCommandProcessed' in body
    mark_pos = body.find('SYSTEM_MarkCommandProcessed')
    write_pos = body.find('SYSTEM_WriteAck', mark_pos)
    assert write_pos > mark_pos


def test_15_buy_sell_strategy_modules_unchanged_presence() -> None:
    for rel in (
        'engine/decision/buy.py',
        'engine/decision/sell.py',
        'engine/decision/engine.py',
        'engine/decision/scorer.py',
        'engine/analysis/structure.py',
        'engine/analysis/momentum.py',
    ):
        assert (SYSTEM_ROOT / rel).exists()


def test_16_no_fixed_tp_in_live_config() -> None:
    system_json = json.loads((SYSTEM_ROOT / 'config' / 'system.json').read_text(encoding='utf-8'))
    assert system_json['trade_management']['use_fixed_take_profit'] is False


def test_17_no_max_risk_percent_in_live_config() -> None:
    system_json = json.loads((SYSTEM_ROOT / 'config' / 'system.json').read_text(encoding='utf-8'))
    assert 'max_risk_per_trade_percent' not in system_json['risk']


def test_18_fixed_lot_only_size_source() -> None:
    system_json = json.loads((SYSTEM_ROOT / 'config' / 'system.json').read_text(encoding='utf-8'))
    assert system_json['risk']['fixed_lot_volume'] == pytest.approx(0.01)
    engine_src = (SYSTEM_ROOT / 'engine' / 'risk' / 'engine.py').read_text(encoding='utf-8')
    assert 'calculate_position_size' not in engine_src


def test_19_trailing_remains_primary_exit() -> None:
    system_json = json.loads((SYSTEM_ROOT / 'config' / 'system.json').read_text(encoding='utf-8'))
    assert system_json['trade_management']['enabled'] is True
    assert system_json['trade_management']['use_fixed_take_profit'] is False
    assert 'trailing_step_pips' in system_json['trade_management']


def test_order_comment_fits_mt4_limit() -> None:
    short = build_open_order_comment('cmd-short')
    assert len(short) <= MT4_ORDER_COMMENT_MAX_LEN
    long_id = 'a' * 40
    token = build_open_order_comment(long_id)
    assert len(token) <= MT4_ORDER_COMMENT_MAX_LEN
    assert token.startswith('C')
    assert token == build_open_order_comment(long_id)


def test_preexisting_ticket_not_matched() -> None:
    state = _pending_state()
    state.pending_preexisting_tickets = (555,)
    comment = build_open_order_comment('cmd-open-1')
    assert _status_matches_pending_open(state, _pos(ticket=555, comment=comment)) is False


def test_open_command_includes_order_comment() -> None:
    from engine.execution.command import build_order_command
    from engine.protocol.constants import Decision, RiskResult
    from engine.risk.engine import RiskEngineResult
    from tests.journal.test_decision_journal import _manual_decision_result

    decision = _manual_decision_result()
    risk = RiskEngineResult(
        result=RiskResult.ALLOW.value,
        reason='ok',
        position_size=0.01,
        stop_loss=1.09,
        take_profit=0.0,
    )
    # Force BUY decision shape from fixture
    if decision.decision not in {Decision.BUY.value, Decision.SELL.value}:
        decision = decision.__class__(
            decision_id=decision.decision_id,
            decision=Decision.BUY.value,
            reason='BUY: test',
            preferred_side='BUY',
            buy_candidate=decision.buy_candidate,
            sell_candidate=decision.sell_candidate,
            buy_score=decision.buy_score,
            sell_score=decision.sell_score,
            analysis_context=decision.analysis_context,
        )
    command = build_order_command(decision, risk, command_id='cmd-open-xyz')
    assert command.order_comment == build_open_order_comment('cmd-open-xyz')
