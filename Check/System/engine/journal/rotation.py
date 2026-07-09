from __future__ import annotations
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from engine.core.atomic_io import atomic_read_text, atomic_write_text
from engine.core.clock import format_utc_timestamp
from engine.core.paths import SystemPaths
MODULE_NAME = 'journal.rotation'

@dataclass(frozen=True)
class JournalRotationResult:
    journal_path: Path
    archived_lines: int
    retained_lines: int
    archive_path: Path | None = None

def _parse_journal_timestamp(line: str) -> datetime | None:
    try:
        payload = json.loads(line)
    except json.JSONDecodeError:
        return None
    timestamp = payload.get('timestamp_utc')
    if not isinstance(timestamp, str) or not timestamp.strip():
        return None
    normalized = timestamp.replace('Z', '+00:00')
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)

def _journal_archive_name(journal_path: Path, archive_date: str) -> str:
    stem = journal_path.stem
    if stem.startswith('decision_'):
        return f'decision_{archive_date}.jsonl'
    if stem.startswith('trade_'):
        return f'trade_{archive_date}.jsonl'
    if stem.startswith('error_'):
        return f'error_{archive_date}.jsonl'
    return f'{stem}_{archive_date}.jsonl'

def _resolve_history_dir_from_journal(paths: SystemPaths, account_id: str, journal_path: Path) -> Path:
    stem = journal_path.stem
    for prefix in ('decision_', 'trade_', 'error_'):
        if stem.startswith(prefix):
            suffix = stem.removeprefix(prefix)
            if '_' not in suffix:
                break
            symbol, magic_text = suffix.rsplit('_', 1)
            try:
                magic = int(magic_text)
            except ValueError:
                break
            return paths.instance_history_dir(account_id, symbol, magic)
    return paths.history_dir / account_id / 'journals'

def rotate_journal_file(journal_path: Path, *, retention_days: int, history_dir: Path, current_utc: str | None=None) -> JournalRotationResult:
    if not journal_path.exists():
        return JournalRotationResult(journal_path=journal_path, archived_lines=0, retained_lines=0)
    resolved_current = current_utc or format_utc_timestamp(datetime.now(timezone.utc))
    current_time = datetime.fromisoformat(resolved_current.replace('Z', '+00:00')).astimezone(timezone.utc)
    cutoff = current_time - timedelta(days=retention_days)
    archive_date = current_time.strftime('%Y-%m-%d')
    lines = [line for line in atomic_read_text(journal_path).splitlines() if line.strip()]
    retained: list[str] = []
    archived: list[str] = []
    for line in lines:
        timestamp = _parse_journal_timestamp(line)
        if timestamp is not None and timestamp < cutoff:
            archived.append(line)
        else:
            retained.append(line)
    if not archived:
        return JournalRotationResult(journal_path=journal_path, archived_lines=0, retained_lines=len(retained))
    history_dir.mkdir(parents=True, exist_ok=True)
    archive_path = history_dir / _journal_archive_name(journal_path, archive_date)
    existing = ''
    if archive_path.exists():
        existing = atomic_read_text(archive_path)
        if existing and (not existing.endswith('\n')):
            existing = f'{existing}\n'
    atomic_write_text(archive_path, f'{existing}{chr(10).join(archived)}\n')
    output = '\n'.join(retained)
    if output:
        output = f'{output}\n'
    atomic_write_text(journal_path, output)
    return JournalRotationResult(journal_path=journal_path, archived_lines=len(archived), retained_lines=len(retained), archive_path=archive_path)

def rotate_account_journals(paths: SystemPaths, account_id: str, *, retention_days: int, current_utc: str | None=None) -> tuple[JournalRotationResult, ...]:
    journal_dir = paths.account_journal_dir(account_id)
    if not journal_dir.is_dir():
        return ()
    results: list[JournalRotationResult] = []
    for journal_path in sorted(journal_dir.glob('*.jsonl')):
        history_dir = _resolve_history_dir_from_journal(paths, account_id, journal_path)
        results.append(rotate_journal_file(journal_path, retention_days=retention_days, history_dir=history_dir, current_utc=current_utc))
    return tuple(results)
