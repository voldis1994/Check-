from __future__ import annotations
from pathlib import Path
from tools.diagnose_skip import diagnose_instance
from engine.core.config import load_system_config
from engine.core.instance import Instance
from engine.core.lifecycle import build_system_paths
from engine.core.paths import SystemPaths
from tests.core.config_payload import valid_system_config_payload
import json


def test_diagnose_reports_missing_market(tmp_path: Path) -> None:
    payload = valid_system_config_payload()
    payload['system']['root_path'] = str(tmp_path)
    config_dir = tmp_path / 'config'
    config_dir.mkdir(parents=True)
    (config_dir / 'system.json').write_text(json.dumps(payload), encoding='utf-8')
    for name in ('data/clients', 'data/logs', 'data/cache', 'data/history', 'data/universe'):
        (tmp_path / name).mkdir(parents=True, exist_ok=True)
    paths = SystemPaths(tmp_path)
    paths.ensure_account_directories('12345')
    config = load_system_config(config_dir / 'system.json', system_paths=paths)
    runtime_paths = build_system_paths(config, runtime_root=tmp_path)
    instance = Instance('12345', 'EURUSD', 100001)
    lines, skip_reason = diagnose_instance(runtime_paths, instance, threshold_ms=90000)
    assert skip_reason is not None
    assert 'load_failed' in skip_reason or 'market' in skip_reason
    assert any('VERDICT: SKIP' in line for line in lines)
