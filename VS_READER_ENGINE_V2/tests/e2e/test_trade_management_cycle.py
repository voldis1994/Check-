from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine.core.cycle import run_instance_cycle
from engine.core.instance import Instance
from engine.core.lifecycle import startup
from engine.core.paths import SystemPaths
from engine.core.history import read_archived_control_text
from engine.execution.control_writer import build_control_path
from engine.normalizer.market_normalizer import NormalizedMarketBar
from engine.protocol.constants import AckStatus, OrderAction, Side
from engine.protocol.parser import parse_control
from engine.state.instance_state import InstanceState
from tests.core.config_payload import valid_system_config_payload
from tests.e2e.simulator.mt4_simulator import MT4Simulator, build_market_csv
from tests.core.config_payload import FIXTURE_CYCLE_UTC
from tests.e2e.test_full_cycle import _patch_fixed_command_id, _startup_runtime


def _instance() -> Instance:
    return Instance(account_id="12345", symbol="EURUSD", magic=100001)


def _startup_runtime_for_trade_management(
    tmp_path: Path,
    *,
    trade_management_overrides: dict[str, object] | None = None,
):
    payload = valid_system_config_payload()
    payload["system"]["root_path"] = str(tmp_path)
    payload["analysis"]["lookback_bars"] = 3
    if trade_management_overrides is not None:
        payload["trade_management"] = {
            **payload["trade_management"],
            **trade_management_overrides,
        }
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "system.json"
    config_path.write_text(json.dumps(payload), encoding="utf-8")
    return startup(root_path=tmp_path, config_path=config_path)


def test_e2e_open_modify_cycle_updates_stop_loss(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_fixed_command_id(monkeypatch)
    paths = SystemPaths(tmp_path)
    simulator = MT4Simulator(paths)
    instance = _instance()
    runtime = _startup_runtime(tmp_path)
    simulator.export_tick(instance, market_scenario="bullish", timestamp_utc=FIXTURE_CYCLE_UTC)
    simulator.install_auto_ack_hook(monkeypatch)

    open_result = run_instance_cycle(
        runtime,
        instance,
        use_global_universe=False,
        timestamp_utc=FIXTURE_CYCLE_UTC,
    )
    assert open_result.completed
    state = InstanceState.load(paths, instance)
    assert state.open_ticket is not None
    original_stop_loss = state.position_stop_loss
    assert original_stop_loss is not None

    modify_timestamp = "2026-07-07T06:03:00.000Z"
    simulator.export_tick(
        instance,
        market_scenario="bullish",
        timestamp_utc=modify_timestamp,
        close_override=1.10800,
    )
    modify_result = run_instance_cycle(
        runtime,
        instance,
        use_global_universe=False,
        timestamp_utc=modify_timestamp,
    )
    assert modify_result.completed
    assert modify_result.execution_result is not None
    assert modify_result.execution_result.order_command.action == OrderAction.MODIFY.value

    updated_state = InstanceState.load(paths, instance)
    assert updated_state.open_ticket == state.open_ticket
    assert updated_state.position_stop_loss is not None
    assert updated_state.position_stop_loss > original_stop_loss
    assert updated_state.last_ack_status == AckStatus.SUCCESS.value

    archived_control_text = read_archived_control_text(paths, instance)
    assert archived_control_text is not None
    control = parse_control(archived_control_text)
    assert control.action == OrderAction.MODIFY.value


def test_e2e_open_close_cycle_clears_position(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_fixed_command_id(monkeypatch)
    paths = SystemPaths(tmp_path)
    simulator = MT4Simulator(paths)
    instance = _instance()
    runtime = _startup_runtime(tmp_path)
    simulator.export_tick(instance, market_scenario="bullish", timestamp_utc=FIXTURE_CYCLE_UTC)
    simulator.install_auto_ack_hook(monkeypatch)

    open_result = run_instance_cycle(
        runtime,
        instance,
        use_global_universe=False,
        timestamp_utc=FIXTURE_CYCLE_UTC,
    )
    assert open_result.completed
    item = runtime.memory.get_or_create(instance)
    item.instance_state.position_bars_open = 119
    item.instance_state.save(paths)

    close_timestamp = "2026-07-07T06:04:00.000Z"
    simulator.export_tick(instance, market_scenario="bullish", timestamp_utc=close_timestamp)
    close_result = run_instance_cycle(
        runtime,
        instance,
        use_global_universe=False,
        timestamp_utc=close_timestamp,
    )
    assert close_result.completed
    assert close_result.execution_result is not None
    assert close_result.execution_result.order_command.action == OrderAction.CLOSE.value

    cleared_state = InstanceState.load(paths, instance)
    assert cleared_state.open_ticket is None
    assert cleared_state.position_volume is None
    assert cleared_state.last_ack_status == AckStatus.SUCCESS.value


def test_e2e_open_partial_close_cycle_reduces_volume(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_fixed_command_id(monkeypatch)
    paths = SystemPaths(tmp_path)
    simulator = MT4Simulator(paths)
    instance = _instance()
    runtime = _startup_runtime_for_trade_management(
        tmp_path,
        trade_management_overrides={
            "time_stop_max_bars": 999,
            "breakeven_progress_ratio": 0.99,
        },
    )
    simulator.export_tick(instance, market_scenario="bullish", timestamp_utc=FIXTURE_CYCLE_UTC)
    simulator.install_auto_ack_hook(monkeypatch)

    open_result = run_instance_cycle(
        runtime,
        instance,
        use_global_universe=False,
        timestamp_utc=FIXTURE_CYCLE_UTC,
    )
    assert open_result.completed
    state = InstanceState.load(paths, instance)
    assert state.open_ticket is not None
    assert state.position_entry_price is not None
    assert state.position_take_profit is not None
    assert state.position_volume is not None
    original_volume = state.position_volume

    if state.position_side == Side.BUY.value:
        target_close = state.position_entry_price + 0.75 * (
            state.position_take_profit - state.position_entry_price
        )
    else:
        target_close = state.position_entry_price - 0.75 * (
            state.position_entry_price - state.position_take_profit
        )

    partial_timestamp = "2026-07-07T06:03:00.000Z"
    simulator.export_tick(
        instance,
        market_scenario="bullish",
        timestamp_utc=partial_timestamp,
        close_override=target_close,
    )
    partial_result = run_instance_cycle(
        runtime,
        instance,
        use_global_universe=False,
        timestamp_utc=partial_timestamp,
    )
    assert partial_result.completed
    assert partial_result.execution_result is not None
    assert partial_result.execution_result.order_command.action == OrderAction.CLOSE.value
    assert partial_result.execution_result.order_command.volume is not None
    assert partial_result.execution_result.order_command.volume < original_volume
    assert partial_result.execution_result.order_command.volume == pytest.approx(
        original_volume * 0.5,
        abs=0.01,
    )
    assert "PARTIAL_CLOSE" in partial_result.execution_result.order_command.reason

    updated_state = InstanceState.load(paths, instance)
    assert updated_state.open_ticket is not None
    assert updated_state.position_volume is not None
    assert updated_state.position_volume < original_volume
    assert updated_state.partial_close_applied is True
    assert updated_state.last_ack_status == AckStatus.SUCCESS.value

    archived_control_text = read_archived_control_text(paths, instance)
    assert archived_control_text is not None
    control = parse_control(archived_control_text)
    assert control.action == OrderAction.CLOSE.value
    assert control.volume is not None
    assert control.volume < original_volume
