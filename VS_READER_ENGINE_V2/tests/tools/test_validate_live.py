from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

import pytest

from engine.core.instance import Instance
from engine.core.lifecycle import build_system_paths
from engine.core.paths import SystemPaths
from engine.deployment.path_contract import sync_deployment_paths
from engine.protocol.constants import PROTOCOL_SCHEMA_VERSION, TIMEFRAME_M1
from tests.core.config_payload import valid_system_config_payload
from tools.validate_live import (
    LiveValidationReport,
    ValidationCheck,
    format_validation_report,
    main,
    run_live_validation,
    validate_config_file,
    validate_directory_layout,
    validate_instance_isolation,
    validate_mql4_ea_files,
    validate_mt4_exports,
    validate_rules_compliance,
    validate_runtime_entry_points,
    validate_universe_context,
)


ROOT = Path(__file__).resolve().parents[2]
INTEGRATION_FIXTURES = ROOT / "tests" / "integration" / "fixtures"


def _write_live_config(root: Path, *, instances: list[dict] | None = None) -> Path:
    payload = valid_system_config_payload()
    payload["system"]["root_path"] = str(root)
    payload["system"]["timeframe"] = TIMEFRAME_M1
    payload["analysis"] = {**payload["analysis"], "lookback_bars": 3}
    if instances is not None:
        payload["instances"] = instances
    config_dir = root / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "system.json"
    config_path.write_text(json.dumps(payload), encoding="utf-8")
    return config_path


def _install_mt4_exports(paths: SystemPaths, instance: Instance) -> None:
    paths.ensure_account_directories(instance.account_id)
    account_dir = paths.account_dir(instance.account_id)
    shutil.copyfile(
        INTEGRATION_FIXTURES / instance.market_filename(),
        account_dir / instance.market_filename(),
    )
    shutil.copyfile(
        INTEGRATION_FIXTURES / instance.sensor_filename(),
        account_dir / instance.sensor_filename(),
    )
    shutil.copyfile(
        INTEGRATION_FIXTURES / instance.status_filename(),
        account_dir / instance.status_filename(),
    )
    shutil.copyfile(INTEGRATION_FIXTURES / "universe.json", account_dir / "universe.json")
    now = time.time()
    for path in account_dir.iterdir():
        if path.is_file():
            import os

            os.utime(path, (now, now))


def _prepare_live_root(tmp_path: Path, *, with_exports: bool = True) -> tuple[Path, SystemPaths, Instance]:
    config_path = _write_live_config(tmp_path)
    paths = build_system_paths(
        __import__("engine.core.config", fromlist=["load_system_config"]).load_system_config(
            config_path,
            system_paths=SystemPaths(tmp_path),
        )
    )
    paths.ensure_directories()
    instance = Instance(account_id="12345", symbol="EURUSD", magic=100001)
    if with_exports:
        _install_mt4_exports(paths, instance)
    shutil.copyfile(ROOT / "run_live.py", tmp_path / "run_live.py")
    shutil.copyfile(ROOT / "dashboard.py", tmp_path / "dashboard.py")
    mql4_src = ROOT / "mql4"
    shutil.copytree(mql4_src, tmp_path / "mql4")
    engine_src = ROOT / "engine"
    shutil.copytree(engine_src, tmp_path / "engine")
    sync_deployment_paths(tmp_path)
    return config_path, paths, instance


def test_validation_check_dataclass_fields() -> None:
    check = ValidationCheck(
        check_id="sample",
        name="sample check",
        passed=True,
        message="ok",
    )
    assert check.check_id == "sample"
    assert check.passed is True


def test_live_validation_report_passed_and_failed_checks() -> None:
    report = LiveValidationReport(
        checks=(
            ValidationCheck("a", "A", True, "ok"),
            ValidationCheck("b", "B", False, "bad"),
        )
    )
    assert not report.passed
    assert len(report.failed_checks) == 1
    assert report.failed_checks[0].check_id == "b"


def test_validate_directory_layout_reports_missing_directories(tmp_path: Path) -> None:
    paths = SystemPaths(tmp_path)
    checks = validate_directory_layout(paths)
    assert checks
    assert all(not check.passed for check in checks)


def test_validate_directory_layout_passes_with_created_directories(tmp_path: Path) -> None:
    _, paths, _ = _prepare_live_root(tmp_path, with_exports=False)
    checks = validate_directory_layout(paths)
    assert all(check.passed for check in checks)


def test_validate_runtime_entry_points(tmp_path: Path) -> None:
    _, paths, _ = _prepare_live_root(tmp_path, with_exports=False)
    checks = validate_runtime_entry_points(paths.root)
    assert all(check.passed for check in checks)


def test_validate_mql4_ea_files_passes_with_project_copy(tmp_path: Path) -> None:
    _, paths, _ = _prepare_live_root(tmp_path, with_exports=False)
    checks = validate_mql4_ea_files(paths.root)
    assert all(check.passed for check in checks)


def test_validate_config_file_passes_for_valid_config(tmp_path: Path) -> None:
    config_path, paths, _ = _prepare_live_root(tmp_path, with_exports=False)
    checks = validate_config_file(config_path, paths)
    assert all(check.passed for check in checks)
    assert any(check.check_id == "rule_01" for check in checks)


def test_validate_instance_isolation_detects_duplicate_keys(tmp_path: Path) -> None:
    _, paths, instance = _prepare_live_root(tmp_path, with_exports=False)
    duplicate = (instance, instance)
    checks = validate_instance_isolation(paths, duplicate)
    isolation = next(check for check in checks if check.check_id == "rule_04")
    assert not isolation.passed


def test_validate_instance_isolation_passes_for_unique_instances(tmp_path: Path) -> None:
    _, paths, instance = _prepare_live_root(tmp_path, with_exports=False)
    second = Instance(account_id="12345", symbol="GBPUSD", magic=100002)
    checks = validate_instance_isolation(paths, (instance, second))
    assert all(check.passed for check in checks)


def test_validate_mt4_exports_fails_without_exports(tmp_path: Path) -> None:
    _, paths, instance = _prepare_live_root(tmp_path, with_exports=False)
    checks = validate_mt4_exports(
        paths,
        (instance,),
        stale_threshold_ms=60_000,
        now_epoch=time.time(),
    )
    assert not all(check.passed for check in checks)


def test_validate_mt4_exports_passes_with_fresh_exports(tmp_path: Path) -> None:
    _, paths, instance = _prepare_live_root(tmp_path, with_exports=True)
    checks = validate_mt4_exports(
        paths,
        (instance,),
        stale_threshold_ms=60_000,
        now_epoch=time.time(),
    )
    assert all(check.passed for check in checks)


def test_validate_universe_context_rejects_trade_signal_fields(tmp_path: Path) -> None:
    _, paths, _ = _prepare_live_root(tmp_path, with_exports=False)
    paths.universe_dir.mkdir(parents=True, exist_ok=True)
    paths.universe_file.write_text(
        json.dumps(
            {
                "schema_version": PROTOCOL_SCHEMA_VERSION,
                "timestamp_utc": "2026-07-07T06:00:00.000Z",
                "session": "LONDON",
                "market_regime": "trending",
                "signal": "BUY",
            }
        ),
        encoding="utf-8",
    )
    checks = validate_universe_context(paths)
    assert not all(check.passed for check in checks)


def test_validate_universe_context_passes_for_valid_universe(tmp_path: Path) -> None:
    _, paths, _ = _prepare_live_root(tmp_path, with_exports=True)
    checks = validate_universe_context(paths)
    assert all(check.passed for check in checks)


def test_validate_rules_compliance_checks_code_and_config(tmp_path: Path) -> None:
    config_path, paths, _ = _prepare_live_root(tmp_path, with_exports=False)
    config = __import__("engine.core.config", fromlist=["load_system_config"]).load_system_config(
        config_path,
        system_paths=paths,
    )
    checks = validate_rules_compliance(
        paths.root,
        config,
        config_text=config_path.read_text(encoding="utf-8"),
    )
    assert all(check.passed for check in checks)
    assert any(check.check_id == "rule_05" for check in checks)
    assert any(check.check_id == "rule_12" for check in checks)


def test_run_live_validation_passes_for_complete_environment(tmp_path: Path) -> None:
    config_path, _, _ = _prepare_live_root(tmp_path, with_exports=True)
    report = run_live_validation(root_path=tmp_path, config_path=config_path)
    assert isinstance(report, LiveValidationReport)
    assert report.passed


def test_run_live_validation_can_skip_mt4_exports(tmp_path: Path) -> None:
    config_path, _, _ = _prepare_live_root(tmp_path, with_exports=False)
    report = run_live_validation(
        root_path=tmp_path,
        config_path=config_path,
        require_mt4_exports=False,
    )
    assert report.passed


def test_format_validation_report_includes_result_line() -> None:
    report = LiveValidationReport(
        checks=(ValidationCheck("a", "A", True, "ok"),),
    )
    rendered = format_validation_report(report)
    assert "RESULT: PASS" in rendered
    assert "[PASS] a A: ok" in rendered


def test_main_returns_zero_for_valid_environment(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    config_path, _, _ = _prepare_live_root(tmp_path, with_exports=True)
    exit_code = main(["--root", str(tmp_path), "--config", str(config_path)])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "RESULT: PASS" in captured.out


def test_main_returns_non_zero_when_mt4_exports_missing(tmp_path: Path) -> None:
    config_path, _, _ = _prepare_live_root(tmp_path, with_exports=False)
    exit_code = main(["--root", str(tmp_path), "--config", str(config_path)])
    assert exit_code == 1
