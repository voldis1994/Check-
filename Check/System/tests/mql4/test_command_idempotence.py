from __future__ import annotations

from engine.execution.command_idempotence import (
    CommandIdempotenceStore,
    command_id_hash,
    processed_command_gv_name,
    try_execute_with_idempotence,
)
from tests.mql4 import mql_source


def test_processed_command_gv_name_matches_mql_convention() -> None:
    assert processed_command_gv_name('12345', 'EURUSD', 100001) == 'SYSTEM_CMD_12345_EURUSD_100001'


def test_command_id_hash_is_deterministic() -> None:
    assert command_id_hash('cmd-1') == command_id_hash('cmd-1')
    assert command_id_hash('cmd-1') != command_id_hash('cmd-2')


def test_mark_before_ack_write_prevents_duplicate_open(tmp_path) -> None:
    store = CommandIdempotenceStore(store_dir=tmp_path)
    opens: list[str] = []
    acks: list[tuple[str, bool, bool]] = []

    def execute_open(command_id: str) -> bool:
        opens.append(command_id)
        return True

    def write_ack(command_id: str, *, success: bool, duplicate: bool) -> bool:
        acks.append((command_id, success, duplicate))
        return True

    first = try_execute_with_idempotence(
        command_id='cmd-open-1',
        account_id='12345',
        symbol='EURUSD',
        magic=100001,
        store=store,
        last_processed_command_id='',
        execute_open=execute_open,
        write_ack=write_ack,
    )
    second = try_execute_with_idempotence(
        command_id='cmd-open-1',
        account_id='12345',
        symbol='EURUSD',
        magic=100001,
        store=store,
        last_processed_command_id='cmd-open-1',
        execute_open=execute_open,
        write_ack=write_ack,
    )

    assert first == (True, 'cmd-open-1', True)
    assert second == (False, '', True)
    assert opens == ['cmd-open-1']
    assert store.is_processed('12345', 'EURUSD', 100001, 'cmd-open-1')


def test_ack_write_failure_after_success_still_blocks_reopen(tmp_path) -> None:
    store = CommandIdempotenceStore(store_dir=tmp_path)
    opens: list[str] = []

    def execute_open(command_id: str) -> bool:
        opens.append(command_id)
        return True

    def write_ack_fail(command_id: str, *, success: bool, duplicate: bool) -> bool:
        return False

    def write_ack_ok(command_id: str, *, success: bool, duplicate: bool) -> bool:
        return True

    did_open, processed_id, ack_written = try_execute_with_idempotence(
        command_id='cmd-open-2',
        account_id='12345',
        symbol='EURUSD',
        magic=100001,
        store=store,
        last_processed_command_id='',
        execute_open=execute_open,
        write_ack=write_ack_fail,
    )
    assert did_open is True
    assert processed_id == 'cmd-open-2'
    assert ack_written is False
    assert store.is_processed('12345', 'EURUSD', 100001, 'cmd-open-2')

    did_open_again, _, _ = try_execute_with_idempotence(
        command_id='cmd-open-2',
        account_id='12345',
        symbol='EURUSD',
        magic=100001,
        store=store,
        last_processed_command_id='',
        execute_open=execute_open,
        write_ack=write_ack_ok,
    )
    assert did_open_again is False
    assert opens == ['cmd-open-2']


def test_mql_execution_marks_processed_before_write_ack() -> None:
    source = mql_source.load_mqh('SYSTEM_Execution.mqh')
    body = mql_source.function_body(source, 'SYSTEM_TryExecutePendingControl')
    mark_pos = body.find('SYSTEM_MarkCommandProcessed')
    assert mark_pos >= 0
    write_after_mark = body.find('SYSTEM_WriteAck', mark_pos)
    assert write_after_mark > mark_pos
    assert 'SYSTEM_IsCommandProcessed' in body


def test_mql_execution_defines_idempotence_helpers() -> None:
    source = mql_source.load_mqh('SYSTEM_Execution.mqh')
    names = set(mql_source.public_function_names(source))
    assert 'SYSTEM_ProcessedCommandGvName' in names
    assert 'SYSTEM_IsCommandProcessed' in names
    assert 'SYSTEM_MarkCommandProcessed' in names
    assert 'SYSTEM_LoadProcessedCommandId' in names
