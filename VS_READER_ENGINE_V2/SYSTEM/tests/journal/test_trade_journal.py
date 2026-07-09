from __future__ import annotations

import json

import pytest

from engine.core.instance import Instance
from engine.core.paths import SystemPaths
from engine.journal.trade_journal import (
    INTENT_REASON_PREFIX,
    TradeIntentParams,
    append_trade_journal_entry,
    build_trade_ack_entry,
    build_trade_intent_entry,
    build_trade_journal_path,
    log_trade_ack,
    log_trade_intent,
    update_trade_journal_ack,
)
from engine.protocol.constants import AckStatus, Side, TradeEvent
from engine.protocol.models import AckRecord, TradeJournalEntry
from engine.protocol.parser import parse_trade_journal_line
from engine.protocol.writer import TRADE_JOURNAL_REQUIRED_FIELDS, write_trade_journal_entry
from tests.protocol.test_writer import required_fields_present


def _instance() -> Instance:
    return Instance(account_id="12345", symbol="EURUSD", magic=100001)


def _open_intent_params() -> TradeIntentParams:
    return TradeIntentParams(
        trade_id="trade-open-1",
        command_id="cmd-open-1",
        event=TradeEvent.OPEN.value,
        reason="OPEN BUY after risk allow",
        side=Side.BUY.value,
        volume=0.1,
        price=1.10310,
    )


def _modify_intent_params() -> TradeIntentParams:
    return TradeIntentParams(
        trade_id="trade-modify-1",
        command_id="cmd-modify-1",
        event=TradeEvent.MODIFY.value,
        reason="TRADE_MANAGEMENT_TRAILING: stop loss raised",
        ticket=1001,
        price=1.10350,
    )


def _close_intent_params() -> TradeIntentParams:
    return TradeIntentParams(
        trade_id="trade-close-1",
        command_id="cmd-close-1",
        event=TradeEvent.CLOSE.value,
        reason="TRADE_MANAGEMENT_TIME_STOP: maximum bars reached",
        ticket=1001,
        volume=0.1,
    )


def _ack_record(
    *,
    command_id: str,
    status: str = AckStatus.SUCCESS.value,
    ticket: int | None = 1001,
) -> AckRecord:
    return AckRecord(
        schema_version="1.0.0",
        timestamp_utc="2026-07-07T06:01:00.000Z",
        command_id=command_id,
        account_id="12345",
        symbol="EURUSD",
        magic=100001,
        status=status,
        ticket=ticket,
    )


def test_build_trade_journal_path_uses_instance_filename(tmp_path) -> None:
    paths = SystemPaths(root_path=tmp_path)

    journal_path = build_trade_journal_path(paths, _instance())

    assert journal_path.name == "trade_EURUSD_100001.jsonl"
    assert journal_path.parent.name == "journal"


def test_build_trade_intent_entry_maps_open_intent_fields() -> None:
    entry = build_trade_intent_entry(
        _instance(),
        _open_intent_params(),
        timestamp_utc="2026-07-07T06:00:00.000Z",
    )

    assert entry.trade_id == "trade-open-1"
    assert entry.command_id == "cmd-open-1"
    assert entry.event == TradeEvent.OPEN.value
    assert entry.side == Side.BUY.value
    assert entry.volume == pytest.approx(0.1)
    assert entry.price == pytest.approx(1.10310)
    assert entry.ack_status == AckStatus.REJECTED.value
    assert entry.reason.startswith(INTENT_REASON_PREFIX)


def test_build_trade_ack_entry_applies_ack_result() -> None:
    intent_entry = build_trade_intent_entry(
        _instance(),
        _open_intent_params(),
        timestamp_utc="2026-07-07T06:00:00.000Z",
    )

    ack_entry = build_trade_ack_entry(
        intent_entry,
        _ack_record(command_id="cmd-open-1", status=AckStatus.SUCCESS.value, ticket=555),
        timestamp_utc="2026-07-07T06:01:00.000Z",
        price=1.10315,
    )

    assert ack_entry.trade_id == intent_entry.trade_id
    assert ack_entry.command_id == "cmd-open-1"
    assert ack_entry.ack_status == AckStatus.SUCCESS.value
    assert ack_entry.ticket == 555
    assert ack_entry.price == pytest.approx(1.10315)
    assert not ack_entry.reason.startswith(INTENT_REASON_PREFIX)


def test_trade_journal_entry_contains_all_section_19_9_fields() -> None:
    entry = build_trade_intent_entry(
        _instance(),
        _open_intent_params(),
        timestamp_utc="2026-07-07T06:00:00.000Z",
    )

    data = json.loads(write_trade_journal_entry(entry))

    assert required_fields_present(data, TRADE_JOURNAL_REQUIRED_FIELDS)
    assert data["side"] == Side.BUY.value
    assert data["volume"] == pytest.approx(0.1)
    assert data["price"] == pytest.approx(1.10310)


def test_log_trade_intent_writes_open_intent_before_ack(tmp_path) -> None:
    paths = SystemPaths(root_path=tmp_path)
    instance = _instance()

    entry = log_trade_intent(
        paths,
        instance,
        _open_intent_params(),
        timestamp_utc="2026-07-07T06:00:00.000Z",
    )

    journal_text = build_trade_journal_path(paths, instance).read_text(encoding="utf-8")
    restored = parse_trade_journal_line(journal_text.strip())

    assert entry.event == TradeEvent.OPEN.value
    assert restored.command_id == "cmd-open-1"
    assert restored.ack_status == AckStatus.REJECTED.value
    assert restored.reason.startswith(INTENT_REASON_PREFIX)


def test_log_trade_ack_updates_entry_with_ack_result(tmp_path) -> None:
    paths = SystemPaths(root_path=tmp_path)
    instance = _instance()

    log_trade_intent(
        paths,
        instance,
        _open_intent_params(),
        timestamp_utc="2026-07-07T06:00:00.000Z",
    )
    updated = log_trade_ack(
        paths,
        instance,
        _ack_record(command_id="cmd-open-1", status=AckStatus.SUCCESS.value, ticket=555),
        timestamp_utc="2026-07-07T06:01:00.000Z",
        price=1.10315,
    )

    journal_text = build_trade_journal_path(paths, instance).read_text(encoding="utf-8")
    lines = [line for line in journal_text.splitlines() if line.strip()]
    restored = parse_trade_journal_line(lines[0])

    assert len(lines) == 1
    assert updated.ack_status == AckStatus.SUCCESS.value
    assert restored.ack_status == AckStatus.SUCCESS.value
    assert restored.ticket == 555
    assert restored.price == pytest.approx(1.10315)


def test_update_trade_journal_ack_rejects_missing_command_id(tmp_path) -> None:
    paths = SystemPaths(root_path=tmp_path)
    instance = _instance()

    log_trade_intent(
        paths,
        instance,
        _open_intent_params(),
        timestamp_utc="2026-07-07T06:00:00.000Z",
    )

    with pytest.raises(Exception, match="trade journal entry not found"):
        update_trade_journal_ack(
            paths,
            instance,
            _ack_record(command_id="cmd-missing", status=AckStatus.FAILED.value),
            timestamp_utc="2026-07-07T06:01:00.000Z",
        )


def test_append_trade_journal_entry_is_append_only_for_multiple_intents(tmp_path) -> None:
    paths = SystemPaths(root_path=tmp_path)
    instance = _instance()
    first = build_trade_intent_entry(
        instance,
        _open_intent_params(),
        timestamp_utc="2026-07-07T06:00:00.000Z",
    )
    second = build_trade_intent_entry(
        instance,
        _modify_intent_params(),
        timestamp_utc="2026-07-07T06:02:00.000Z",
    )

    append_trade_journal_entry(paths, instance, first)
    append_trade_journal_entry(paths, instance, second)

    journal_text = build_trade_journal_path(paths, instance).read_text(encoding="utf-8")
    lines = [line for line in journal_text.splitlines() if line.strip()]

    assert len(lines) == 2
    assert parse_trade_journal_line(lines[0]).event == TradeEvent.OPEN.value
    assert parse_trade_journal_line(lines[1]).event == TradeEvent.MODIFY.value


def test_log_trade_intent_supports_modify_and_close_events(tmp_path) -> None:
    paths = SystemPaths(root_path=tmp_path)
    instance = _instance()

    modify_entry = log_trade_intent(
        paths,
        instance,
        _modify_intent_params(),
        timestamp_utc="2026-07-07T06:02:00.000Z",
    )
    close_entry = log_trade_intent(
        paths,
        instance,
        _close_intent_params(),
        timestamp_utc="2026-07-07T06:03:00.000Z",
    )

    assert modify_entry.event == TradeEvent.MODIFY.value
    assert close_entry.event == TradeEvent.CLOSE.value

    journal_text = build_trade_journal_path(paths, instance).read_text(encoding="utf-8")
    events = [parse_trade_journal_line(line).event for line in journal_text.splitlines() if line.strip()]
    assert events == [TradeEvent.MODIFY.value, TradeEvent.CLOSE.value]


def test_trade_journal_is_isolated_by_instance(tmp_path) -> None:
    paths = SystemPaths(root_path=tmp_path)
    instance_a = Instance(account_id="12345", symbol="EURUSD", magic=100001)
    instance_b = Instance(account_id="12345", symbol="GBPUSD", magic=100002)

    log_trade_intent(
        paths,
        instance_a,
        _open_intent_params(),
        timestamp_utc="2026-07-07T06:00:00.000Z",
    )
    log_trade_intent(
        paths,
        instance_b,
        TradeIntentParams(
            trade_id="trade-gbp-1",
            command_id="cmd-gbp-1",
            event=TradeEvent.OPEN.value,
            reason="OPEN SELL after risk allow",
            side=Side.SELL.value,
            volume=0.2,
        ),
        timestamp_utc="2026-07-07T06:00:00.000Z",
    )

    path_a = build_trade_journal_path(paths, instance_a)
    path_b = build_trade_journal_path(paths, instance_b)

    assert path_a.exists()
    assert path_b.exists()
    assert path_a != path_b
    assert parse_trade_journal_line(path_a.read_text(encoding="utf-8").strip()).symbol == "EURUSD"
    assert parse_trade_journal_line(path_b.read_text(encoding="utf-8").strip()).symbol == "GBPUSD"


def test_log_trade_ack_records_failed_ack_status(tmp_path) -> None:
    paths = SystemPaths(root_path=tmp_path)
    instance = _instance()

    log_trade_intent(
        paths,
        instance,
        _open_intent_params(),
        timestamp_utc="2026-07-07T06:00:00.000Z",
    )
    updated = log_trade_ack(
        paths,
        instance,
        _ack_record(command_id="cmd-open-1", status=AckStatus.FAILED.value, ticket=None),
        timestamp_utc="2026-07-07T06:01:00.000Z",
    )

    assert updated.ack_status == AckStatus.FAILED.value
