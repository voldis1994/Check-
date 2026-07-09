from __future__ import annotations
from engine.core.instance import Instance
from engine.core.paths import SystemPaths
from engine.normalizer.spread_model import update_spread_model
from engine.state.spread_state import SpreadState

def test_spread_state_updates_from_spread_model_snapshot(tmp_path) -> None:
    instance = Instance(account_id='12345', symbol='EURUSD', magic=100001)
    state = SpreadState(instance=instance)
    snapshot = update_spread_model((0.0001, 0.0002), current_spread=0.0003, lookback_bars=10)
    record = state.update_from_snapshot(snapshot, '2026-07-07T06:00:00.000Z')
    assert record.sample_count == 3
    assert record.mean_spread == snapshot.mean_spread
    assert record.std_spread == snapshot.std_spread
    assert record.median_spread == snapshot.median_spread
    assert record.current_spread == snapshot.current_spread
    assert record.relative_spread == snapshot.relative_spread

def test_spread_state_persists_and_loads_from_disk(tmp_path) -> None:
    paths = SystemPaths(root_path=tmp_path)
    instance = Instance(account_id='12345', symbol='EURUSD', magic=100001)
    snapshot = update_spread_model((0.0001, 0.0002), current_spread=0.0003, lookback_bars=10)
    state = SpreadState(instance=instance)
    state.update_from_snapshot(snapshot, '2026-07-07T06:00:00.000Z')
    state.save(paths)
    loaded = SpreadState.load(paths, instance)
    assert loaded.record is not None
    assert loaded.record.account_id == '12345'
    assert loaded.record.symbol == 'EURUSD'
    assert loaded.record.magic == 100001
    assert loaded.record.sample_count == snapshot.sample_count

def test_spread_state_isolated_per_instance(tmp_path) -> None:
    paths = SystemPaths(root_path=tmp_path)
    instance_a = Instance(account_id='12345', symbol='EURUSD', magic=100001)
    instance_b = Instance(account_id='12345', symbol='GBPUSD', magic=100002)
    snapshot_a = update_spread_model((0.0001,), current_spread=0.0002, lookback_bars=10)
    snapshot_b = update_spread_model((0.0003,), current_spread=0.0004, lookback_bars=10)
    state_a = SpreadState(instance=instance_a)
    state_b = SpreadState(instance=instance_b)
    state_a.update_from_snapshot(snapshot_a, '2026-07-07T06:00:00.000Z')
    state_b.update_from_snapshot(snapshot_b, '2026-07-07T06:00:01.000Z')
    state_a.save(paths)
    state_b.save(paths)
    loaded_a = SpreadState.load(paths, instance_a)
    loaded_b = SpreadState.load(paths, instance_b)
    assert loaded_a.record is not None
    assert loaded_b.record is not None
    assert loaded_a.record.symbol == 'EURUSD'
    assert loaded_b.record.symbol == 'GBPUSD'
    assert loaded_a.record.current_spread != loaded_b.record.current_spread
