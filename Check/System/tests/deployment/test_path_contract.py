from __future__ import annotations
import json
import shutil
from pathlib import Path
import pytest
from engine.deployment.path_contract import prepare_deployment_root, read_config_root_path, read_mql4_compiled_root, resolve_deployment_root, run_path_contract_validation, sync_config_instances_from_clients, sync_deployment_paths, validate_config_matches_runtime_root, validate_mql4_root_matches_config, validate_no_competing_deployment_trees, validate_relative_path_segments, write_config_root_path, write_mql4_root_config
from tests.core.config_payload import valid_system_config_payload

def _install_minimal_deployment(root: Path) -> None:
    repo_root = resolve_deployment_root()
    for relative in ('run_live.py', 'mql4/Include/SYSTEM_Paths.mqh', 'mql4/Include/SYSTEM_RootConfig.mqh'):
        source = repo_root / relative
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    config_dir = root / 'config'
    config_dir.mkdir(parents=True, exist_ok=True)
    payload = valid_system_config_payload()
    payload['system']['root_path'] = str(root)
    (config_dir / 'system.json').write_text(json.dumps(payload), encoding='utf-8')

def test_relative_path_segments_match_python() -> None:
    root = resolve_deployment_root()
    checks = validate_relative_path_segments(root)
    assert checks
    assert all((check.passed for check in checks)), [check.message for check in checks if not check.passed]

def test_sync_paths_aligns_config_and_mql4(tmp_path: Path) -> None:
    _install_minimal_deployment(tmp_path)
    write_config_root_path(tmp_path / 'other', config_path=tmp_path / 'config' / 'system.json')
    write_mql4_root_config(tmp_path / 'other', output_path=tmp_path / 'mql4' / 'Include' / 'SYSTEM_RootConfig.mqh')
    report = run_path_contract_validation(tmp_path)
    assert not report.passed
    sync_deployment_paths(tmp_path)
    report = run_path_contract_validation(tmp_path)
    assert report.passed
    assert read_config_root_path(tmp_path / 'config' / 'system.json') == str(tmp_path)
    assert read_mql4_compiled_root(tmp_path) == str(tmp_path)

def test_path_contract_detects_config_runtime_mismatch(tmp_path: Path) -> None:
    _install_minimal_deployment(tmp_path)
    write_config_root_path(tmp_path / 'wrong', config_path=tmp_path / 'config' / 'system.json')
    write_mql4_root_config(tmp_path, output_path=tmp_path / 'mql4' / 'Include' / 'SYSTEM_RootConfig.mqh')
    config_check = validate_config_matches_runtime_root(tmp_path)
    mql4_check = validate_mql4_root_matches_config(tmp_path)
    assert not config_check.passed
    assert not mql4_check.passed

def test_competing_trees_fail_when_both_have_client_data(tmp_path: Path) -> None:
    outer = tmp_path / 'outer'
    inner = outer / 'SYSTEM'
    _install_minimal_deployment(outer)
    _install_minimal_deployment(inner)
    write_config_root_path(outer, config_path=outer / 'config' / 'system.json')
    write_config_root_path(inner, config_path=inner / 'config' / 'system.json')
    write_mql4_root_config(outer, output_path=outer / 'mql4' / 'Include' / 'SYSTEM_RootConfig.mqh')
    for tree in (outer, inner):
        clients = tree / 'data' / 'clients' / '231054'
        clients.mkdir(parents=True, exist_ok=True)
        (clients / 'market_EURUSD_100001.csv').write_text('time_utc,open,high,low,close,volume\n', encoding='utf-8')
    check = validate_no_competing_deployment_trees(outer)
    assert not check.passed
    assert 'conflicting roots' in check.message

@pytest.mark.deployment
def test_repo_path_contract_after_sync(tmp_path: Path) -> None:
    repo_root = resolve_deployment_root()
    for name in ('run_live.py', 'dashboard.py', 'pytest.ini', 'requirements.txt'):
        shutil.copy2(repo_root / name, tmp_path / name)
    shutil.copytree(repo_root / 'engine', tmp_path / 'engine')
    shutil.copytree(repo_root / 'mql4', tmp_path / 'mql4')
    shutil.copytree(repo_root / 'config', tmp_path / 'config')
    sync_deployment_paths(tmp_path)
    report = run_path_contract_validation(tmp_path)
    assert report.passed, [check.message for check in report.failed_checks]

def test_repo_path_contract_fails_before_sync() -> None:
    root = resolve_deployment_root()
    report = run_path_contract_validation(root)
    if report.passed:
        pytest.skip('repository paths already aligned on this host')
    failed_ids = {check.check_id for check in report.failed_checks}
    assert 'config_runtime_root' in failed_ids or 'mql4_config_root' in failed_ids


def test_prepare_deployment_root_aligns_config_mql4_and_directories(tmp_path: Path) -> None:
    _install_minimal_deployment(tmp_path)
    write_config_root_path(tmp_path / 'other', config_path=tmp_path / 'config' / 'system.json')
    write_mql4_root_config(tmp_path / 'other', output_path=tmp_path / 'mql4' / 'Include' / 'SYSTEM_RootConfig.mqh')
    root = prepare_deployment_root(tmp_path)
    report = run_path_contract_validation(root)
    assert report.passed
    assert (tmp_path / 'data' / 'clients').is_dir()
    assert (tmp_path / 'data' / 'logs').is_dir()
    assert (tmp_path / 'data' / 'clients' / '12345').is_dir()
    assert read_config_root_path(tmp_path / 'config' / 'system.json') == str(tmp_path)
    assert read_mql4_compiled_root(tmp_path) == str(tmp_path)


def test_sync_config_instances_from_clients_updates_account_id(tmp_path: Path) -> None:
    _install_minimal_deployment(tmp_path)
    sync_deployment_paths(tmp_path)
    account_dir = tmp_path / 'data' / 'clients' / '999888'
    account_dir.mkdir(parents=True, exist_ok=True)
    (account_dir / 'market_EURUSD_100001.csv').write_text('time_utc,open,high,low,close,volume\n', encoding='utf-8')
    changed = sync_config_instances_from_clients(tmp_path)
    assert changed
    payload = json.loads((tmp_path / 'config' / 'system.json').read_text(encoding='utf-8'))
    assert payload['instances'][0]['account_id'] == '999888'
