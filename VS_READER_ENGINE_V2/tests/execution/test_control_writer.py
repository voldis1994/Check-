from __future__ import annotations

import os

import pytest

from engine.core import atomic_io
from engine.core.instance import Instance
from engine.core.paths import SystemPaths
from engine.execution.command import OrderCommand
from engine.execution.control_writer import (
    build_control_command,
    build_control_path,
    publish_control,
    write_control_file,
)
from engine.protocol.constants import OrderAction, PROTOCOL_SCHEMA_VERSION, Side
from engine.protocol.errors import DataIOError
from engine.protocol.models import ControlCommand
from engine.protocol.parser import parse_control, parse_json
from engine.protocol.writer import CONTROL_REQUIRED_FIELDS
from tests.protocol.test_writer import required_fields_present


def _instance() -> Instance:
    return Instance(account_id="12345", symbol="EURUSD", magic=100001)


def _open_order_command() -> OrderCommand:
    return OrderCommand(
        command_id="cmd-open-1",
        action=OrderAction.OPEN.value,
        reason="BUY: preferred side selected",
        decision_id="decision-123",
        side=Side.BUY.value,
        volume=0.1,
        stop_loss=1.09880,
        take_profit=1.11170,
    )


def _none_order_command() -> OrderCommand:
    return OrderCommand(
        command_id="cmd-none-1",
        action=OrderAction.NONE.value,
        reason="WAIT: equal scores",
        decision_id="decision-456",
    )


def test_build_control_path_uses_instance_filename(tmp_path) -> None:
    paths = SystemPaths(root_path=tmp_path)

    control_path = build_control_path(paths, _instance())

    assert control_path.name == "control_EURUSD_100001.json"
    assert control_path.parent.name == "12345"


def test_build_control_command_maps_order_command_and_instance_fields() -> None:
    instance = _instance()
    order_command = _open_order_command()

    control_command = build_control_command(
        instance,
        order_command,
        timestamp_utc="2026-07-07T06:00:00.000Z",
    )

    assert control_command.schema_version == PROTOCOL_SCHEMA_VERSION
    assert control_command.timestamp_utc == "2026-07-07T06:00:00.000Z"
    assert control_command.command_id == order_command.command_id
    assert control_command.account_id == instance.account_id
    assert control_command.symbol == instance.symbol
    assert control_command.magic == instance.magic
    assert control_command.action == OrderAction.OPEN.value
    assert control_command.side == Side.BUY.value
    assert control_command.volume == pytest.approx(0.1)
    assert control_command.stop_loss == pytest.approx(1.09880)
    assert control_command.take_profit == pytest.approx(1.11170)
    assert control_command.reason == order_command.reason
    assert control_command.decision_id == order_command.decision_id


def test_control_output_contains_all_section_19_4_fields(tmp_path) -> None:
    paths = SystemPaths(root_path=tmp_path)
    instance = _instance()

    control_command = publish_control(
        paths,
        instance,
        _open_order_command(),
        timestamp_utc="2026-07-07T06:00:00.000Z",
    )
    data = parse_json(build_control_path(paths, instance).read_text(encoding="utf-8"))

    assert required_fields_present(data, CONTROL_REQUIRED_FIELDS)
    assert data["schema_version"] == PROTOCOL_SCHEMA_VERSION
    assert data["side"] == Side.BUY.value
    assert control_command.schema_version == PROTOCOL_SCHEMA_VERSION


def test_write_control_file_uses_atomic_tmp_and_rename(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = SystemPaths(root_path=tmp_path)
    instance = _instance()
    control_command = build_control_command(
        instance,
        _open_order_command(),
        timestamp_utc="2026-07-07T06:00:00.000Z",
    )
    target_path = build_control_path(paths, instance)
    calls: list[str] = []
    original_fsync = os.fsync
    original_replace = os.replace

    def tracked_fsync(fd: int) -> None:
        calls.append("fsync")
        original_fsync(fd)

    def tracked_replace(src: os.PathLike[str] | str, dst: os.PathLike[str] | str) -> None:
        calls.append("replace")
        original_replace(src, dst)

    monkeypatch.setattr(atomic_io.os, "fsync", tracked_fsync)
    monkeypatch.setattr(atomic_io.os, "replace", tracked_replace)

    write_control_file(paths, instance, control_command)

    assert target_path.exists()
    assert not target_path.with_name(f"{target_path.name}.tmp").exists()
    assert calls == ["fsync", "replace"]


def test_write_control_file_rejects_instance_mismatch(tmp_path) -> None:
    paths = SystemPaths(root_path=tmp_path)
    instance = _instance()
    mismatched = ControlCommand(
        schema_version=PROTOCOL_SCHEMA_VERSION,
        timestamp_utc="2026-07-07T06:00:00.000Z",
        command_id="cmd-open-1",
        account_id="12345",
        symbol="GBPUSD",
        magic=100001,
        action=OrderAction.OPEN.value,
        reason="BUY selected",
        decision_id="decision-123",
        side=Side.BUY.value,
        volume=0.1,
    )

    with pytest.raises(DataIOError, match="instance does not match"):
        write_control_file(paths, instance, mismatched)


def test_publish_control_writes_parseable_control_json(tmp_path) -> None:
    paths = SystemPaths(root_path=tmp_path)
    instance = _instance()

    control_command = publish_control(
        paths,
        instance,
        _none_order_command(),
        timestamp_utc="2026-07-07T06:00:00.000Z",
    )
    restored = parse_control(build_control_path(paths, instance).read_text(encoding="utf-8"))

    assert control_command.action == OrderAction.NONE.value
    assert restored.command_id == "cmd-none-1"
    assert restored.decision_id == "decision-456"
    assert restored.account_id == instance.account_id
    assert restored.symbol == instance.symbol
    assert restored.magic == instance.magic


def test_publish_control_is_isolated_by_instance(tmp_path) -> None:
    paths = SystemPaths(root_path=tmp_path)
    instance_a = Instance(account_id="12345", symbol="EURUSD", magic=100001)
    instance_b = Instance(account_id="12345", symbol="GBPUSD", magic=100002)

    publish_control(
        paths,
        instance_a,
        _open_order_command(),
        timestamp_utc="2026-07-07T06:00:00.000Z",
    )
    publish_control(
        paths,
        instance_b,
        OrderCommand(
            command_id="cmd-gbp-1",
            action=OrderAction.OPEN.value,
            reason="SELL selected",
            decision_id="decision-789",
            side=Side.SELL.value,
            volume=0.2,
            stop_loss=1.20000,
            take_profit=1.19000,
        ),
        timestamp_utc="2026-07-07T06:01:00.000Z",
    )

    path_a = build_control_path(paths, instance_a)
    path_b = build_control_path(paths, instance_b)

    assert path_a.exists()
    assert path_b.exists()
    assert path_a != path_b
    assert parse_control(path_a.read_text(encoding="utf-8")).symbol == "EURUSD"
    assert parse_control(path_b.read_text(encoding="utf-8")).symbol == "GBPUSD"
