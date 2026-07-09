from __future__ import annotations
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from engine.core.atomic_io import atomic_write_text
from engine.core.paths import SystemPaths
from engine.journal.rotation import rotate_journal_file

def _journal_line(timestamp_utc: str, decision: str='WAIT') -> str:
    return json.dumps({'decision_id': f'id-{timestamp_utc}', 'timestamp_utc': timestamp_utc, 'account_id': '12345', 'symbol': 'EURUSD', 'magic': 100001, 'decision': decision, 'reason': 'test', 'risk_result': 'ALLOW'})

def test_rotate_journal_file_moves_old_lines_to_history(tmp_path: Path) -> None:
    journal_path = tmp_path / 'decision_EURUSD_100001.jsonl'
    history_dir = tmp_path / 'history'
    old_time = datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat().replace('+00:00', 'Z')
    recent_time = datetime(2026, 7, 7, tzinfo=timezone.utc).isoformat().replace('+00:00', 'Z')
    atomic_write_text(journal_path, '\n'.join([_journal_line(old_time), _journal_line(recent_time)]) + '\n')
    result = rotate_journal_file(journal_path, retention_days=30, history_dir=history_dir, current_utc='2026-07-07T06:00:00.000Z')
    assert result.archived_lines == 1
    assert result.retained_lines == 1
    assert result.archive_path is not None
    assert result.archive_path.name == 'decision_2026-07-07.jsonl'
    assert result.archive_path.exists()
    retained = journal_path.read_text(encoding='utf-8')
    assert recent_time in retained
    assert old_time not in retained
