from __future__ import annotations
import shutil
from pathlib import Path
import pytest
from tools.validate_order_command import OrderCommandValidationReport, ValidationCheck, format_validation_report, main, run_order_command_validation, validate_close_command_contract, validate_command_module_structure, validate_control_writer_support, validate_management_command_contract, validate_modify_command_contract, validate_none_command_contract, validate_open_command_contract, validate_order_command_dataclass_fields, validate_public_builder_signatures, validate_resolve_order_command_priority, validate_supported_actions
ROOT = Path(__file__).resolve().parents[2]

def test_validation_check_dataclass_fields() -> None:
    check = ValidationCheck(check_id='sample', name='sample check', passed=True, message='ok')
    assert check.check_id == 'sample'
    assert check.passed is True

def test_order_command_validation_report_passed_and_failed_checks() -> None:
    report = OrderCommandValidationReport(checks=(ValidationCheck('a', 'A', True, 'ok'), ValidationCheck('b', 'B', False, 'bad')))
    assert not report.passed
    assert len(report.failed_checks) == 1
    assert report.failed_checks[0].check_id == 'b'

def test_validate_order_command_dataclass_fields_passes() -> None:
    checks = validate_order_command_dataclass_fields()
    assert len(checks) == 1
    assert checks[0].passed

def test_validate_command_module_structure_passes_for_project_root() -> None:
    checks = validate_command_module_structure(ROOT)
    assert all((check.passed for check in checks))

def test_validate_command_module_structure_fails_without_command_module(tmp_path: Path) -> None:
    checks = validate_command_module_structure(tmp_path)
    assert not checks[0].passed

def test_validate_supported_actions_passes() -> None:
    checks = validate_supported_actions()
    assert checks[0].passed

def test_validate_open_command_contract_passes() -> None:
    checks = validate_open_command_contract()
    assert checks[0].passed

def test_validate_none_command_contract_passes() -> None:
    checks = validate_none_command_contract()
    assert checks[0].passed

def test_validate_modify_command_contract_passes() -> None:
    checks = validate_modify_command_contract()
    assert checks[0].passed

def test_validate_close_command_contract_passes() -> None:
    checks = validate_close_command_contract()
    assert checks[0].passed

def test_validate_management_command_contract_passes() -> None:
    checks = validate_management_command_contract()
    assert checks[0].passed

def test_validate_resolve_order_command_priority_passes() -> None:
    checks = validate_resolve_order_command_priority()
    assert checks[0].passed

def test_validate_public_builder_signatures_passes() -> None:
    checks = validate_public_builder_signatures()
    assert all((check.passed for check in checks))

def test_validate_control_writer_support_passes_for_project_root() -> None:
    checks = validate_control_writer_support(ROOT)
    assert checks[0].passed

def test_run_order_command_validation_passes_for_project_root() -> None:
    report = run_order_command_validation(root_path=ROOT)
    assert report.passed

def test_run_order_command_validation_passes_for_copied_project_tree(tmp_path: Path) -> None:
    shutil.copytree(ROOT / 'engine', tmp_path / 'engine')
    report = run_order_command_validation(root_path=tmp_path)
    assert report.passed

def test_format_validation_report_includes_result_line() -> None:
    report = OrderCommandValidationReport(checks=(ValidationCheck('a', 'A', True, 'ok'),))
    rendered = format_validation_report(report)
    assert 'RESULT: PASS' in rendered
    assert 'Order Command validation report' in rendered

def test_main_returns_zero_for_valid_project_root() -> None:
    assert main(['--root', str(ROOT)]) == 0

def test_main_returns_non_zero_when_command_module_missing(tmp_path: Path) -> None:
    assert main(['--root', str(tmp_path)]) == 1
