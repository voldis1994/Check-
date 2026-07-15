from __future__ import annotations
import argparse
import signal
import socket
import sys
import time
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from engine.core.config import load_system_config
from engine.core.lifecycle import build_system_paths, validate_config_root_path, validate_root_path
from engine.core.logging_setup import log_event, setup_system_logger
from engine.core.paths import SystemPaths
from engine.dashboard.console import live_console_printer, render_dashboard
from engine.dashboard.reader import load_dashboard_snapshot
from engine.dashboard.web import DEFAULT_PORT, start_dashboard_server
from engine.deployment.path_contract import prepare_deployment_root
from engine.protocol.errors import ConfigurationError
from engine.protocol.models import SystemConfig
MODULE_NAME = 'dashboard.runtime'
STARTUP_EXIT_CODE = 0
STARTUP_ERROR_EXIT_CODE = 1
CONFIG_RELATIVE_PATH = Path('config') / 'system.json'


def _resolve_project_root() -> Path:
    return Path(__file__).resolve().parent


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
    from engine.core.lifecycle import ensure_runtime_paths_aligned
    config = ensure_runtime_paths_aligned(bootstrap_paths, config, config_path=resolved_config_path)
    validate_config_root_path(config, bootstrap_paths)
    paths = build_system_paths(config, runtime_root=bootstrap_paths.root)
    validate_root_path(paths)
    paths.ensure_directories()
    system_logger = setup_system_logger(paths, level=config.logging.level, format_name=config.logging.format)
    log_event(system_logger, level='INFO', module=MODULE_NAME, message='dashboard startup complete')
    return DashboardRuntime(paths=paths, config=config)


def request_dashboard_shutdown(runtime: DashboardRuntime) -> None:
    runtime.shutdown_requested = True


def refresh_dashboard(runtime: DashboardRuntime, *, timestamp_utc: str | None=None, output: Callable[[str], None] | None=None, clear: bool=False) -> str:
    snapshot = load_dashboard_snapshot(runtime.config, runtime.paths, timestamp_utc=timestamp_utc)
    return render_dashboard(snapshot, output=output, clear=clear)


def _resolve_lan_ip() -> str | None:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(('8.8.8.8', 80))
            return sock.getsockname()[0]
    except OSError:
        return None


def _print_dashboard_urls(*, web_host: str, web_port: int, bind_lan: bool) -> None:
    local_url = f'http://127.0.0.1:{web_port}/'
    print(f'SYSTEM web dashboard (PC): {local_url}', flush=True)
    if bind_lan:
        lan_ip = _resolve_lan_ip()
        if lan_ip:
            print(f'SYSTEM web dashboard (telefons, tas pats WiFi): http://{lan_ip}:{web_port}/', flush=True)
        else:
            print('SYSTEM web dashboard (telefons): neizdevas noteikt LAN IP — izmanto ipconfig', flush=True)
    if web_host not in {'127.0.0.1', '0.0.0.0'}:
        print(f'SYSTEM web dashboard (bind): http://{web_host}:{web_port}/', flush=True)


def run_dashboard_main(*, root_path: str | Path | None=None, config_path: str | Path | None=None, wait_for_shutdown: Callable[[DashboardRuntime], None] | None=None, sleep_fn: Callable[[float], None]=time.sleep, output: Callable[[str], None] | None=None, clear: bool=False, enable_web: bool=False, web_host: str='127.0.0.1', web_port: int=DEFAULT_PORT, open_browser: bool=False, bind_lan: bool=False) -> int:
    try:
        runtime = startup_dashboard(root_path=root_path, config_path=config_path)
    except ConfigurationError as exc:
        print(f'dashboard startup failed: {exc.message}', file=sys.stderr)
        return STARTUP_ERROR_EXIT_CODE

    resolved_output = output if output is not None else live_console_printer
    resolved_clear = clear if output is not None else False

    def _handle_shutdown_signal(_signum: int, _frame: object | None) -> None:
        request_dashboard_shutdown(runtime)
    signal.signal(signal.SIGINT, _handle_shutdown_signal)
    signal.signal(signal.SIGTERM, _handle_shutdown_signal)

    server = None
    if enable_web:
        def _provider():
            return load_dashboard_snapshot(runtime.config, runtime.paths)
        bind_host = '0.0.0.0' if bind_lan else web_host
        try:
            server = start_dashboard_server(provider=_provider, host=bind_host, port=web_port)
        except OSError as exc:
            print(f'dashboard web bind failed on {bind_host}:{web_port}: {exc}', file=sys.stderr)
            return STARTUP_ERROR_EXIT_CODE
        _print_dashboard_urls(web_host=bind_host, web_port=web_port, bind_lan=bind_lan)
        if open_browser:
            try:
                webbrowser.open(f'http://127.0.0.1:{web_port}/')
            except Exception:
                pass

    refresh_dashboard(runtime, output=resolved_output, clear=resolved_clear)
    if wait_for_shutdown is not None:
        wait_for_shutdown(runtime)
        if server is not None:
            server.shutdown()
        return STARTUP_EXIT_CODE
    interval_seconds = runtime.config.dashboard.refresh_interval_ms / 1000.0
    while not runtime.shutdown_requested:
        sleep_fn(interval_seconds)
        if runtime.shutdown_requested:
            break
        refresh_dashboard(runtime, output=resolved_output, clear=resolved_clear)
    if server is not None:
        server.shutdown()
    return STARTUP_EXIT_CODE


def _parse_args(argv: list[str] | None=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='SYSTEM live command-center dashboard')
    parser.add_argument('--web', action='store_true', help='serve HTML dashboard on localhost')
    parser.add_argument('--port', type=int, default=DEFAULT_PORT, help=f'web port (default {DEFAULT_PORT})')
    parser.add_argument('--host', default='127.0.0.1', help='web bind host')
    parser.add_argument('--open-browser', action='store_true', help='open default browser to the web dashboard')
    parser.add_argument('--bind-lan', action='store_true', help='listen on all interfaces so phone on same WiFi can connect')
    parser.add_argument('--no-clear', action='store_true', help='do not clear console between refreshes')
    return parser.parse_args(argv)


def main(argv: list[str] | None=None) -> int:
    args = _parse_args(argv)
    project_root = _resolve_project_root()
    config_path = project_root / CONFIG_RELATIVE_PATH
    if not config_path.is_file():
        print(f'dashboard startup failed: config file not found at {config_path}', file=sys.stderr)
        return STARTUP_ERROR_EXIT_CODE
    prepare_deployment_root(project_root)
    output = print if args.no_clear else live_console_printer
    return run_dashboard_main(root_path=project_root, config_path=config_path, output=output, enable_web=args.web or args.open_browser or args.bind_lan, web_host=args.host, web_port=args.port, open_browser=args.open_browser, bind_lan=args.bind_lan)


if __name__ == '__main__':
    sys.exit(main())
