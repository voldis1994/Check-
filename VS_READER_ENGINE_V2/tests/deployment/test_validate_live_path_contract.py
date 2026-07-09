from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine.deployment.path_contract import (
    read_config_root_path,
    read_mql4_compiled_root,
    sync_deployment_paths,
)
from tools.validate_live import validate_path_contract
from engine.core.paths import SystemPaths
from tests.core.config_payload import valid_system_config_payload


def test_validate_live_includes_path_contract_checks(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    payload = valid_system_config_payload()
    payload["system"]["root_path"] = str(tmp_path)
    (config_dir / "system.json").write_text(json.dumps(payload), encoding="utf-8")

    repo_root = Path(__file__).resolve().parents[2]
    mql4_include = repo_root / "mql4" / "Include"
    target_include = tmp_path / "mql4" / "Include"
    target_include.mkdir(parents=True, exist_ok=True)
    for name in ("SYSTEM_Paths.mqh", "SYSTEM_RootConfig.mqh"):
        (target_include / name).write_text((mql4_include / name).read_text(encoding="utf-8"), encoding="utf-8")

    sync_deployment_paths(tmp_path)
    checks = validate_path_contract(SystemPaths(tmp_path))
    assert checks
    assert all(check.passed for check in checks), [check.message for check in checks if not check.passed]
