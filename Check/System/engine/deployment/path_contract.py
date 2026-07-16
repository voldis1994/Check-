from __future__ import annotations
import json
import re
from dataclasses import dataclass
from pathlib import Path
from engine.core.paths import (
    DEFAULT_CACHE_PATH,
    DEFAULT_CLIENTS_PATH,
    DEFAULT_HISTORY_PATH,
    DEFAULT_LOGS_PATH,
    DEFAULT_UNIVERSE_PATH,
    CONFIG_RELATIVE_PATH,
    SystemPaths,
)
MODULE_NAME = 'deployment.path_contract'
MQL4_ROOT_CONFIG = Path('mql4') / 'Include' / 'SYSTEM_RootConfig.mqh'
MQL4_PATHS_MQH = Path('mql4') / 'Include' / 'SYSTEM_Paths.mqh'
_RELATIVE_PATH_PAIRS = (('SYSTEM_CLIENTS_RELATIVE_PATH', DEFAULT_CLIENTS_PATH), ('SYSTEM_LOGS_RELATIVE_PATH', DEFAULT_LOGS_PATH), ('SYSTEM_CACHE_RELATIVE_PATH', DEFAULT_CACHE_PATH), ('SYSTEM_HISTORY_RELATIVE_PATH', DEFAULT_HISTORY_PATH), ('SYSTEM_UNIVERSE_RELATIVE_PATH', DEFAULT_UNIVERSE_PATH))

@dataclass(frozen=True)
class PathContractCheck:
    check_id: str
    name: str
    passed: bool
    message: str

@dataclass(frozen=True)
class PathContractReport:
    checks: tuple[PathContractCheck, ...]

    @property
    def passed(self) -> bool:
        return all((check.passed for check in self.checks))

    @property
    def failed_checks(self) -> tuple[PathContractCheck, ...]:
        return tuple((check for check in self.checks if not check.passed))

def _check(check_id: str, name: str, passed: bool, message: str) -> PathContractCheck:
    return PathContractCheck(check_id=check_id, name=name, passed=passed, message=message)

def resolve_deployment_root(start: Path | None=None) -> Path:
    anchor = start or Path(__file__).resolve()
    for candidate in (anchor, *anchor.parents):
        if (candidate / 'run_live.py').is_file() and (candidate / CONFIG_RELATIVE_PATH).is_file():
            return candidate.resolve()
    raise FileNotFoundError('could not locate deployment root containing run_live.py and config/system.json')

def normalize_path(path: str | Path) -> Path:
    text = str(path).strip()
    if len(text) >= 2 and text[1] == ':' and text[0].isalpha():
        return Path(text.replace('\\', '/'))
    return Path(text).expanduser().resolve()

def read_config_root_path(config_path: Path) -> str:
    payload = json.loads(config_path.read_text(encoding='utf-8'))
    system = payload.get('system')
    if not isinstance(system, dict):
        raise ValueError('config missing system section')
    root_path = system.get('root_path')
    if not isinstance(root_path, str) or not root_path.strip():
        raise ValueError('config missing system.root_path')
    return root_path

def parse_mql4_define(source: str, name: str) -> str:
    match = re.search(f'#define\\s+{re.escape(name)}\\s+\\"([^\\"]*)\\"', source)
    if match is None:
        raise ValueError(f'missing define: {name}')
    return match.group(1).replace('\\\\', '\\')

def read_mql4_compiled_root(root: Path) -> str:
    source = (root / MQL4_ROOT_CONFIG).read_text(encoding='utf-8')
    return parse_mql4_define(source, 'SYSTEM_ROOT_PATH')

def _to_mql4_relative(value: str) -> str:
    return value.replace('/', '\\')

def validate_relative_path_segments(root: Path) -> tuple[PathContractCheck, ...]:
    paths_source = (root / MQL4_PATHS_MQH).read_text(encoding='utf-8')
    checks: list[PathContractCheck] = []
    for define_name, python_relative in _RELATIVE_PATH_PAIRS:
        mql4_relative = parse_mql4_define(paths_source, define_name)
        expected = _to_mql4_relative(python_relative)
        checks.append(_check(f'relative_{define_name.lower()}', f'{define_name} matches Python', mql4_relative == expected, f'mql4={mql4_relative!r} python={expected!r}'))
    return tuple(checks)

def validate_config_matches_runtime_root(root: Path) -> PathContractCheck:
    config_path = root / CONFIG_RELATIVE_PATH
    try:
        configured_root = normalize_path(read_config_root_path(config_path))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return _check('config_runtime_root', 'config root_path matches runtime root', False, str(exc))
    runtime_root = normalize_path(root)
    passed = configured_root == runtime_root
    return _check('config_runtime_root', 'config root_path matches runtime root', passed, f'config={configured_root} runtime={runtime_root}' if passed else f'MISMATCH: config.system.root_path={configured_root} but run_live.py root={runtime_root}. Run: python scripts/sync_paths.py')

def validate_mql4_root_matches_config(root: Path) -> PathContractCheck:
    config_path = root / CONFIG_RELATIVE_PATH
    mql4_config_path = root / MQL4_ROOT_CONFIG
    try:
        configured_root = normalize_path(read_config_root_path(config_path))
        compiled_root = normalize_path(read_mql4_compiled_root(root))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return _check('mql4_config_root', 'MQL4 compiled root matches config root', False, str(exc))
    passed = configured_root == compiled_root
    return _check('mql4_config_root', 'MQL4 compiled root matches config root', passed, f'both={configured_root}' if passed else f'MISMATCH: config.system.root_path={configured_root} but SYSTEM_ROOT_PATH={compiled_root}. Run: python scripts/sync_paths.py')

def validate_mt4_data_visible_to_python(root: Path) -> PathContractCheck:
    config_path = root / CONFIG_RELATIVE_PATH
    try:
        configured_root = normalize_path(read_config_root_path(config_path))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return _check('mt4_data_visible', 'Python reads MT4 exports from configured root', False, str(exc))
    clients_dir = configured_root / DEFAULT_CLIENTS_PATH
    if not clients_dir.is_dir():
        return _check('mt4_data_visible', 'Python reads MT4 exports from configured root', False, f'clients directory missing at {clients_dir}')
    account_dirs = [entry for entry in clients_dir.iterdir() if entry.is_dir()]
    if not account_dirs:
        return _check('mt4_data_visible', 'Python reads MT4 exports from configured root', True, f'clients directory exists at {clients_dir} (no account exports yet)')
    export_files = list(account_dirs[0].glob('market_*.csv'))
    passed = len(export_files) > 0
    return _check('mt4_data_visible', 'Python reads MT4 exports from configured root', passed, f'found MT4 market exports under {account_dirs[0]}' if passed else f'no market_*.csv under {account_dirs[0]}. MT4 EA likely writes to a different root than config.system.root_path')

def validate_no_competing_deployment_trees(root: Path) -> PathContractCheck:
    nested = root / 'SYSTEM'
    nested_config = nested / CONFIG_RELATIVE_PATH
    if not nested_config.is_file():
        return _check('no_competing_trees', 'no competing nested SYSTEM deployment tree', True, 'single deployment root')
    try:
        outer_root = normalize_path(read_config_root_path(root / CONFIG_RELATIVE_PATH))
        inner_root = normalize_path(read_config_root_path(nested_config))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return _check('no_competing_trees', 'no competing nested SYSTEM deployment tree', False, str(exc))
    if outer_root == inner_root:
        return _check('no_competing_trees', 'no competing nested SYSTEM deployment tree', True, f'nested SYSTEM/ config points to same root: {outer_root}')
    outer_clients = outer_root / DEFAULT_CLIENTS_PATH
    inner_clients = inner_root / DEFAULT_CLIENTS_PATH
    outer_has_data = outer_clients.is_dir() and any(outer_clients.iterdir())
    inner_has_data = inner_clients.is_dir() and any(inner_clients.iterdir())
    if outer_has_data and inner_has_data:
        return _check('no_competing_trees', 'no competing nested SYSTEM deployment tree', False, f'conflicting roots with data: outer={outer_root} inner={inner_root}. Pick one directory and run scripts/sync_paths.py there only')
    return _check('no_competing_trees', 'no competing nested SYSTEM deployment tree', True, f'nested SYSTEM/ uses different root ({inner_root}) but only one tree has client data')

def run_path_contract_validation(root: str | Path | None=None, *, require_mt4_exports: bool=False) -> PathContractReport:
    deployment_root = normalize_path(root) if root is not None else resolve_deployment_root()
    checks: list[PathContractCheck] = [validate_config_matches_runtime_root(deployment_root), validate_mql4_root_matches_config(deployment_root), validate_no_competing_deployment_trees(deployment_root), *validate_relative_path_segments(deployment_root)]
    if require_mt4_exports:
        checks.append(validate_mt4_data_visible_to_python(deployment_root))
    return PathContractReport(checks=tuple(checks))

def format_path_contract_report(report: PathContractReport) -> str:
    lines = ['SYSTEM path contract', '']
    for check in report.checks:
        status = 'PASS' if check.passed else 'FAIL'
        lines.append(f'[{status}] {check.check_id} {check.name}: {check.message}')
    lines.append('')
    lines.append('RESULT: PASS' if report.passed else 'RESULT: FAIL')
    return '\n'.join(lines)

def write_mql4_root_config(root: Path, output_path: Path | None=None) -> Path:
    resolved = normalize_path(root)
    escaped = str(resolved).replace('\\', '\\\\')
    target = output_path or resolved / MQL4_ROOT_CONFIG
    target.parent.mkdir(parents=True, exist_ok=True)
    content = f'#ifndef __SYSTEM_ROOT_CONFIG_MQH__\n#define __SYSTEM_ROOT_CONFIG_MQH__\n\n#define SYSTEM_ROOT_PATH "{escaped}"\n\n#endif\n'
    target.write_text(content, encoding='ascii')
    return target

def write_config_root_path(root: Path, config_path: Path | None=None) -> Path:
    resolved = normalize_path(root)
    target = config_path or resolved / CONFIG_RELATIVE_PATH
    payload = json.loads(target.read_text(encoding='utf-8'))
    system = payload.setdefault('system', {})
    if not isinstance(system, dict):
        raise ValueError('config system section must be an object')
    system['root_path'] = str(resolved)
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    return target

def sync_deployment_paths(root: str | Path | None=None) -> Path:
    deployment_root = normalize_path(root) if root is not None else resolve_deployment_root()
    write_config_root_path(deployment_root)
    write_mql4_root_config(deployment_root)
    return deployment_root


def _account_dirs_with_market_exports(clients_dir: Path) -> list[Path]:
    ranked: list[tuple[float, Path]] = []
    for entry in clients_dir.iterdir():
        if not entry.is_dir():
            continue
        market_files = list(entry.glob('market_*.csv'))
        if not market_files:
            continue
        newest = max(path.stat().st_mtime for path in market_files)
        ranked.append((newest, entry))
    ranked.sort(key=lambda item: (-item[0], item[1].name))
    return [entry for _, entry in ranked]


def _discover_market_instance_rows(clients_dir: Path, *, parse_market_filename) -> list[dict[str, str | int | bool]]:
    rows: list[dict[str, str | int | bool]] = []
    seen: set[tuple[str, str, int]] = set()
    for account_dir in _account_dirs_with_market_exports(clients_dir):
        for entry in sorted(account_dir.glob('market_*.csv')):
            parsed = parse_market_filename(entry.name)
            if parsed is None:
                continue
            symbol, magic = parsed
            key = (account_dir.name, symbol, magic)
            if key in seen:
                continue
            seen.add(key)
            rows.append({'account_id': account_dir.name, 'symbol': symbol, 'magic': magic, 'enabled': True})
    return rows


def _instance_key(row: dict[str, object]) -> tuple[str, str, int] | None:
    try:
        account_id = str(row.get('account_id') or '')
        symbol = str(row.get('symbol') or '')
        magic = int(row.get('magic'))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if not account_id or not symbol:
        return None
    return (account_id, symbol, magic)


def sync_config_instances_from_clients(root: str | Path, *, config_path: Path | None=None) -> bool:
    from engine.core.config import load_system_config
    from engine.core.lifecycle import build_system_paths, parse_market_filename

    deployment_root = normalize_path(root)
    resolved_config_path = config_path if config_path is not None else deployment_root / CONFIG_RELATIVE_PATH
    bootstrap_paths = SystemPaths(deployment_root)
    config = load_system_config(resolved_config_path, system_paths=bootstrap_paths)
    paths = build_system_paths(config, runtime_root=deployment_root)
    clients_dir = paths.clients_dir
    if not clients_dir.is_dir():
        return False
    discovered = _discover_market_instance_rows(clients_dir, parse_market_filename=parse_market_filename)
    if not discovered:
        return False
    payload = json.loads(resolved_config_path.read_text(encoding='utf-8'))
    instances = payload.get('instances')
    if not isinstance(instances, list) or not instances:
        return False
    existing = [item for item in instances if isinstance(item, dict)]
    if not existing:
        return False

    discovered_by_account: dict[str, list[dict[str, str | int | bool]]] = {}
    for row in discovered:
        discovered_by_account.setdefault(str(row['account_id']), []).append(row)
    discovered_keys = {_instance_key(row) for row in discovered}
    discovered_keys.discard(None)

    # Single stale placeholder (config account has no exports) → replace with all live exports.
    only_account = str(existing[0].get('account_id') or '')
    if len(existing) == 1 and only_account not in discovered_by_account:
        payload['instances'] = discovered
        resolved_config_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        return True

    merged: list[dict[str, str | int | bool]] = []
    covered: set[tuple[str, str, int]] = set()

    for item in existing:
        key = _instance_key(item)
        account_id = str(item.get('account_id') or '')
        account_rows = discovered_by_account.get(account_id, [])
        if key is not None and key in discovered_keys:
            enabled = bool(item.get('enabled', True))
            row = {'account_id': key[0], 'symbol': key[1], 'magic': key[2], 'enabled': enabled}
            merged.append(row)
            covered.add(key)
            continue
        if len(account_rows) == 1:
            row = dict(account_rows[0])
            row['enabled'] = bool(item.get('enabled', True))
            row_key = _instance_key(row)
            if row_key is not None:
                covered.add(row_key)
            merged.append(row)
            continue
        # Keep pre-declared account waiting for its first EA export.
        merged.append({'account_id': account_id, 'symbol': str(item.get('symbol') or 'EURUSD'), 'magic': int(item.get('magic') or 100001), 'enabled': bool(item.get('enabled', True))})

    for row in discovered:
        row_key = _instance_key(row)
        if row_key is None or row_key in covered:
            continue
        merged.append(dict(row))
        covered.add(row_key)

    if merged == existing:
        return False
    payload['instances'] = merged
    resolved_config_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    return True


def prepare_deployment_root(root: str | Path) -> Path:
    from engine.core.config import load_system_config
    from engine.core.lifecycle import build_system_paths

    deployment_root = sync_deployment_paths(root)
    bootstrap_paths = SystemPaths(deployment_root)
    config = load_system_config(deployment_root / CONFIG_RELATIVE_PATH, system_paths=bootstrap_paths)
    paths = build_system_paths(config, runtime_root=deployment_root)
    paths.ensure_directories()
    for definition in config.instances:
        if definition.enabled:
            paths.ensure_account_directories(definition.account_id)
    sync_config_instances_from_clients(deployment_root)
    return deployment_root
