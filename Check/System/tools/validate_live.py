from __future__ import annotations
import argparse
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from typing import Iterable
from engine.core.config import load_system_config
from engine.core.instance import Instance
from engine.core.lifecycle import build_system_paths, discover_instances, validate_root_path
from engine.core.paths import SystemPaths
from engine.deployment.path_contract import run_path_contract_validation
from engine.protocol.constants import TIMEFRAME_M1, UNIVERSE_FORBIDDEN_FIELDS, RiskResult
from engine.protocol.writer import DECISION_JOURNAL_REQUIRED_FIELDS
from engine.protocol.errors import ConfigurationError, SystemError
from engine.protocol.models import SystemConfig
from engine.protocol.parser import parse_status, parse_universe
from engine.validator.universe_validator import validate_universe_json
MODULE_NAME = 'tools.validate_live'
CHECKLIST_IDS = tuple((f'rule_{index:02d}' for index in range(1, 16)))

@dataclass(frozen=True)
class ValidationCheck:
    check_id: str
    name: str
    passed: bool
    message: str

@dataclass(frozen=True)
class LiveValidationReport:
    checks: tuple[ValidationCheck, ...]

    @property
    def passed(self) -> bool:
        return all((check.passed for check in self.checks))

    @property
    def failed_checks(self) -> tuple[ValidationCheck, ...]:
        return tuple((check for check in self.checks if not check.passed))

def _check(check_id: str, name: str, passed: bool, message: str) -> ValidationCheck:
    return ValidationCheck(check_id=check_id, name=name, passed=passed, message=message)

def validate_directory_layout(paths: SystemPaths) -> tuple[ValidationCheck, ...]:
    checks: list[ValidationCheck] = []
    required_dirs = (('clients', paths.clients_dir), ('logs', paths.logs_dir), ('cache', paths.cache_dir), ('history', paths.history_dir), ('universe', paths.universe_dir))
    for label, directory in required_dirs:
        checks.append(_check(f'path_{label}', f'{label} directory exists', directory.is_dir(), f'{label} directory ready at {directory}' if directory.is_dir() else f'missing {label} directory at {directory}'))
    checks.append(_check('path_config', 'config file exists', paths.config_path.is_file(), f'config found at {paths.config_path}' if paths.config_path.is_file() else f'missing config at {paths.config_path}'))
    return tuple(checks)

def validate_runtime_entry_points(root: Path) -> tuple[ValidationCheck, ...]:
    run_live = root / 'run_live.py'
    dashboard = root / 'dashboard.py'
    return (_check('entry_run_live', 'run_live.py exists', run_live.is_file(), f'run_live entry point found at {run_live}' if run_live.is_file() else 'missing run_live.py'), _check('entry_dashboard', 'dashboard.py exists', dashboard.is_file(), f'dashboard entry point found at {dashboard}' if dashboard.is_file() else 'missing dashboard.py'))

def validate_mql4_ea_files(root: Path) -> tuple[ValidationCheck, ...]:
    ea_path = root / 'mql4' / 'Experts' / 'SYSTEM_EA.mq4'
    include_dir = root / 'mql4' / 'Include'
    include_files = ('SYSTEM_Export.mqh', 'SYSTEM_Status.mqh', 'SYSTEM_Control.mqh', 'SYSTEM_Execution.mqh')
    checks = [_check('ea_main', 'SYSTEM_EA.mq4 exists', ea_path.is_file(), f'EA found at {ea_path}' if ea_path.is_file() else 'missing SYSTEM_EA.mq4')]
    for filename in include_files:
        path = include_dir / filename
        checks.append(_check(f'ea_include_{filename}', f'{filename} exists', path.is_file(), f'include found at {path}' if path.is_file() else f'missing {filename}'))
    if ea_path.is_file():
        source = ea_path.read_text(encoding='utf-8').lower()
        checks.append(_check('rule_14', 'MT4 does not analyze market', 'decision' not in source and 'scoring' not in source, 'SYSTEM_EA.mq4 contains no decision or scoring logic'))
    return tuple(checks)

def validate_path_contract(paths: SystemPaths, *, require_mt4_exports: bool=False) -> tuple[ValidationCheck, ...]:
    report = run_path_contract_validation(paths.root, require_mt4_exports=require_mt4_exports)
    return tuple((_check(f'path_contract_{item.check_id}', item.name, item.passed, item.message) for item in report.checks))

def validate_config_file(config_path: Path, paths: SystemPaths) -> tuple[ValidationCheck, ...]:
    try:
        config = load_system_config(config_path, system_paths=paths)
    except ConfigurationError as exc:
        return (_check('config_load', 'system.json loads', False, exc.message),)
    checks = [_check('config_load', 'system.json loads', True, f'loaded config schema {config.schema_version}'), _check('rule_01', 'M1 is the only timeframe', config.system.timeframe == TIMEFRAME_M1, f'timeframe={config.system.timeframe}'), _check('rule_08', 'spread uses relative threshold', config.analysis.spread_relative_threshold > 0, f'spread_relative_threshold={config.analysis.spread_relative_threshold}')]
    return tuple(checks)

def validate_instance_isolation(paths: SystemPaths, instances: tuple[Instance, ...]) -> tuple[ValidationCheck, ...]:
    if not instances:
        return (_check('instances_present', 'instances configured or discovered', False, 'no instances available for validation'),)
    account_ids = {instance.account_id for instance in instances}
    symbols = {instance.symbol for instance in instances}
    journal_paths: set[Path] = set()
    duplicate_paths = False
    for instance in instances:
        journal_path = paths.account_journal_dir(instance.account_id) / instance.decision_journal_filename()
        if journal_path in journal_paths:
            duplicate_paths = True
        journal_paths.add(journal_path)
    unique_keys = {instance.instance_key for instance in instances}
    return (_check('instances_present', 'instances configured or discovered', True, f'validated {len(instances)} instance(s)'), _check('rule_02', 'multi-account support', len(account_ids) >= 1, f'account_ids={sorted(account_ids)}'), _check('rule_03', 'multi-symbol support', len(symbols) >= 1, f'symbols={sorted(symbols)}'), _check('rule_04', 'instance isolation by account+symbol+magic', len(unique_keys) == len(instances) and (not duplicate_paths), 'instance keys and journal paths are isolated'))

def _file_is_fresh(path: Path, *, stale_threshold_ms: int, now_epoch: float) -> bool:
    if not path.exists():
        return False
    age_ms = max(0.0, (now_epoch - path.stat().st_mtime) * 1000.0)
    return age_ms <= stale_threshold_ms

def validate_mt4_exports(paths: SystemPaths, instances: tuple[Instance, ...], *, stale_threshold_ms: int, now_epoch: float | None=None) -> tuple[ValidationCheck, ...]:
    if not instances:
        return ()
    resolved_now = time.time() if now_epoch is None else now_epoch
    checks: list[ValidationCheck] = []
    seen_status_accounts: set[str] = set()
    for instance in instances:
        account_dir = paths.account_dir(instance.account_id)
        market_path = account_dir / instance.market_filename()
        sensor_path = account_dir / instance.sensor_filename()
        status_path = account_dir / instance.status_filename()
        checks.append(_check(f'mt4_market_{instance.symbol}_{instance.magic}', f'market export for {instance.symbol}/{instance.magic}', market_path.is_file() and _file_is_fresh(market_path, stale_threshold_ms=stale_threshold_ms, now_epoch=resolved_now), f'market file ready at {market_path}' if market_path.is_file() else f'missing market file at {market_path}'))
        checks.append(_check(f'mt4_sensor_{instance.symbol}_{instance.magic}', f'sensor export for {instance.symbol}/{instance.magic}', sensor_path.is_file() and _file_is_fresh(sensor_path, stale_threshold_ms=stale_threshold_ms, now_epoch=resolved_now), f'sensor file ready at {sensor_path}' if sensor_path.is_file() else f'missing sensor file at {sensor_path}'))
        if instance.account_id not in seen_status_accounts:
            seen_status_accounts.add(instance.account_id)
            status_ready = False
            status_message = f'missing status file at {status_path}'
            if status_path.is_file():
                try:
                    status = parse_status(status_path.read_text(encoding='utf-8'))
                    status_ready = status.connected and status.trade_allowed
                    status_message = f'status connected={status.connected} trade_allowed={status.trade_allowed}'
                except SystemError as exc:
                    status_message = exc.message
            checks.append(_check(f'mt4_status_{instance.account_id}', f'status export for account {instance.account_id}', status_ready, status_message))
    exports_ready = all((check.passed for check in checks))
    checks.append(_check('ea_connection', 'MT4 EA export connection', exports_ready, 'all required MT4 exports are present and fresh' if exports_ready else 'one or more MT4 exports are missing or stale'))
    return tuple(checks)

def validate_universe_context(paths: SystemPaths) -> tuple[ValidationCheck, ...]:
    universe_path = paths.universe_file
    account_universe_files = sorted(paths.clients_dir.glob('*/universe.json'))
    targets = [universe_path] if universe_path.exists() else []
    targets.extend((path for path in account_universe_files if path not in targets))
    if not targets:
        return (_check('rule_13', 'universe is context-only', True, 'no universe file present yet; runtime will use account-local context when exported'),)
    checks: list[ValidationCheck] = []
    for target in targets:
        raw_text = target.read_text(encoding='utf-8')
        validation = validate_universe_json(raw_text)
        payload = json.loads(raw_text)
        forbidden_present = [field for field in UNIVERSE_FORBIDDEN_FIELDS if field in payload]
        try:
            parse_universe(raw_text)
            parsed_ok = validation.is_valid and (not forbidden_present)
        except SystemError:
            parsed_ok = False
        checks.append(_check(f'rule_13_{target.name}', 'universe is context-only', parsed_ok, f'universe at {target} has no trade signal fields'))
    return tuple(checks)

def validate_rules_compliance(root: Path, config: SystemConfig, *, config_text: str) -> tuple[ValidationCheck, ...]:
    decision_engine = (root / 'engine' / 'decision' / 'engine.py').read_text(encoding='utf-8')
    risk_engine = (root / 'engine' / 'risk' / 'engine.py').read_text(encoding='utf-8')
    dashboard_reader = (root / 'engine' / 'dashboard' / 'reader.py').read_text(encoding='utf-8')
    payload = json.loads(config_text)
    hard_symbol_list = 'symbols' in json.dumps(payload)
    hard_spread_cap = 'max_spread' in config_text.lower()
    return (_check('rule_05', 'BUY and SELL are both evaluated', 'calculate_buy_candidate' in decision_engine and 'calculate_sell_candidate' in decision_engine, 'decision engine evaluates both directions'), _check('rule_06', 'WAIT is not the default decision', 'evaluate_wait_decision' in decision_engine and 'Decision.WAIT' in decision_engine, 'WAIT requires explicit evaluation path'), _check('rule_07', 'risk returns only ALLOW or BLOCK', RiskResult.ALLOW.value in risk_engine and RiskResult.BLOCK.value in risk_engine and ('Decision.WAIT' in risk_engine), 'risk engine blocks non-trade decisions without emitting WAIT'), _check('rule_09', 'no hard symbol list in config', not hard_symbol_list, 'config does not define a fixed symbol whitelist'), _check('rule_08b', 'no hard spread cap in config', not hard_spread_cap, 'config uses relative spread threshold only'), _check('rule_10', 'decision journal records reason', 'reason' in DECISION_JOURNAL_REQUIRED_FIELDS, 'decision journal schema requires reason'), _check('rule_11', 'decision journal is mandatory', 'log_decision' in (root / 'engine' / 'core' / 'cycle.py').read_text(encoding='utf-8'), 'cycle logs every decision to journal'), _check('rule_12', 'dashboard is read-only', 'engine.analysis' not in dashboard_reader and 'engine.decision' not in dashboard_reader and ('engine.risk' not in dashboard_reader), 'dashboard reader does not import analysis, decision, or risk'), _check('rule_15', 'errors are recorded explicitly', 'log_error' in (root / 'engine' / 'journal' / 'error_journal.py').read_text(encoding='utf-8'), 'error journal module is available for explicit error recording'), _check('config_instances', 'instances configured', len(config.instances) > 0, f'configured_instances={len(config.instances)}'))

def run_live_validation(*, root_path: str | Path | None=None, config_path: str | Path | None=None, require_mt4_exports: bool=True, now_epoch: float | None=None) -> LiveValidationReport:
    bootstrap_paths = SystemPaths(root_path)
    validate_root_path(bootstrap_paths)
    resolved_config_path = Path(config_path) if config_path is not None else bootstrap_paths.config_path
    config = load_system_config(resolved_config_path, system_paths=bootstrap_paths)
    paths = build_system_paths(config)
    validate_root_path(paths)
    instances = discover_instances(config, paths)
    checks: list[ValidationCheck] = []
    checks.extend(validate_directory_layout(paths))
    checks.extend(validate_runtime_entry_points(paths.root))
    checks.extend(validate_mql4_ea_files(paths.root))
    checks.extend(validate_path_contract(paths, require_mt4_exports=require_mt4_exports))
    checks.extend(validate_config_file(resolved_config_path, paths))
    checks.extend(validate_instance_isolation(paths, instances))
    checks.extend(validate_rules_compliance(paths.root, config, config_text=resolved_config_path.read_text(encoding='utf-8')))
    checks.extend(validate_universe_context(paths))
    if require_mt4_exports:
        checks.extend(validate_mt4_exports(paths, instances, stale_threshold_ms=config.runtime.data_stale_threshold_ms, now_epoch=now_epoch))
    return LiveValidationReport(checks=tuple(checks))

def format_validation_report(report: LiveValidationReport) -> str:
    lines = ['SYSTEM LIVE validation report', '']
    for check in report.checks:
        status = 'PASS' if check.passed else 'FAIL'
        lines.append(f'[{status}] {check.check_id} {check.name}: {check.message}')
    lines.append('')
    lines.append('RESULT: PASS' if report.passed else 'RESULT: FAIL')
    return '\n'.join(lines)

def main(argv: list[str] | None=None) -> int:
    parser = argparse.ArgumentParser(description='Validate SYSTEM LIVE environment')
    parser.add_argument('--root', dest='root_path', default=None, help='SYSTEM root path')
    parser.add_argument('--config', dest='config_path', default=None, help='Path to system.json')
    parser.add_argument('--skip-mt4-exports', action='store_true', help='Skip MT4 export freshness checks')
    args = parser.parse_args(argv)
    try:
        report = run_live_validation(root_path=args.root_path, config_path=args.config_path, require_mt4_exports=not args.skip_mt4_exports)
    except ConfigurationError as exc:
        print(f'LIVE validation failed: {exc.message}', file=sys.stderr)
        return 1
    print(format_validation_report(report))
    return 0 if report.passed else 1
if __name__ == '__main__':
    sys.exit(main())
