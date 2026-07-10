from __future__ import annotations
import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine.core.config import load_system_config
from engine.core.instance import Instance
from engine.core.lifecycle import build_system_paths, discover_instances, validate_root_path
from engine.core.paths import SystemPaths
from engine.deployment.path_contract import (
    format_path_contract_report,
    read_mql4_compiled_root,
    resolve_deployment_root,
    run_path_contract_validation,
)
from engine.protocol.errors import ConfigurationError
MODULE_NAME = 'tools.show_paths'
MQL4_ROOT_CONFIG = Path('mql4') / 'Include' / 'SYSTEM_RootConfig.mqh'

@dataclass(frozen=True)
class AccountScan:
    account_id: str
    path: Path
    market_files: tuple[str, ...]
    has_exports: bool

def _status_label(ok: bool) -> str:
    return 'OK' if ok else 'MISSING'

def _scan_clients_dir(paths: SystemPaths) -> tuple[AccountScan, ...]:
    clients_dir = paths.clients_dir
    if not clients_dir.is_dir():
        return ()
    scans: list[AccountScan] = []
    for entry in sorted(clients_dir.iterdir()):
        if not entry.is_dir():
            continue
        market_files = tuple(sorted(p.name for p in entry.glob('market_*.csv')))
        scans.append(AccountScan(account_id=entry.name, path=entry, market_files=market_files, has_exports=bool(market_files)))
    return tuple(scans)

def _instance_file_rows(paths: SystemPaths, instance: Instance) -> list[str]:
    account_dir = paths.account_dir(instance.account_id)
    files = (
        ('market', account_dir / instance.market_filename()),
        ('sensor', account_dir / instance.sensor_filename()),
        ('status', account_dir / instance.status_filename()),
        ('universe', account_dir / 'universe.json'),
        ('control', account_dir / instance.control_filename()),
        ('ack', account_dir / instance.ack_filename()),
        ('decision_journal', paths.account_journal_dir(instance.account_id) / instance.decision_journal_filename()),
        ('trade_journal', paths.account_journal_dir(instance.account_id) / instance.trade_journal_filename()),
        ('error_journal', paths.account_journal_dir(instance.account_id) / instance.error_journal_filename()),
        ('instance_state', paths.account_state_dir(instance.account_id) / instance.instance_state_filename()),
        ('spread_state', paths.account_state_dir(instance.account_id) / instance.spread_state_filename()),
    )
    rows: list[str] = []
    for label, file_path in files:
        rows.append(f'    {label:16} {_status_label(file_path.is_file()):7} {file_path}')
    return rows

def _mql4_join(*parts: str) -> str:
    if not parts:
        return ''
    root = parts[0]
    if root.startswith('/') or (len(root) >= 2 and root[1] != ':'):
        cleaned = [part.replace('\\', '/').strip('/') for part in parts[1:] if part]
        return '/'.join([root.rstrip('/'), *cleaned]) if cleaned else root.rstrip('/')
    cleaned = [part.replace('/', '\\').strip('\\') for part in parts[1:] if part]
    return '\\'.join([root.rstrip('\\'), *cleaned]) if cleaned else root.rstrip('\\')

def _mql4_clients_dir(mql4_root: str, clients_relative: str) -> str:
    return _mql4_join(mql4_root, clients_relative)

def _mql4_account_dir(mql4_root: str, clients_relative: str, account_id: str) -> str:
    return _mql4_join(mql4_root, clients_relative, account_id)

def build_paths_report(*, root_path: str | Path | None=None, config_path: str | Path | None=None) -> str:
    deployment_root = Path(root_path).resolve() if root_path is not None else resolve_deployment_root()
    bootstrap_paths = SystemPaths(deployment_root)
    validate_root_path(bootstrap_paths)
    resolved_config_path = Path(config_path) if config_path is not None else bootstrap_paths.config_path
    config = load_system_config(resolved_config_path, system_paths=bootstrap_paths)
    paths = build_system_paths(config, runtime_root=deployment_root)
    validate_root_path(paths)
    instances = discover_instances(config, paths)
    account_scans = _scan_clients_dir(paths)
    mql4_root = read_mql4_compiled_root(deployment_root)
    contract = run_path_contract_validation(deployment_root)
    run_live_root = deployment_root
    lines: list[str] = []
    lines.append('SYSTEM path diagnostic')
    lines.append('')
    lines.append('[ROOT SOURCES]')
    lines.append(f'  run_live.py root          {run_live_root}')
    lines.append(f'  config.system.root_path   {config.system.root_path}')
    lines.append(f'  python paths.root         {paths.root}')
    lines.append(f'  mql4 SYSTEM_ROOT_PATH     {mql4_root}')
    lines.append(f'  config paths.clients      {config.paths.clients}')
    lines.append(f'  python clients_dir        {paths.clients_dir}')
    lines.append(f'  mql4 clients_dir          {_mql4_clients_dir(mql4_root, config.paths.clients)}')
    lines.append('')
    lines.append('[PATH CONTRACT]')
    lines.extend(format_path_contract_report(contract).splitlines()[2:])
    lines.append('')
    lines.append('[CLIENT DISCOVERY]')
    lines.append(f'  auto_discover_instances   {config.runtime.auto_discover_instances}')
    lines.append(f'  configured instances      {len(config.instances)}')
    lines.append(f'  discovered instances      {len(instances)}')
    if account_scans:
        for scan in account_scans:
            export_note = 'has market exports' if scan.has_exports else 'no market exports'
            lines.append(f'  account {scan.account_id:8} {scan.path} ({export_note})')
            if scan.market_files:
                for name in scan.market_files:
                    lines.append(f'    market file             {name}')
    else:
        lines.append(f'  no account folders under  {paths.clients_dir}')
    lines.append('')
    lines.append('[CONFIGURED / DISCOVERED INSTANCES]')
    if not instances:
        lines.append('  none')
    else:
        for instance in instances:
            lines.append(f'  {instance.account_id} {instance.symbol} magic={instance.magic}')
            lines.append(f'    python account_dir      {paths.account_dir(instance.account_id)}')
            lines.append(f'    mql4 account_dir        {_mql4_account_dir(mql4_root, config.paths.clients, instance.account_id)}')
            lines.extend(_instance_file_rows(paths, instance))
            lines.append('')
    lines.append('[OTHER DIRECTORIES]')
    lines.append(f'  logs_dir                  {paths.logs_dir}')
    lines.append(f'  cache_dir                 {paths.cache_dir}')
    lines.append(f'  history_dir               {paths.history_dir}')
    lines.append(f'  universe_dir              {paths.universe_dir}')
    lines.append(f'  config_path               {paths.config_path}')
    lines.append('')
    if not contract.passed:
        lines.append('RESULT: PATH MISMATCH DETECTED')
        lines.append('Fix: python scripts/sync_paths.py')
        lines.append('MT4 EA input SystemRootPath must match config.system.root_path')
    elif instances and not any((scan.has_exports for scan in account_scans)):
        lines.append('RESULT: ROOTS ALIGN, BUT NO MT4 EXPORTS FOUND')
        lines.append('Check MT4 EA is running and writing under clients_dir')
    else:
        lines.append('RESULT: PATHS LOOK CONSISTENT')
    return '\n'.join(lines)

def run_show_paths(*, root_path: str | Path | None=None, config_path: str | Path | None=None) -> str:
    return build_paths_report(root_path=root_path, config_path=config_path)

def main(argv: list[str] | None=None) -> int:
    parser = argparse.ArgumentParser(description='Show SYSTEM path resolution and client lookup locations')
    parser.add_argument('--root', dest='root_path', default=None, help='Deployment root path')
    parser.add_argument('--config', dest='config_path', default=None, help='Path to system.json')
    args = parser.parse_args(argv)
    try:
        print(run_show_paths(root_path=args.root_path, config_path=args.config_path))
    except ConfigurationError as exc:
        print(f'path diagnostic failed: {exc.message}', file=sys.stderr)
        return 1
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f'path diagnostic failed: {exc}', file=sys.stderr)
        return 1
    return 0
if __name__ == '__main__':
    sys.exit(main())
