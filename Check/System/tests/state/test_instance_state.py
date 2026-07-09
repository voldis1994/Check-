from __future__ import annotations
import pytest
from engine.core.instance import Instance
from engine.core.paths import SystemPaths
from engine.state.instance_state import InstanceState

def test_instance_state_contains_all_spec_72_3_fields(tmp_path) -> None:
    instance = Instance(account_id='12345', symbol='EURUSD', magic=100001)
    state = InstanceState(instance=instance)
    state.update_cycle(decision='WAIT', reason='NO_SIGNAL', cycle_utc='2026-07-07T06:00:00.000Z')
    state.update_execution(command_id='cmd-1', ack_status='SUCCESS')
    state.update_instrument(digits=5, point=1e-05, pip=0.0001)
    state.update_position(open_ticket=123456, position_side='BUY', position_volume=0.1)
    payload = state.to_dict()
    assert payload['last_decision'] == 'WAIT'
    assert payload['last_reason'] == 'NO_SIGNAL'
    assert payload['open_ticket'] == 123456
    assert payload['position_side'] == 'BUY'
    assert payload['position_volume'] == 0.1
    assert payload['last_command_id'] == 'cmd-1'
    assert payload['last_ack_status'] == 'SUCCESS'
    assert payload['instrument_digits'] == 5
    assert payload['instrument_point'] == 1e-05
    assert payload['instrument_pip'] == 0.0001
    assert payload['cycle_count'] == 1

def test_instance_state_persist_and_load(tmp_path) -> None:
    paths = SystemPaths(root_path=tmp_path)
    instance = Instance(account_id='12345', symbol='EURUSD', magic=100001)
    state = InstanceState(instance=instance)
    state.update_cycle(decision='BUY', reason='TREND_UP', cycle_utc='2026-07-07T06:01:00.000Z')
    state.update_execution(command_id='cmd-2', ack_status='SUCCESS')
    state.update_instrument(digits=5, point=1e-05, pip=0.0001)
    state.update_position(open_ticket=900001, position_side='BUY', position_volume=0.2)
    state.save(paths)
    loaded = InstanceState.load(paths, instance)
    assert loaded.last_decision == 'BUY'
    assert loaded.last_reason == 'TREND_UP'
    assert loaded.last_command_id == 'cmd-2'
    assert loaded.last_ack_status == 'SUCCESS'
    assert loaded.instrument_digits == 5
    assert loaded.instrument_point == 1e-05
    assert loaded.instrument_pip == 0.0001
    assert loaded.open_ticket == 900001
    assert loaded.position_side == 'BUY'
    assert loaded.position_volume == 0.2

def test_instance_state_clears_position_fields_after_close(tmp_path) -> None:
    instance = Instance(account_id='12345', symbol='EURUSD', magic=100001)
    state = InstanceState(instance=instance)
    state.update_position(open_ticket=900001, position_side='SELL', position_volume=0.3, entry_price=1.105, stop_loss=1.107, take_profit=1.101)
    state.clear_position()
    payload = state.to_dict()
    assert 'open_ticket' not in payload
    assert 'position_side' not in payload
    assert 'position_volume' not in payload
    assert 'position_entry_price' not in payload
    assert 'position_stop_loss' not in payload
    assert 'position_take_profit' not in payload

def test_instance_state_tracks_position_bars_and_partial_close(tmp_path) -> None:
    instance = Instance(account_id='12345', symbol='EURUSD', magic=100001)
    state = InstanceState(instance=instance)
    state.update_position(open_ticket=900001, position_side='BUY', position_volume=0.2, entry_price=1.1, stop_loss=1.098, take_profit=1.104)
    assert state.position_bars_open == 1
    assert state.partial_close_applied is False
    state.increment_position_bars()
    assert state.position_bars_open == 2
    state.reduce_position_volume(volume=0.1)
    assert state.position_volume == pytest.approx(0.1)
    assert state.partial_close_applied is True
    payload = state.to_dict()
    assert payload['position_bars_open'] == 2
    assert payload['partial_close_applied'] is True

def test_instance_state_persists_position_management_fields(tmp_path) -> None:
    paths = SystemPaths(root_path=tmp_path)
    instance = Instance(account_id='12345', symbol='EURUSD', magic=100001)
    state = InstanceState(instance=instance)
    state.update_position(open_ticket=900001, position_side='BUY', position_volume=0.2, entry_price=1.1, stop_loss=1.098, take_profit=1.104)
    state.increment_position_bars()
    state.reduce_position_volume(volume=0.05)
    state.save(paths)
    loaded = InstanceState.load(paths, instance)
    assert loaded.position_bars_open == 2
    assert loaded.partial_close_applied is True
    assert loaded.position_volume == pytest.approx(0.15)
