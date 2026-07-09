from __future__ import annotations
import json
import shutil
from pathlib import Path
from engine.deployment.path_contract import sync_deployment_paths
from tests.core.config_payload import valid_system_config_payload
from tools.show_paths import build_paths_report, main, run_show_paths

def _prepare_root(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    for relative in ('run_live.py', 'mql4/Include/SYSTEM_Paths.mqh', 'mql4/Include/SYSTEM_RootConfig.mqh'):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo_root / relative, target)
    config_dir = tmp_path / 'config'
    config_dir.mkdir(parents=True, exist_ok=True)
    payload = valid_system_config_payload()
    payload['system']['root_path'] = str(tmp_path)
    (config_dir / 'system.json').write_text(json.dumps(payload), encoding='utf-8')
    clients = tmp_path / 'data' / 'clients' / '12345'
    clients.mkdir(parents=True, exist_ok=True)
    (clients / 'market_EURUSD_100001.csv').write_text('time_utc,open,high,low,close,volume\n', encoding='utf-8')
    sync_deployment_paths(tmp_path)

def test_build_paths_report_lists_clients_and_instances(tmp_path: Path) -> None:
    _prepare_root(tmp_path)
    report = build_paths_report(root_path=tmp_path)
    assert 'SYSTEM path diagnostic' in report
    assert str(tmp_path / 'data' / 'clients') in report
    assert '12345' in report
    assert 'EURUSD' in report
    assert 'market file' in report
    assert 'RESULT:' in report

def test_main_returns_zero_for_valid_root(tmp_path: Path, capsys) -> None:
    _prepare_root(tmp_path)
    exit_code = main(['--root', str(tmp_path)])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert 'SYSTEM path diagnostic' in captured.out
    assert 'clients_dir' in captured.out

def test_run_show_paths_matches_build_paths_report(tmp_path: Path) -> None:
    _prepare_root(tmp_path)
    assert run_show_paths(root_path=tmp_path) == build_paths_report(root_path=tmp_path)
