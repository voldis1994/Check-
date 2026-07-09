from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from engine.core.instance import Instance
from engine.core.lifecycle import startup
from engine.core.paths import SystemPaths
from engine.core.position_sync import reconcile_position_with_status
from engine.protocol.constants import PROTOCOL_SCHEMA_VERSION, Side
from engine.protocol.models import StatusPositionSnapshot, StatusRecord
from engine.protocol.writer import write_status
from engine.state.instance_state import InstanceState
from tests.core.config_payload import valid_system_config_payload


FIXTURES_DIR = Path(__file__).parent.parent / "loader" / "fixtures"


def _write_config(root: Path) -> Path:
    payload = valid_system_config_payload()
    payload["system"]["root_path"] = str(root)
    config_dir = root / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "system.json"
    config_path.write_text(json.dumps(payload), encoding="utf-8")
    return config_path


def _instance() -> Instance:
    return Instance(account_id="12345", symbol="EURUSD", magic=100001)


def _install_fixtures(paths: SystemPaths, instance: Instance) -> None:
    paths.ensure_account_directories(instance.account_id)
    account_dir = paths.account_dir(instance.account_id)
    shutil.copyfile(FIXTURES_DIR / "status_valid.json", account_dir / instance.status_filename())


def _status_without_position() -> StatusRecord:
    return StatusRecord(
        schema_version=PROTOCOL_SCHEMA_VERSION,
        timestamp_utc="2026-07-07T06:00:00.000Z",
        account_id="12345",
        connected=True,
        trade_allowed=True,
        balance=10000.0,
        equity=10020.5,
        margin_free=9800.0,
        ea_version="1.0.0",
        open_positions=(),
    )


def _status_with_position(*, ticket: int = 555, volume: float = 0.1) -> StatusRecord:
    return StatusRecord(
        schema_version=PROTOCOL_SCHEMA_VERSION,
        timestamp_utc="2026-07-07T06:00:00.000Z",
        account_id="12345",
        connected=True,
        trade_allowed=True,
        balance=10000.0,
        equity=10020.5,
        margin_free=9800.0,
        ea_version="1.0.0",
        open_positions=(
            StatusPositionSnapshot(
                symbol="EURUSD",
                magic=100001,
                ticket=ticket,
                side=Side.BUY.value,
                volume=volume,
                entry_price=1.10150,
                stop_loss=1.09880,
                take_profit=1.11170,
            ),
        ),
    )


def test_reconcile_position_with_status_clears_state_on_external_close(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path)
    instance = _instance()
    paths = SystemPaths(tmp_path)
    _install_fixtures(paths, instance)
    runtime = startup(root_path=tmp_path, config_path=config_path)
    state = runtime.memory.get_or_create(instance).instance_state
    state.update_position(
        open_ticket=555,
        position_side=Side.BUY.value,
        position_volume=0.1,
        entry_price=1.10150,
        stop_loss=1.09880,
        take_profit=1.11170,
    )

    result = reconcile_position_with_status(
        runtime.paths,
        instance,
        state,
        _status_without_position(),
        timestamp_utc="2026-07-07T06:02:00.000Z",
    )

    assert result.external_close is True
    assert result.trade_journal_logged is True
    assert state.open_ticket is None


def test_reconcile_position_with_status_syncs_open_position_from_status(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path)
    instance = _instance()
    paths = SystemPaths(tmp_path)
    _install_fixtures(paths, instance)
    runtime = startup(root_path=tmp_path, config_path=config_path)
    state = runtime.memory.get_or_create(instance).instance_state

    changed = reconcile_position_with_status(
        runtime.paths,
        instance,
        state,
        _status_with_position(ticket=777, volume=0.2),
        timestamp_utc="2026-07-07T06:02:00.000Z",
    ).changed

    assert changed is True
    assert state.open_ticket == 777
    assert state.position_volume == 0.2


def test_reconcile_position_with_status_logs_partial_close(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path)
    instance = _instance()
    paths = SystemPaths(tmp_path)
    _install_fixtures(paths, instance)
    runtime = startup(root_path=tmp_path, config_path=config_path)
    state = runtime.memory.get_or_create(instance).instance_state
    state.update_position(
        open_ticket=555,
        position_side=Side.BUY.value,
        position_volume=0.2,
        entry_price=1.10150,
        stop_loss=1.09880,
        take_profit=1.11170,
    )

    result = reconcile_position_with_status(
        runtime.paths,
        instance,
        state,
        _status_with_position(ticket=555, volume=0.1),
        timestamp_utc="2026-07-07T06:02:00.000Z",
    )

    assert result.external_partial_close is True
    assert result.trade_journal_logged is True
    assert state.open_ticket == 555
    assert state.position_volume == 0.1


def test_reconcile_position_does_not_clear_when_other_instance_position_present(
    tmp_path: Path,
) -> None:
    config_path = _write_config(tmp_path)
    instance = _instance()
    paths = SystemPaths(tmp_path)
    _install_fixtures(paths, instance)
    runtime = startup(root_path=tmp_path, config_path=config_path)
    state = runtime.memory.get_or_create(instance).instance_state
    state.update_position(
        open_ticket=555,
        position_side=Side.BUY.value,
        position_volume=0.1,
        entry_price=1.10150,
        stop_loss=1.09880,
        take_profit=1.11170,
    )

    status = StatusRecord(
        schema_version=PROTOCOL_SCHEMA_VERSION,
        timestamp_utc="2026-07-07T06:00:00.000Z",
        account_id="12345",
        connected=True,
        trade_allowed=True,
        balance=10000.0,
        equity=10020.5,
        margin_free=9800.0,
        ea_version="1.0.0",
        open_positions=(
            StatusPositionSnapshot(
                symbol="EURUSD",
                magic=100001,
                ticket=555,
                side=Side.BUY.value,
                volume=0.1,
                entry_price=1.10150,
                stop_loss=1.09880,
                take_profit=1.11170,
            ),
            StatusPositionSnapshot(
                symbol="GBPUSD",
                magic=100002,
                ticket=888,
                side=Side.SELL.value,
                volume=0.05,
                entry_price=1.25000,
                stop_loss=1.25500,
                take_profit=1.24000,
            ),
        ),
    )

    result = reconcile_position_with_status(
        runtime.paths,
        instance,
        state,
        status,
        timestamp_utc="2026-07-07T06:02:00.000Z",
    )

    assert result.external_close is False
    assert state.open_ticket == 555


def test_status_round_trip_includes_open_positions() -> None:
    status = _status_with_position()
    payload = json.loads(write_status(status))
    assert len(payload["open_positions"]) == 1
    assert payload["open_positions"][0]["ticket"] == 555
