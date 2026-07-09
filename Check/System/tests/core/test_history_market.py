from __future__ import annotations
from pathlib import Path
from engine.core.history import archive_market_snapshot
from engine.core.instance import Instance
from engine.core.paths import SystemPaths
from engine.loader.market_loader import build_market_file_path

def _instance() -> Instance:
    return Instance(account_id='12345', symbol='EURUSD', magic=100001)

def test_archive_market_snapshot_uses_spec_date_filename(tmp_path: Path) -> None:
    paths = SystemPaths(tmp_path)
    paths.ensure_directories()
    instance = _instance()
    paths.ensure_account_directories(instance.account_id)
    market_path = build_market_file_path(paths, instance)
    market_path.write_text('time_utc,open\n', encoding='utf-8')
    archived = archive_market_snapshot(paths, instance, current_utc='2026-07-07T06:00:00.000Z')
    assert archived is not None
    assert archived.name == 'market_2026-07-07.csv'
    assert archived.parent.name == 'EURUSD_100001'
