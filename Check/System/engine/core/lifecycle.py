from __future__ import annotations
import logging
import re
import signal
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable
from engine.core.atomic_io import atomic_read_text
from engine.core.cache import invalidate_startup_cache
from engine.core.config import load_system_config
from engine.core.instance import Instance, ensure_unique_instance_keys
from engine.core.logging_setup import log_event, setup_account_logger, setup_system_logger
from engine.core.paths import SystemPaths
from engine.normalizer.spread_model import SpreadModelSnapshot
from engine.protocol.constants import FILENAME_STATUS, RiskResult
from engine.protocol.errors import ConfigurationError
from engine.protocol.identity import validate_account_id
from engine.protocol.models import SpreadStateRecord, SystemConfig
from engine.protocol.parser import parse_status
from engine.state.instance_state import InstanceState
from engine.state.memory import StateMemory
from engine.state.spread_state import SpreadState
MODULE_NAME = 'core.lifecycle'
MARKET_FILENAME_PATTERN = re.compile('^market_(.+)_(\\d+)\\.csv$')
STARTUP_EXIT_CODE = 0
STARTUP_ERROR_EXIT_CODE = 1

def _config_error(message: str, **context: object) -> ConfigurationError:
    return ConfigurationError(message, module=MODULE_NAME, context=dict(context))

def build_system_paths(config: SystemConfig, runtime_root: str | Path | None=None) -> SystemPaths:
    resolved_root = runtime_root if runtime_root is not None else config.system.root_path
    return SystemPaths(resolved_root, clients_path=config.paths.clients, logs_path=config.paths.logs, cache_path=config.paths.cache, history_path=config.paths.history, universe_path=config.paths.universe)

def ensure_runtime_paths_aligned(bootstrap_paths: SystemPaths, config: SystemConfig, *, config_path: Path) -> SystemConfig:
    configured_root = Path(config.system.root_path).expanduser().resolve()
    bootstrap_root = bootstrap_paths.root
    if configured_root == bootstrap_root:
        return config
    from engine.deployment.path_contract import sync_config_instances_from_clients, sync_deployment_paths
    sync_deployment_paths(bootstrap_root)
    sync_config_instances_from_clients(bootstrap_root, config_path=config_path)
    return load_system_config(config_path, system_paths=bootstrap_paths)

def format_mt4_missing_exports_message(paths: SystemPaths, instances: Iterable[Instance]) -> str:
    instance_list = tuple(instances)
    missing: list[str] = []
    for instance in instance_list:
        market_path = paths.account_dir(instance.account_id) / instance.market_filename()
        if not market_path.is_file():
            missing.append(str(market_path))
    lines = ['MT4 export files not found. Python reads market data from:', *('  ' + path for path in missing), '', f'deployment root: {paths.root}', f'clients_dir: {paths.clients_dir}']
    if paths.clients_dir.is_dir():
        account_dirs = sorted(entry for entry in paths.clients_dir.iterdir() if entry.is_dir())
        if account_dirs:
            lines.append('')
            lines.append('account folders found on disk:')
            for account_dir in account_dirs:
                market_files = sorted(p.name for p in account_dir.glob('market_*.csv'))
                if market_files:
                    lines.append(f'  {account_dir.name}: {", ".join(market_files)}')
                else:
                    lines.append(f'  {account_dir.name}: no market_*.csv')
        else:
            lines.append('')
            lines.append(f'no account folders under {paths.clients_dir}')
    if instance_list:
        configured_accounts = sorted({instance.account_id for instance in instance_list})
        lines.append('')
        lines.append(f'configured account_id(s): {", ".join(configured_accounts)}')
    lines.extend([
        '',
        'Fix (MT4 must WRITE these files — chart moving is not enough):',
        '  1. MT4 open, SYSTEM_EA attached to EURUSD M1',
        '  2. AutoTrading ON (green button)',
        '  3. EA Properties -> Common -> Allow DLL imports = YES',
        f'  4. EA Inputs -> SystemRootPath = {paths.root}',
        '  5. Recompile SYSTEM_EA.mq4 in MetaEditor after update',
        '  6. Experts tab: look for \"SYSTEM export OK\"',
        '  7. Fallback path (no DLL): %APPDATA%\\MetaQuotes\\Terminal\\Common\\Files\\CheckSystem\\',
        '  8. Run: python tools\\show_paths.py',
    ])
    return '\n'.join(lines)

def validate_mt4_runtime_ready(paths: SystemPaths, instances: Iterable[Instance]) -> None:
    instance_list = tuple(instances)
    if not instance_list:
        raise _config_error('no trading instances configured or discovered', clients_dir=str(paths.clients_dir))
    missing = False
    for instance in instance_list:
        market_path = paths.account_dir(instance.account_id) / instance.market_filename()
        if not market_path.is_file():
            missing = True
            break
    if missing:
        raise _config_error(format_mt4_missing_exports_message(paths, instance_list), clients_dir=str(paths.clients_dir))

def wait_for_mt4_exports(paths: SystemPaths, instances: Iterable[Instance], *, wait_seconds: float, poll_interval_seconds: float=2.0) -> None:
    from engine.core.mt4_bridge import mirror_common_bridge_to_deployment
    if wait_seconds <= 0:
        mirror_common_bridge_to_deployment(paths)
        validate_mt4_runtime_ready(paths, instances)
        return
    deadline = time.monotonic() + wait_seconds
    printed_hint = False
    while True:
        mirror_common_bridge_to_deployment(paths)
        try:
            validate_mt4_runtime_ready(paths, instances)
            if printed_hint:
                print('MT4 exports detected — starting live engine.', flush=True)
            return
        except ConfigurationError:
            remaining = max(0.0, deadline - time.monotonic())
            if remaining <= 0:
                validate_mt4_runtime_ready(paths, instances)
            if not printed_hint:
                print(format_mt4_missing_exports_message(paths, instances), file=sys.stderr)
                printed_hint = True
            print(f'waiting for MT4 exports ({int(remaining)}s remaining)...', file=sys.stderr, flush=True)
            time.sleep(min(poll_interval_seconds, max(0.5, remaining)))

def validate_root_path(paths: SystemPaths) -> None:
    if not paths.root.exists():
        raise _config_error('system root path does not exist', path=str(paths.root))
    if not paths.root.is_dir():
        raise _config_error('system root path is not a directory', path=str(paths.root))

def validate_config_root_path(config: SystemConfig, bootstrap_paths: SystemPaths) -> None:
    configured_root = Path(config.system.root_path).expanduser().resolve()
    bootstrap_root = bootstrap_paths.root
    if configured_root != bootstrap_root:
        raise _config_error('system.root_path does not match runtime root path', configured_root=str(configured_root), bootstrap_root=str(bootstrap_root))

def parse_market_filename(filename: str) -> tuple[str, int] | None:
    match = MARKET_FILENAME_PATTERN.match(filename)
    if match is None:
        return None
    return (match.group(1), int(match.group(2)))

def instances_from_config(config: SystemConfig) -> list[Instance]:
    return [Instance(definition.account_id, definition.symbol, definition.magic) for definition in config.instances if definition.enabled]

def discover_instances_from_account(paths: SystemPaths, account_id: str) -> list[Instance]:
    account_dir = paths.account_dir(account_id)
    if not account_dir.is_dir():
        return []
    discovered: list[Instance] = []
    for entry in account_dir.iterdir():
        if not entry.is_file():
            continue
        parsed = parse_market_filename(entry.name)
        if parsed is None:
            continue
        symbol, magic = parsed
        discovered.append(Instance(account_id, symbol, magic))
    return discovered

def discover_instances(config: SystemConfig, paths: SystemPaths) -> tuple[Instance, ...]:
    discovered: dict[tuple[str, str, int], Instance] = {}
    for instance in instances_from_config(config):
        discovered[instance.instance_key] = instance
    if config.runtime.auto_discover_instances and paths.clients_dir.exists():
        for account_dir in sorted(paths.clients_dir.iterdir()):
            if not account_dir.is_dir():
                continue
            validate_account_id(account_dir.name, MODULE_NAME)
            for instance in discover_instances_from_account(paths, account_dir.name):
                discovered[instance.instance_key] = instance
    ensure_unique_instance_keys(discovered.values())
    return tuple((discovered[key] for key in sorted(discovered)))

def load_runtime_memory(paths: SystemPaths, instances: Iterable[Instance], *, lookback_bars: int) -> StateMemory:
    memory = StateMemory(lookback_bars=lookback_bars)
    for instance in instances:
        item = memory.get_or_create(instance)
        item.instance_state = InstanceState.load(paths, instance)
        item.spread_state = SpreadState.load(paths, instance)
    return memory

def spread_snapshot_from_record(record: SpreadStateRecord) -> SpreadModelSnapshot:
    if record.sample_count <= 0:
        history: tuple[float, ...] = ()
    else:
        history = tuple([record.current_spread] * record.sample_count)
    return SpreadModelSnapshot(history=history, mean_spread=record.mean_spread, std_spread=record.std_spread, median_spread=record.median_spread, current_spread=record.current_spread, relative_spread=record.relative_spread)

def build_spread_models(memory: StateMemory) -> dict[tuple[str, str, int], SpreadModelSnapshot]:
    models: dict[tuple[str, str, int], SpreadModelSnapshot] = {}
    for key, item in memory.items().items():
        if item.spread_state.record is not None:
            models[key] = spread_snapshot_from_record(item.spread_state.record)
    return models

def invalidate_runtime_cache(paths: SystemPaths, instances: Iterable[Instance]) -> int:
    removed = 0
    for instance in instances:
        removed += invalidate_startup_cache(paths.instance_cache_dir(instance.account_id, instance.symbol, instance.magic))
    return removed

def read_status_connected(paths: SystemPaths, account_id: str) -> bool | None:
    status_path = paths.account_dir(account_id) / FILENAME_STATUS.format(account_id=account_id)
    if not status_path.exists():
        return None
    record = parse_status(atomic_read_text(status_path))
    return record.connected

@dataclass
class LiveRuntime:
    paths: SystemPaths
    config: SystemConfig
    memory: StateMemory
    system_logger: logging.Logger
    spread_models: dict[tuple[str, str, int], SpreadModelSnapshot] = field(default_factory=dict)
    account_loggers: dict[str, logging.Logger] = field(default_factory=dict)
    shutdown_requested: bool = False
    allow_control_writes: bool = True

def ensure_account_logger(runtime: LiveRuntime, account_id: str) -> logging.Logger:
    existing = runtime.account_loggers.get(account_id)
    if existing is not None:
        return existing
    logger = setup_account_logger(runtime.paths, account_id, level=runtime.config.logging.level, format_name=runtime.config.logging.format)
    runtime.account_loggers[account_id] = logger
    return logger

def register_account_loggers(runtime: LiveRuntime, instances: Iterable[Instance]) -> None:
    for instance in instances:
        ensure_account_logger(runtime, instance.account_id)

def log_runtime_event(runtime: LiveRuntime, *, level: str, module: str, message: str, account_id: str | None=None, symbol: str | None=None, magic: int | None=None) -> None:
    log_event(runtime.system_logger, level=level, module=module, message=message, account_id=account_id, symbol=symbol, magic=magic)
    if account_id:
        log_event(ensure_account_logger(runtime, account_id), level=level, module=module, message=message, account_id=account_id, symbol=symbol, magic=magic)

def startup(*, root_path: str | Path | None=None, config_path: str | Path | None=None, require_mt4_exports: bool=False, wait_for_mt4_seconds: float=0.0) -> LiveRuntime:
    bootstrap_paths = SystemPaths(root_path)
    validate_root_path(bootstrap_paths)
    resolved_config_path = Path(config_path) if config_path is not None else bootstrap_paths.config_path
    config = load_system_config(resolved_config_path, system_paths=bootstrap_paths)
    config = ensure_runtime_paths_aligned(bootstrap_paths, config, config_path=resolved_config_path)
    validate_config_root_path(config, bootstrap_paths)
    paths = build_system_paths(config, runtime_root=bootstrap_paths.root)
    validate_root_path(paths)
    paths.ensure_directories()
    for definition in config.instances:
        if definition.enabled:
            paths.ensure_account_directories(definition.account_id)
    system_logger = setup_system_logger(paths, level=config.logging.level, format_name=config.logging.format)
    from engine.core.version import read_system_version
    system_version = read_system_version(paths.root)
    log_event(system_logger, level='INFO', module=MODULE_NAME, message=f'startup begin version={system_version}')
    instances = discover_instances(config, paths)
    if wait_for_mt4_seconds > 0:
        try:
            wait_for_mt4_exports(paths, instances, wait_seconds=wait_for_mt4_seconds)
        except ConfigurationError as exc:
            if require_mt4_exports:
                raise
            print(exc.message, file=sys.stderr)
            print('WARNING: starting without MT4 market exports. Cycles will SKIP until SYSTEM_EA writes files.', file=sys.stderr, flush=True)
            log_event(system_logger, level='WARNING', module=MODULE_NAME, message='startup continuing without MT4 exports')
    elif require_mt4_exports:
        validate_mt4_runtime_ready(paths, instances)
    memory = load_runtime_memory(paths, instances, lookback_bars=config.analysis.lookback_bars)
    spread_models = build_spread_models(memory)
    removed_hashes = invalidate_runtime_cache(paths, instances)
    runtime = LiveRuntime(paths=paths, config=config, memory=memory, system_logger=system_logger, spread_models=spread_models)
    register_account_loggers(runtime, instances)
    log_event(system_logger, level='INFO', module=MODULE_NAME, message=f'startup complete instances={len(instances)} cache_hashes_removed={removed_hashes}')
    from engine.core.recovery import run_runtime_recovery
    run_runtime_recovery(runtime, instances=instances)
    return runtime

def request_shutdown(runtime: LiveRuntime) -> None:
    runtime.shutdown_requested = True
    runtime.allow_control_writes = False

def persist_runtime_state(runtime: LiveRuntime) -> None:
    for item in runtime.memory.items().values():
        item.instance_state.save(runtime.paths)
        if item.spread_state.record is not None:
            item.spread_state.save(runtime.paths)

def close_runtime_logging(runtime: LiveRuntime) -> None:
    for handler in list(runtime.system_logger.handlers):
        handler.close()
        runtime.system_logger.removeHandler(handler)
    for logger in runtime.account_loggers.values():
        for handler in list(logger.handlers):
            handler.close()
            logger.removeHandler(handler)
    runtime.account_loggers.clear()

def shutdown(runtime: LiveRuntime) -> int:
    request_shutdown(runtime)
    persist_runtime_state(runtime)
    log_event(runtime.system_logger, level='INFO', module=MODULE_NAME, message='shutdown complete')
    close_runtime_logging(runtime)
    return STARTUP_EXIT_CODE

def print_live_startup_banner(runtime: LiveRuntime, instances: tuple[Instance, ...]) -> None:
    import os
    from engine.core.version import read_system_version
    ai_mode = runtime.config.ai.mode
    ai_key = 'yes' if os.getenv('OPENAI_API_KEY') else 'missing'
    system_version = read_system_version(runtime.paths.root)
    print(f'SYSTEM v{system_version} live started: root={runtime.paths.root}', flush=True)
    print(f'instances={len(instances)} cycle_interval_ms={runtime.config.runtime.cycle_interval_ms} stale_threshold_ms={runtime.config.runtime.data_stale_threshold_ms} closed_bar_entries={runtime.config.runtime.execute_entries_on_closed_bar_only} python_close={runtime.config.trade_management.allow_close} ai_mode={ai_mode} openai_key={ai_key} trail_lookback={runtime.config.trade_management.trailing_lookback_bars} trail_pips={runtime.config.trade_management.trailing_step_pips}', flush=True)
    print(f'logs={runtime.paths.logs_dir}', flush=True)
    for instance in instances:
        market_path = runtime.paths.account_dir(instance.account_id) / instance.market_filename()
        print(f'  {instance.account_id} {instance.symbol} magic={instance.magic} market={"OK" if market_path.is_file() else "MISSING"}', flush=True)
    print('Ctrl+C to stop. Cycle status prints below.', flush=True)

def print_live_cycle_summary(result: object) -> None:
    from engine.core.orchestrator import OrchestratorCycleResult
    if not isinstance(result, OrchestratorCycleResult):
        return
    for item in result.instance_results:
        decision = item.decision_result.decision if item.decision_result is not None else '-'
        decision_reason = item.decision_result.reason if item.decision_result is not None else ''
        risk = item.risk_engine_result.result if item.risk_engine_result is not None else '-'
        risk_reason = item.risk_engine_result.reason if item.risk_engine_result is not None else ''
        action = item.execution_result.order_command.action if item.execution_result is not None else '-'
        management_reason = ''
        if item.execution_result is not None and item.execution_result.order_command.action in {'MODIFY', 'CLOSE'}:
            management_reason = item.execution_result.order_command.reason
        if item.skip_reason:
            reason = item.skip_reason
        elif management_reason:
            reason = management_reason
        elif risk == RiskResult.BLOCK.value and risk_reason:
            reason = risk_reason
        else:
            reason = decision_reason or '-'
        if item.completed:
            status = 'OK'
        elif item.error_logged:
            status = 'SKIP'
        else:
            status = 'FAIL'
        print(f'cycle {item.instance.account_id} {item.instance.symbol} {status} decision={decision} risk={risk} action={action} reason={reason}', flush=True)

def run_live_main(*, root_path: str | Path | None=None, config_path: str | Path | None=None, wait_for_shutdown: Callable[[LiveRuntime], None] | None=None, require_mt4_exports: bool=False, wait_for_mt4_seconds: float=0.0) -> int:
    try:
        runtime = startup(root_path=root_path, config_path=config_path, require_mt4_exports=require_mt4_exports, wait_for_mt4_seconds=wait_for_mt4_seconds)
    except ConfigurationError as exc:
        print(f'startup failed: {exc.message}', file=sys.stderr)
        return STARTUP_ERROR_EXIT_CODE
    instances = discover_instances(runtime.config, runtime.paths)
    print_live_startup_banner(runtime, instances)

    def _handle_shutdown_signal(_signum: int, _frame: object | None) -> None:
        request_shutdown(runtime)
    signal.signal(signal.SIGINT, _handle_shutdown_signal)
    signal.signal(signal.SIGTERM, _handle_shutdown_signal)
    if wait_for_shutdown is not None:
        wait_for_shutdown(runtime)
    else:
        from engine.core.orchestrator import run_runtime_cycles
        interval_seconds = runtime.config.runtime.cycle_interval_ms / 1000.0
        while not runtime.shutdown_requested:
            try:
                cycle_result = run_runtime_cycles(runtime)
                print_live_cycle_summary(cycle_result)
            except Exception as exc:
                print(f'runtime cycle crashed: {exc}', flush=True)
                log_runtime_event(runtime, level='ERROR', module='core.lifecycle', message=f'runtime cycle crashed: {exc}')
            time.sleep(interval_seconds)
    return shutdown(runtime)
