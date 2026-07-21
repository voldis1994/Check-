"""PR #21 acceptance regressions: preexisting tickets, ACK, closed history, money-step trailing."""
from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

from engine.core.cycle import run_instance_trade_management_phase
from engine.core.instance import Instance
from engine.core.paths import SystemPaths
from engine.core.position_sync import (
    _archive_money_trailing_state,
    _status_matches_pending_open,
    _try_reconcile_closed_trade,
    find_status_positions,
)
from engine.execution.ack_reader import interpret_ack
from engine.execution.command_idempotence import CommandIdempotenceStore, try_execute_with_idempotence
from engine.execution.engine import apply_ack_to_instance_state, is_valid_open_fill_ack
from engine.execution.order_comment import build_open_order_comment
from engine.loader.closed_trade_loader import build_closed_trade_path, parse_closed_trade_payload
from engine.protocol.constants import PROTOCOL_SCHEMA_VERSION, AckStatus, OrderAction, Side
from engine.protocol.models import AckRecord, ControlCommand, StatusPositionSnapshot, StatusRecord
from engine.risk.money_step_trailing import (
    MoneyStepTrailingParams,
    MoneyStepTrailingState,
    choose_protective_sl,
    compute_locked_profit_money,
    compute_money_step_sl,
    compute_net_profit_money,
    evaluate_money_step_trailing,
    merge_technical_and_money_step_trailing,
    sl_improves,
)
from engine.risk.trade_management import TradeManagementResult
from engine.state.instance_state import InstanceState
from tests.mql4 import mql_source

SYSTEM_ROOT = Path(__file__).resolve().parents[2]


def _params(**overrides) -> MoneyStepTrailingParams:
    base = dict(
        enabled=True,
        activation_profit_money=5.0,
        profit_step_money=2.0,
        initial_locked_profit_money=1.0,
        lock_increment_money=2.0,
    )
    base.update(overrides)
    return MoneyStepTrailingParams(**base)


def _status(*, positions=(), tick_value=1.0, tick_size=0.00001, stop_level=0, freeze_level=0, timestamp_utc='2026-07-17T12:00:05.000Z') -> StatusRecord:
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
        tick_value=tick_value,
        tick_size=tick_size,
        stop_level=stop_level,
        freeze_level=freeze_level,
    )


def _pos(**kwargs) -> StatusPositionSnapshot:
    data = dict(
        symbol='EURUSD',
        magic=100001,
        ticket=555,
        side='BUY',
        volume=0.01,
        entry_price=1.1000,
        stop_loss=1.0900,
        take_profit=0.0,
        open_time_utc='2026-07-17T12:00:01.000Z',
        order_comment=build_open_order_comment('cmd-open-1'),
        profit=0.0,
        swap=0.0,
        commission=0.0,
    )
    data.update(kwargs)
    return StatusPositionSnapshot(**data)


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


def _ack(**overrides) -> AckRecord:
    data = dict(
        schema_version=PROTOCOL_SCHEMA_VERSION,
        timestamp_utc='2026-07-17T12:00:01.000Z',
        command_id='cmd-open-1',
        account_id='12345',
        symbol='EURUSD',
        magic=100001,
        status=AckStatus.SUCCESS.value,
        ticket=777,
        fill_price=1.1003,
        side='BUY',
        volume=0.01,
        open_time_utc='2026-07-17T12:00:01.000Z',
    )
    data.update(overrides)
    return AckRecord(**data)


def _open_cmd() -> ControlCommand:
    return ControlCommand(
        schema_version=PROTOCOL_SCHEMA_VERSION,
        timestamp_utc='2026-07-17T12:00:00.000Z',
        command_id='cmd-open-1',
        account_id='12345',
        symbol='EURUSD',
        magic=100001,
        action=OrderAction.OPEN.value,
        reason='entry',
        decision_id='dec-1',
        side=Side.BUY.value,
        volume=0.01,
        stop_loss=1.09,
        take_profit=0.0,
    )


def test_01_preexisting_tickets_collected_before_open_in_cycle_source() -> None:
    from engine.core import cycle as cycle_mod
    cycle_src = inspect.getsource(cycle_mod)
    assert 'entry_preexisting_tickets = tuple(p.ticket for p in find_status_positions(status, instance))' in cycle_src
    assert 'preexisting_tickets=entry_preexisting_tickets' in cycle_src


def test_02_preexisting_ticket_not_accepted_as_pending_result() -> None:
    state = _pending_state(pending_preexisting_tickets=(555,))
    assert _status_matches_pending_open(state, _pos(ticket=555)) is False
    assert _status_matches_pending_open(state, _pos(ticket=999)) is True


def test_03_repeated_command_id_does_not_open_second_order(tmp_path: Path) -> None:
    store = CommandIdempotenceStore(store_dir=tmp_path)
    opens: list[str] = []

    def execute_open(command_id: str) -> bool:
        opens.append(command_id)
        return True

    acks: list[tuple] = []

    def write_ack(command_id: str, *, success: bool, duplicate: bool) -> bool:
        acks.append((command_id, success, duplicate))
        return True

    first = try_execute_with_idempotence(
        command_id='cmd-1',
        account_id='12345',
        symbol='EURUSD',
        magic=100001,
        store=store,
        last_processed_command_id='',
        execute_open=execute_open,
        write_ack=write_ack,
    )
    second = try_execute_with_idempotence(
        command_id='cmd-1',
        account_id='12345',
        symbol='EURUSD',
        magic=100001,
        store=store,
        last_processed_command_id='cmd-1',
        execute_open=execute_open,
        write_ack=write_ack,
    )
    assert first[0] is True
    assert second[0] is False
    assert opens == ['cmd-1']
    assert acks[-1][2] is True


def test_04_already_processed_command_does_not_return_plain_success_ticket_zero() -> None:
    exec_src = mql_source.load_mqh('SYSTEM_Execution.mqh')
    assert 'SYSTEM_ACK_STATUS_ALREADY_PROCESSED' in exec_src
    assert 'result.status = SYSTEM_ACK_STATUS_ALREADY_PROCESSED' in exec_src
    assert is_valid_open_fill_ack(_ack(ticket=0, fill_price=None, side=None, volume=None)) is False


def test_05_already_processed_without_position_keeps_pending() -> None:
    state = _pending_state()
    ack = _ack(status=AckStatus.ALREADY_PROCESSED.value, ticket=0, fill_price=None, side=None, volume=None)
    interpretation = interpret_ack(ack)
    assert interpretation.is_already_processed is True
    assert interpretation.is_success is False
    apply_ack_to_instance_state(state, _open_cmd(), ack)
    assert state.pending_execution_command_id == 'cmd-open-1'
    assert state.open_ticket is None


def test_05b_success_ticket_zero_does_not_clear_pending() -> None:
    state = _pending_state()
    ack = _ack(ticket=0, fill_price=1.1, side='BUY', volume=0.01)
    assert is_valid_open_fill_ack(ack) is False
    apply_ack_to_instance_state(state, _open_cmd(), ack)
    assert state.pending_execution_command_id == 'cmd-open-1'


def test_06_closed_history_exports_side_and_volume() -> None:
    status_src = mql_source.load_mqh('SYSTEM_Status.mqh')
    assert 'OrderLots()' in status_src
    assert 'OrderType()' in status_src
    assert 'side' in status_src
    assert 'volume' in status_src
    assert 'SYSTEM_BuildClosedTradeJson' in status_src
    payload = {
        'account_id': '12345',
        'symbol': 'EURUSD',
        'magic': 100001,
        'ticket': 77,
        'close_price': 1.101,
        'close_time_utc': '2026-07-17T12:05:00.000Z',
        'profit': 1.5,
        'commission': -0.1,
        'swap': 0.0,
        'side': 'BUY',
        'volume': 0.01,
        'order_comment': 'cmd-x',
    }
    record = parse_closed_trade_payload(payload)
    assert record.side == 'BUY'
    assert record.volume == 0.01


def test_07_closed_history_side_volume_used_in_reconciliation(tmp_path: Path) -> None:
    paths = SystemPaths(tmp_path)
    instance = Instance('12345', 'EURUSD', 100001)
    paths.ensure_instance_directories(instance.account_id, instance.symbol, instance.magic)
    state = InstanceState(instance)
    state.set_close_pending(ticket=77, side='BUY', volume=0.01, since_utc='2026-07-17T12:00:00.000Z')
    state.apply_money_trailing_state(peak_net_profit_money=9.0, money_trailing_step_index=2, locked_profit_money=5.0, last_money_trailing_sl=1.095, ticket=77)
    closed_path = build_closed_trade_path(paths, instance)
    closed_path.write_text(json.dumps({
        'account_id': '12345',
        'symbol': 'EURUSD',
        'magic': 100001,
        'ticket': 77,
        'close_price': 1.101,
        'close_time_utc': '2026-07-17T12:05:00.000Z',
        'profit': 1.5,
        'commission': -0.1,
        'swap': 0.0,
        'side': 'SELL',
        'volume': 0.01,
    }), encoding='utf-8')
    assert _try_reconcile_closed_trade(paths, instance, state, timestamp_utc='2026-07-17T12:06:00.000Z') is False
    assert state.close_pending_reconciliation is True


def test_08_money_trailing_not_activated_before_activation() -> None:
    ev, new_state = evaluate_money_step_trailing(
        params=_params(),
        state=MoneyStepTrailingState(),
        side='BUY',
        open_price=1.1,
        current_sl=1.09,
        net_profit_money=4.9,
        current_swap=0.0,
        current_commission=0.0,
        tick_value=1.0,
        tick_size=0.00001,
        volume=0.01,
        digits=5,
    )
    assert ev.activated is False
    assert ev.money_step_sl is None
    assert new_state.locked_profit_money == 0.0


def test_09_activation_locks_initial_profit() -> None:
    assert compute_locked_profit_money(completed_steps=0, params=_params()) == 1.0
    ev, new_state = evaluate_money_step_trailing(
        params=_params(),
        state=MoneyStepTrailingState(),
        side='BUY',
        open_price=1.1,
        current_sl=1.09,
        net_profit_money=5.0,
        current_swap=0.0,
        current_commission=0.0,
        tick_value=1.0,
        tick_size=0.00001,
        volume=0.01,
        digits=5,
    )
    assert ev.activated is True
    assert ev.completed_steps == 0
    assert new_state.locked_profit_money == 1.0


def test_10_each_profit_step_increases_locked() -> None:
    params = _params()
    assert compute_locked_profit_money(completed_steps=0, params=params) == 1.0
    assert compute_locked_profit_money(completed_steps=1, params=params) == 3.0
    assert compute_locked_profit_money(completed_steps=2, params=params) == 5.0
    assert compute_locked_profit_money(completed_steps=3, params=params) == 7.0


def test_11_profit_retreat_does_not_reduce_locked() -> None:
    state = MoneyStepTrailingState(peak_net_profit_money=11.0, money_trailing_step_index=3, locked_profit_money=7.0)
    ev, new_state = evaluate_money_step_trailing(
        params=_params(),
        state=state,
        side='BUY',
        open_price=1.1,
        current_sl=1.09,
        net_profit_money=6.0,
        current_swap=0.0,
        current_commission=0.0,
        tick_value=1.0,
        tick_size=0.00001,
        volume=0.01,
        digits=5,
    )
    assert new_state.peak_net_profit_money == 11.0
    assert new_state.locked_profit_money == 7.0
    assert ev.locked_profit_money == 7.0


def test_12_buy_sl_never_moves_down() -> None:
    assert sl_improves(side='BUY', current_sl=1.095, proposed_sl=1.094, tolerance=0.00001) is False
    assert choose_protective_sl(side='BUY', current_sl=1.095, technical_sl=1.094, money_sl=1.093) == 1.095


def test_13_sell_sl_never_moves_up() -> None:
    assert sl_improves(side='SELL', current_sl=1.105, proposed_sl=1.106, tolerance=0.00001) is False
    assert choose_protective_sl(side='SELL', current_sl=1.105, technical_sl=1.106, money_sl=1.107) == 1.105


def test_14_money_step_never_weakens_technical() -> None:
    assert choose_protective_sl(side='BUY', current_sl=1.09, technical_sl=1.098, money_sl=1.095) == 1.098


def test_15_technical_never_weakens_money_step() -> None:
    assert choose_protective_sl(side='BUY', current_sl=1.09, technical_sl=1.094, money_sl=1.098) == 1.098


def test_16_identical_sl_not_resent() -> None:
    money_sl = compute_money_step_sl(
        side='BUY',
        open_price=1.1,
        locked_profit_money=1.0,
        current_swap=0.0,
        current_commission=0.0,
        tick_value=1.0,
        tick_size=0.00001,
        volume=0.01,
        digits=5,
    )
    merge = merge_technical_and_money_step_trailing(
        technical_result=TradeManagementResult(action=OrderAction.NONE.value, reason=''),
        params=_params(),
        state=MoneyStepTrailingState(peak_net_profit_money=5.0, money_trailing_step_index=0, locked_profit_money=1.0, last_money_trailing_sl=money_sl),
        side='BUY',
        open_price=1.1,
        current_sl=money_sl,
        current_price=1.12,
        net_profit_money=5.0,
        current_swap=0.0,
        current_commission=0.0,
        tick_value=1.0,
        tick_size=0.00001,
        volume=0.01,
        digits=5,
        point=0.00001,
        stop_level=0,
        freeze_level=0,
        price_tolerance=0.00001,
        modify_take_profit=0.0,
        sensor_fresh=True,
    )
    assert merge.management_result.action == OrderAction.NONE.value


def test_17_stale_bid_ask_blocks_money_modify() -> None:
    merge = merge_technical_and_money_step_trailing(
        technical_result=TradeManagementResult(action=OrderAction.NONE.value, reason=''),
        params=_params(),
        state=MoneyStepTrailingState(),
        side='BUY',
        open_price=1.1,
        current_sl=1.09,
        current_price=1.12,
        net_profit_money=9.0,
        current_swap=0.0,
        current_commission=0.0,
        tick_value=1.0,
        tick_size=0.00001,
        volume=0.01,
        digits=5,
        point=0.00001,
        stop_level=0,
        freeze_level=0,
        price_tolerance=0.00001,
        modify_take_profit=0.0,
        sensor_fresh=False,
    )
    assert merge.management_result.action == OrderAction.NONE.value
    assert 'stale' in merge.skip_reason


def test_18_invalid_tick_blocks_modify() -> None:
    merge = merge_technical_and_money_step_trailing(
        technical_result=TradeManagementResult(action=OrderAction.NONE.value, reason=''),
        params=_params(),
        state=MoneyStepTrailingState(),
        side='BUY',
        open_price=1.1,
        current_sl=1.09,
        current_price=1.12,
        net_profit_money=9.0,
        current_swap=0.0,
        current_commission=0.0,
        tick_value=0.0,
        tick_size=0.00001,
        volume=0.01,
        digits=5,
        point=0.00001,
        stop_level=0,
        freeze_level=0,
        price_tolerance=0.00001,
        modify_take_profit=0.0,
        sensor_fresh=True,
    )
    assert merge.management_result.action == OrderAction.NONE.value
    assert 'invalid_tick' in merge.skip_reason


def test_18b_invalid_tick_keeps_technical_trailing() -> None:
    technical = TradeManagementResult(action=OrderAction.MODIFY.value, reason='TRADE_MANAGEMENT_TRAILING', stop_loss=1.101, take_profit=0.0)
    merge = merge_technical_and_money_step_trailing(
        technical_result=technical,
        params=_params(),
        state=MoneyStepTrailingState(),
        side='BUY',
        open_price=1.1,
        current_sl=1.09,
        current_price=1.12,
        net_profit_money=9.0,
        current_swap=0.0,
        current_commission=0.0,
        tick_value=0.0,
        tick_size=0.00001,
        volume=0.01,
        digits=5,
        point=0.00001,
        stop_level=0,
        freeze_level=0,
        price_tolerance=0.00001,
        modify_take_profit=0.0,
        sensor_fresh=True,
    )
    assert merge.management_result.action == OrderAction.MODIFY.value
    assert merge.management_result.stop_loss == pytest.approx(1.101)
    assert 'invalid_tick' in merge.skip_reason


def test_19_stop_and_freeze_levels_respected() -> None:
    merge = merge_technical_and_money_step_trailing(
        technical_result=TradeManagementResult(action=OrderAction.NONE.value, reason=''),
        params=_params(),
        state=MoneyStepTrailingState(),
        side='BUY',
        open_price=1.1,
        current_sl=1.09,
        current_price=1.1005,
        net_profit_money=9.0,
        current_swap=0.0,
        current_commission=0.0,
        tick_value=1.0,
        tick_size=0.00001,
        volume=0.01,
        digits=5,
        point=0.00001,
        stop_level=100,
        freeze_level=50,
        price_tolerance=0.00001,
        modify_take_profit=0.0,
        sensor_fresh=True,
    )
    assert merge.management_result.action == OrderAction.NONE.value
    assert 'stop_freeze' in merge.skip_reason


def test_20_commission_and_swap_in_locked_net_profit() -> None:
    net = compute_net_profit_money(profit=10.0, swap=-0.5, commission=-0.2)
    assert net == pytest.approx(9.3)
    sl = compute_money_step_sl(
        side='BUY',
        open_price=1.1,
        locked_profit_money=5.0,
        current_swap=-0.5,
        current_commission=-0.2,
        tick_value=1.0,
        tick_size=0.00001,
        volume=0.01,
        digits=5,
    )
    expected = round(1.1 + 5.7 / ((1.0 / 0.00001) * 0.01), 5)
    assert sl == expected


def test_21_money_trailing_state_persists_across_restart(tmp_path: Path) -> None:
    paths = SystemPaths(tmp_path)
    instance = Instance('12345', 'EURUSD', 100001)
    paths.ensure_account_directories(instance.account_id)
    state = InstanceState(instance)
    state.update_position(open_ticket=555, position_side='BUY', position_volume=0.01, entry_price=1.1, stop_loss=1.09, take_profit=0.0)
    state.apply_money_trailing_state(peak_net_profit_money=11.0, money_trailing_step_index=3, locked_profit_money=7.0, last_money_trailing_sl=1.097, ticket=555)
    state.save(paths)
    loaded = InstanceState.load(paths, instance)
    assert loaded.peak_net_profit_money == 11.0
    assert loaded.money_trailing_step_index == 3
    assert loaded.locked_profit_money == 7.0
    assert loaded.last_money_trailing_sl == 1.097
    assert loaded.money_trailing_ticket == 555


def test_22_closed_ticket_money_state_cleared_and_archived(tmp_path: Path) -> None:
    paths = SystemPaths(tmp_path)
    instance = Instance('12345', 'EURUSD', 100001)
    paths.ensure_instance_directories(instance.account_id, instance.symbol, instance.magic)
    state = InstanceState(instance)
    state.update_position(open_ticket=88, position_side='BUY', position_volume=0.01, entry_price=1.1, stop_loss=1.09)
    state.apply_money_trailing_state(peak_net_profit_money=9.0, money_trailing_step_index=2, locked_profit_money=5.0, last_money_trailing_sl=1.095, ticket=88)
    _archive_money_trailing_state(paths, instance, state)
    archive = paths.instance_history_dir(instance.account_id, instance.symbol, instance.magic) / 'money_trailing_88.json'
    assert archive.exists()
    state.clear_position()
    assert state.peak_net_profit_money == 0.0
    assert state.money_trailing_step_index == -1
    assert state.locked_profit_money == 0.0
    assert state.last_money_trailing_sl is None


def test_23_fixed_tp_not_added() -> None:
    cfg = json.loads((SYSTEM_ROOT / 'config' / 'system.json').read_text(encoding='utf-8'))
    assert cfg['trade_management']['use_fixed_take_profit'] is False
    assert 'use_fixed_take_profit' in inspect.getsource(run_instance_trade_management_phase)


def test_24_percent_account_risk_not_restored() -> None:
    risk_src = (SYSTEM_ROOT / 'engine' / 'risk' / 'position_sizing.py').read_text(encoding='utf-8')
    assert 'risk_percent' not in risk_src
    assert 'percent_of_balance' not in risk_src
    cfg = json.loads((SYSTEM_ROOT / 'config' / 'system.json').read_text(encoding='utf-8'))
    assert 'risk_percent' not in cfg['risk']
    assert cfg['risk']['fixed_lot_volume'] > 0


def test_25_fixed_lot_unchanged() -> None:
    cfg = json.loads((SYSTEM_ROOT / 'config' / 'system.json').read_text(encoding='utf-8'))
    assert cfg['risk']['fixed_lot_volume'] == 0.01


def test_26_buy_sell_score_and_entry_strategy_unchanged() -> None:
    decision_src = (SYSTEM_ROOT / 'engine' / 'decision' / 'engine.py').read_text(encoding='utf-8')
    assert 'buy_score' in decision_src and 'sell_score' in decision_src
    assert 'money_step' not in decision_src
    analysis_dir = SYSTEM_ROOT / 'engine' / 'analysis'
    for path in analysis_dir.rglob('*.py'):
        assert 'money_step' not in path.read_text(encoding='utf-8')


def test_money_step_config_invalid_values_not_runnable() -> None:
    assert _params(activation_profit_money=0.0).is_runnable() is False
    assert _params(enabled=True, activation_profit_money=5.0, profit_step_money=0.0).is_runnable() is False
    assert _params(initial_locked_profit_money=5.0, activation_profit_money=5.0).is_runnable() is False


def test_find_status_positions_used_for_preexisting() -> None:
    status = _status(positions=(_pos(ticket=10), _pos(ticket=11, magic=100002)))
    instance = Instance('12345', 'EURUSD', 100001)
    tickets = tuple(p.ticket for p in find_status_positions(status, instance))
    assert tickets == (10,)


def test_money_step_wired_into_trade_management_phase() -> None:
    src = inspect.getsource(run_instance_trade_management_phase)
    assert 'merge_technical_and_money_step_trailing' in src
    assert 'money_step_trailing' in src
