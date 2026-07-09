from __future__ import annotations
import os
from pathlib import Path
import pytest
from engine.core import atomic_io
from engine.core.atomic_io import atomic_read_text, atomic_write_json, atomic_write_text, is_file_stable
from engine.protocol.errors import DataIOError

def test_atomic_write_text_uses_tmp_and_rename(tmp_path: Path) -> None:
    target = tmp_path / 'control_EURUSD_100001.json'
    atomic_write_text(target, '{"ok":true}')
    assert target.exists()
    assert target.read_text(encoding='utf-8') == '{"ok":true}'
    assert not target.with_name(f'{target.name}.tmp').exists()

def test_atomic_write_text_calls_fsync_before_replace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / 'control_EURUSD_100001.json'
    calls: list[str] = []
    original_fsync = os.fsync
    original_replace = os.replace

    def tracked_fsync(fd: int) -> None:
        calls.append('fsync')
        original_fsync(fd)

    def tracked_replace(src: os.PathLike[str] | str, dst: os.PathLike[str] | str) -> None:
        calls.append('replace')
        original_replace(src, dst)
    monkeypatch.setattr(atomic_io.os, 'fsync', tracked_fsync)
    monkeypatch.setattr(atomic_io.os, 'replace', tracked_replace)
    atomic_write_text(target, 'payload')
    assert calls == ['fsync', 'replace']

def test_is_file_stable_false_when_missing(tmp_path: Path) -> None:
    assert not is_file_stable(tmp_path / 'missing.json')

def test_is_file_stable_true_for_existing_unchanged_file(tmp_path: Path) -> None:
    target = tmp_path / 'status_12345.json'
    target.write_text('{"ok":true}', encoding='utf-8')
    assert is_file_stable(target)

def test_is_file_stable_rejects_invalid_checks(tmp_path: Path) -> None:
    target = tmp_path / 'status_12345.json'
    target.write_text('x', encoding='utf-8')
    with pytest.raises(DataIOError, match='checks must be >= 1'):
        is_file_stable(target, checks=0)

def test_atomic_read_text_reads_only_when_stable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / 'ack_EURUSD_100001.json'
    target.write_text('{"status":"SUCCESS"}', encoding='utf-8')
    monkeypatch.setattr(atomic_io, 'is_file_stable', lambda _: True)
    assert atomic_read_text(target) == '{"status":"SUCCESS"}'

def test_atomic_read_text_waits_when_tmp_exists_then_reads(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / 'ack_EURUSD_100001.json'
    tmp_path_file = target.with_name(f'{target.name}.tmp')
    tmp_path_file.write_text('tmp', encoding='utf-8')
    calls = {'count': 0}

    def fake_once(path: str | Path, *, encoding: str='utf-8') -> str:
        calls['count'] += 1
        if calls['count'] < 3:
            if tmp_path_file.exists():
                raise DataIOError('tmp file exists, final file is not ready', module='core.atomic_io')
        target.write_text('{"status":"SUCCESS"}', encoding='utf-8')
        tmp_path_file.unlink(missing_ok=True)
        return '{"status":"SUCCESS"}'
    monkeypatch.setattr(atomic_io, '_atomic_read_text_once', fake_once)
    assert atomic_read_text(target) == '{"status":"SUCCESS"}'
    assert calls['count'] >= 3

def test_atomic_read_text_rejects_when_tmp_exists(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / 'ack_EURUSD_100001.json'
    target.write_text('x', encoding='utf-8')
    target.with_name(f'{target.name}.tmp').write_text('tmp', encoding='utf-8')
    monkeypatch.setattr(atomic_io, 'DEFAULT_READ_WAIT_ATTEMPTS', 2)
    with pytest.raises(DataIOError, match='tmp file exists'):
        atomic_read_text(target)

def test_atomic_read_text_rejects_unstable_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / 'ack_EURUSD_100001.json'
    target.write_text('x', encoding='utf-8')
    monkeypatch.setattr(atomic_io, 'is_file_stable', lambda _: False)
    with pytest.raises(DataIOError, match='not stable'):
        atomic_read_text(target)

def test_atomic_read_text_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(DataIOError, match='does not exist'):
        atomic_read_text(tmp_path / 'missing.json')

def test_atomic_write_json_writes_minified_json(tmp_path: Path) -> None:
    target = tmp_path / 'status_12345.json'
    atomic_write_json(target, {'b': 2, 'a': 1})
    assert target.read_text(encoding='utf-8') == '{"a":1,"b":2}'

def test_atomic_write_json_pretty_adds_trailing_newline(tmp_path: Path) -> None:
    target = tmp_path / 'status_12345.json'
    atomic_write_json(target, {'a': 1}, pretty=True)
    assert target.read_text(encoding='utf-8') == '{\n  "a": 1\n}\n'

def test_atomic_write_json_rejects_non_dict_payload(tmp_path: Path) -> None:
    target = tmp_path / 'status_12345.json'
    with pytest.raises(DataIOError, match='payload must be a dict'):
        atomic_write_json(target, ['x'])
