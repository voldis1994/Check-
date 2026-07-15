from __future__ import annotations
from pathlib import Path
from engine.core.mt4_bridge import mirror_common_bridge_to_deployment
from engine.core.paths import SystemPaths


def test_mirror_common_bridge_copies_market_file(tmp_path: Path, monkeypatch) -> None:
    bridge = tmp_path / 'AppData' / 'MetaQuotes' / 'Terminal' / 'Common' / 'Files' / 'CheckSystem'
    src_dir = bridge / 'data' / 'clients' / '231054'
    src_dir.mkdir(parents=True)
    src = src_dir / 'market_EURUSD_100001.csv'
    src.write_text('time_utc,open\n2026-07-15T00:00:00.000Z,1.1\n', encoding='utf-8')
    monkeypatch.setenv('APPDATA', str(tmp_path / 'AppData'))

    deploy = tmp_path / 'Check' / 'System'
    deploy.mkdir(parents=True)
    paths = SystemPaths(deploy)
    copied = mirror_common_bridge_to_deployment(paths)
    dest = deploy / 'data' / 'clients' / '231054' / 'market_EURUSD_100001.csv'
    assert 'data/clients/231054/market_EURUSD_100001.csv' in copied
    assert dest.is_file()
    assert '1.1' in dest.read_text(encoding='utf-8')
