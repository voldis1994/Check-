from __future__ import annotations
import signal
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from engine.core.config import load_system_config
from engine.core.lifecycle import build_system_paths, validate_root_path
from engine.core.logging_setup import log_event, setup_system_logger
from engine.core.paths import SystemPaths
from engine.dashboard.console import render_dashboard
from engine.dashboard.reader import load_dashboard_snapshot
from engine.protocol.errors import ConfigurationError
from engine.protocol.models import SystemConfig
MODULE_NAME = 'dashboard.runtime'
STARTUP_EXIT_CODE = 0
STARTUP_ERROR_EXIT_CODE = 1

@dataclass
class DashboardRuntime:
    paths: SystemPaths
    config: SystemConfig
    shutdown_requested: bool = False

def startup_dashboard(*, root_path: str | Path | None=None, config_path: str | Path | None=None) -> DashboardRuntime:
    bootstrap_paths = SystemPaths(root_path)
    validate_root_path(bootstrap_paths)
    resolved_config_path = Path(config_path) if config_path is not None else bootstrap_paths.config_path
    config = load_system_config(resolved_config_path, system_paths=bootstrap_paths)
    paths = build_system_paths(config)
    validate_root_path(paths)
    paths.ensure_directories()
    system_logger = setup_system_logger(paths, level=config.logging.level, format_name=config.logging.format)
    log_event(system_logger, level='INFO', module=MODULE_NAME, message='dashboard startup complete')
    return DashboardRuntime(paths=paths, config=config)

def request_dashboard_shutdown(runtime: DashboardRuntime) -> None:
    runtime.shutdown_requested = True

def refresh_dashboard(runtime: DashboardRuntime, *, timestamp_utc: str | None=None, output: Callable[[str], None] | None=None) -> str:
    snapshot = load_dashboard_snapshot(runtime.config, runtime.paths, timestamp_utc=timestamp_utc)
    return render_dashboard(snapshot, output=output)

def run_dashboard_main(*, root_path: str | Path | None=None, config_path: str | Path | None=None, wait_for_shutdown: Callable[[DashboardRuntime], None] | None=None, sleep_fn: Callable[[float], None]=time.sleep, output: Callable[[str], None] | None=None) -> int:
    try:
        runtime = startup_dashboard(root_path=root_path, config_path=config_path)
    except ConfigurationError as exc:
        print(f'dashboard startup failed: {exc.message}', file=sys.stderr)
        return STARTUP_ERROR_EXIT_CODE

    def _handle_shutdown_signal(_signum: int, _frame: object | None) -> None:
        request_dashboard_shutdown(runtime)
    signal.signal(signal.SIGINT, _handle_shutdown_signal)
    signal.signal(signal.SIGTERM, _handle_shutdown_signal)
    refresh_dashboard(runtime, output=output)
    if wait_for_shutdown is not None:
        wait_for_shutdown(runtime)
        return STARTUP_EXIT_CODE
    interval_seconds = runtime.config.dashboard.refresh_interval_ms / 1000.0
    while not runtime.shutdown_requested:
        sleep_fn(interval_seconds)
        if runtime.shutdown_requested:
            break
        refresh_dashboard(runtime, output=output)
    return STARTUP_EXIT_CODE

def main() -> int:
    return run_dashboard_main()
if __name__ == '__main__':
    sys.exit(main())
