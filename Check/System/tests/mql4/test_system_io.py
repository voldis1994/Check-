from __future__ import annotations
import os
from pathlib import Path
import pytest
from tests.mql4 import io_reference, mql_source

@pytest.fixture
def io_source() -> str:
    return mql_source.load_mqh('SYSTEM_IO.mqh')

def test_system_io_includes_system_paths(io_source: str) -> None:
    assert '#include <SYSTEM_Paths.mqh>' in io_source

def test_system_io_public_functions_are_defined(io_source: str) -> None:
    expected = {'SYSTEM_TmpPathFor', 'SYSTEM_ParentDirectory', 'SYSTEM_AtomicWriteText'}
    assert expected.issubset(set(mql_source.public_function_names(io_source)))

def test_system_tmp_path_for_appends_tmp_suffix() -> None:
    assert io_reference.tmp_path_for('C:\\Check\\System\\data\\clients\\12345\\status_12345.json') == Path('C:\\Check\\System\\data\\clients\\12345\\status_12345.json.tmp')

def test_system_tmp_path_for_function_uses_tmp_suffix(io_source: str) -> None:
    body = mql_source.function_body(io_source, 'SYSTEM_TmpPathFor')
    assert '".tmp"' in body

def test_system_parent_directory_returns_parent_segment() -> None:
    assert io_reference.parent_directory('C:\\Check\\System\\data\\clients\\12345\\status_12345.json') == 'C:\\Check\\System\\data\\clients\\12345'
    assert io_reference.parent_directory('C:\\Check\\System') == 'C:\\Check'

def test_system_parent_directory_function_splits_on_backslash(io_source: str) -> None:
    body = mql_source.function_body(io_source, 'SYSTEM_ParentDirectory')
    assert "'\\\\'" in body or "'\\'" in body

def test_system_atomic_write_text_writes_tmp_then_renames(tmp_path: Path) -> None:
    target = tmp_path / 'status_12345.json'
    io_reference.atomic_write_text(target, '{"connected":true}')
    assert target.exists()
    assert target.read_text(encoding='utf-8') == '{"connected":true}'
    assert not target.with_name(f'{target.name}.tmp').exists()

def test_system_atomic_write_text_calls_fsync_before_replace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / 'ack_EURUSD_100001.json'
    calls: list[str] = []
    original_fsync = os.fsync
    original_replace = os.replace

    def tracked_fsync(fd: int) -> None:
        calls.append('fsync')
        original_fsync(fd)

    def tracked_replace(src: os.PathLike[str] | str, dst: os.PathLike[str] | str) -> None:
        calls.append('replace')
        original_replace(src, dst)
    monkeypatch.setattr(os, 'fsync', tracked_fsync)
    monkeypatch.setattr(os, 'replace', tracked_replace)
    io_reference.atomic_write_text(target, 'payload')
    assert calls == ['fsync', 'replace']

def test_system_atomic_write_text_uses_tmp_flush_and_move(io_source: str) -> None:
    body = mql_source.function_body(io_source, 'SYSTEM_AtomicWriteText')
    assert 'SYSTEM_TmpPathFor' in body
    assert 'CreateFileW' in body
    assert 'WriteFile' in body
    assert 'FlushFileBuffers' in body
    assert 'CloseHandle' in body
    assert 'MoveFileExW' in body
    assert 'SYSTEM_EnsureDirectory' in body

def test_system_atomic_write_text_ensures_parent_directory_before_write(io_source: str) -> None:
    body = mql_source.function_body(io_source, 'SYSTEM_AtomicWriteText')
    assert 'SYSTEM_ParentDirectory' in body
