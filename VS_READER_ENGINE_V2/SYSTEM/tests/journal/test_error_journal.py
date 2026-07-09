from __future__ import annotations

import pytest

from engine.core.instance import Instance
from engine.core.paths import SystemPaths
from engine.journal.error_journal import append_error_journal_entry, build_error_journal_path, log_error
from engine.protocol.models import ErrorJournalEntry
from engine.protocol.parser import parse_error_journal_line


def test_error_journal_entry_with_all_required_fields() -> None:
    entry = ErrorJournalEntry(
        error_id="err-1",
        timestamp_utc="2026-07-07T06:00:00.000Z",
        account_id="12345",
        symbol="EURUSD",
        magic=100001,
        module="validator.market",
        error_type="VALIDATION",
        message="market csv invalid",
        context={"row": 2},
    )
    line = entry.to_dict()
    assert line["error_id"] == "err-1"
    assert line["timestamp_utc"] == "2026-07-07T06:00:00.000Z"
    assert line["account_id"] == "12345"
    assert line["module"] == "validator.market"
    assert line["error_type"] == "VALIDATION"
    assert line["message"] == "market csv invalid"


def test_error_journal_is_append_only(tmp_path) -> None:
    paths = SystemPaths(root_path=tmp_path)
    instance = Instance(account_id="12345", symbol="EURUSD", magic=100001)
    first = ErrorJournalEntry(
        error_id="err-1",
        timestamp_utc="2026-07-07T06:00:00.000Z",
        account_id="12345",
        symbol="EURUSD",
        magic=100001,
        module="module.a",
        error_type="VALIDATION",
        message="first error",
    )
    second = ErrorJournalEntry(
        error_id="err-2",
        timestamp_utc="2026-07-07T06:01:00.000Z",
        account_id="12345",
        symbol="EURUSD",
        magic=100001,
        module="module.b",
        error_type="PROTOCOL",
        message="second error",
    )

    append_error_journal_entry(paths, instance, first)
    append_error_journal_entry(paths, instance, second)

    journal_text = build_error_journal_path(paths, instance).read_text(encoding="utf-8")
    lines = [line for line in journal_text.splitlines() if line.strip()]
    assert len(lines) == 2
    assert parse_error_journal_line(lines[0]).error_id == "err-1"
    assert parse_error_journal_line(lines[1]).error_id == "err-2"


def test_error_journal_is_isolated_by_instance(tmp_path) -> None:
    paths = SystemPaths(root_path=tmp_path)
    instance_a = Instance(account_id="12345", symbol="EURUSD", magic=100001)
    instance_b = Instance(account_id="12345", symbol="GBPUSD", magic=100002)

    log_error(
        paths,
        instance_a,
        module="module.a",
        error_type="VALIDATION",
        message="error A",
    )
    log_error(
        paths,
        instance_b,
        module="module.b",
        error_type="PROTOCOL",
        message="error B",
    )

    path_a = build_error_journal_path(paths, instance_a)
    path_b = build_error_journal_path(paths, instance_b)
    assert path_a.exists()
    assert path_b.exists()
    assert path_a != path_b


def test_error_journal_has_no_silent_exception(tmp_path) -> None:
    paths = SystemPaths(root_path=tmp_path)
    instance = Instance(account_id="12345", symbol="EURUSD", magic=100001)

    with pytest.raises(Exception):
        log_error(
            paths,
            instance,
            module="module.invalid",
            error_type="NOT_A_VALID_TYPE",
            message="this must fail loudly",
        )
