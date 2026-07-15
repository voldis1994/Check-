#!/usr/bin/env python3
"""Diagnose why live cycles print SKIP (same gates as run_live cycle).

Usage (Windows):
  cd C:\\Check\\System
  PARBAUDI.bat
  .venv\\Scripts\\python.exe tools\\diagnose_skip.py
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine.core.clock import format_utc_timestamp, now_utc
from engine.core.config import load_system_config
from engine.core.instance import Instance
from engine.core.lifecycle import build_system_paths, discover_instances
from engine.core.monitoring import compute_data_freshness_ms, is_data_stale
from engine.core.mt4_bridge import common_files_bridge_root, mirror_common_bridge_to_deployment
from engine.core.paths import SystemPaths
from engine.loader.market_loader import load_market_data
from engine.loader.sensor_loader import load_sensor_data
from engine.loader.status_loader import load_status_data
from engine.loader.universe_loader import load_universe_data
from engine.normalizer.market_normalizer import normalize_market_csv
from engine.protocol.errors import DataIOError, SystemError
from engine.protocol.parser import parse_sensor_csv
from engine.validator.market_validator import validate_market_csv
from engine.validator.sensor_validator import validate_sensor_csv
from engine.validator.status_validator import validate_status_json
from engine.validator.universe_validator import validate_universe_json


def _age_ms(path: Path, now_epoch: float) -> int | None:
    if not path.is_file():
        return None
    return max(0, int((now_epoch - path.stat().st_mtime) * 1000))


def _fmt_age(age_ms: int | None) -> str:
    if age_ms is None:
        return 'MISSING'
    if age_ms < 1000:
        return f'{age_ms}ms'
    return f'{age_ms / 1000:.1f}s'


def diagnose_instance(paths: SystemPaths, instance: Instance, *, threshold_ms: int) -> tuple[list[str], str | None]:
    lines: list[str] = []
    now_epoch = time.time()
    account_dir = paths.account_dir(instance.account_id)
    market_path = account_dir / instance.market_filename()
    sensor_path = account_dir / instance.sensor_filename()
    status_path = account_dir / instance.status_filename()
    universe_path = account_dir / 'universe.json'
    global_universe = paths.universe_file

    lines.append(f'=== INSTANCE {instance.account_id} {instance.symbol} magic={instance.magic} ===')
    lines.append(f'account_dir: {account_dir}')
    lines.append(f'market : {"OK" if market_path.is_file() else "MISSING"}  age={_fmt_age(_age_ms(market_path, now_epoch))}  {market_path.name}')
    lines.append(f'sensor : {"OK" if sensor_path.is_file() else "MISSING"}  age={_fmt_age(_age_ms(sensor_path, now_epoch))}  {sensor_path.name}')
    lines.append(f'status : {"OK" if status_path.is_file() else "MISSING"}  age={_fmt_age(_age_ms(status_path, now_epoch))}  {status_path.name}')
    lines.append(f'universe account: {"OK" if universe_path.is_file() else "MISSING"}  global: {"OK" if global_universe.is_file() else "MISSING"}')
    lines.append(f'stale_threshold: {threshold_ms}ms ({threshold_ms / 1000:.0f}s)')

    skip_reason: str | None = None
    try:
        market_raw = load_market_data(paths, instance)
        market_validation = validate_market_csv(market_raw.raw_text)
        if not market_validation.is_valid:
            skip_reason = f'market_invalid:{";".join(market_validation.errors[:2])}'
        else:
            market_bars = normalize_market_csv(market_raw.raw_text)
            sensor_raw = load_sensor_data(paths, instance)
            sensor_validation = validate_sensor_csv(sensor_raw.raw_text)
            if not sensor_validation.is_valid:
                skip_reason = f'sensor_invalid:{";".join(sensor_validation.errors[:2])}'
            else:
                readings = parse_sensor_csv(sensor_raw.raw_text)
                if not readings:
                    skip_reason = 'sensor_invalid:no readings'
                else:
                    resolved_timestamp = now_utc()
                    market_freshness_ms = compute_data_freshness_ms(market_raw.modified_utc, resolved_timestamp)
                    sensor_freshness_ms = compute_data_freshness_ms(sensor_raw.modified_utc, resolved_timestamp)
                    bar_freshness_ms = compute_data_freshness_ms(format_utc_timestamp(market_bars[-1].time_utc), resolved_timestamp)
                    lines.append(
                        f'freshness: market_file={market_freshness_ms}ms '
                        f'sensor_file={sensor_freshness_ms}ms last_bar={bar_freshness_ms}ms'
                    )
                    if is_data_stale(market_freshness_ms, threshold_ms) or is_data_stale(sensor_freshness_ms, threshold_ms):
                        skip_reason = (
                            f'stale_data:market_file={market_freshness_ms}ms '
                            f'sensor_file={sensor_freshness_ms}ms bar={bar_freshness_ms}ms '
                            f'threshold={threshold_ms}ms'
                        )
                    else:
                        use_global = global_universe.is_file()
                        universe_raw = load_universe_data(paths, instance.account_id, use_global_universe=use_global)
                        universe_validation = validate_universe_json(universe_raw.raw_text)
                        if not universe_validation.is_valid:
                            skip_reason = f'universe_invalid:{";".join(universe_validation.errors[:2])}'
                        else:
                            status_raw = load_status_data(paths, instance.account_id)
                            status_validation = validate_status_json(status_raw.raw_text)
                            if not status_validation.is_valid or status_validation.record is None:
                                skip_reason = f'status_invalid:{";".join(status_validation.errors[:2])}'
                            else:
                                status = status_validation.record
                                lines.append(f'status: connected={status.connected} trade_allowed={status.trade_allowed}')
    except DataIOError as exc:
        skip_reason = f'load_failed:{exc}'
    except SystemError as exc:
        skip_reason = f'load_failed:{exc.message}'
    except OSError as exc:
        skip_reason = f'load_failed:{exc}'

    lines.append('')
    if skip_reason:
        lines.append(f'VERDICT: SKIP  reason={skip_reason}')
        lines.append('This is why PALAID shows SKIP decision=-')
        if skip_reason.startswith('stale_data'):
            lines.append('-> EA not writing fresh files. AutoTrading ON + Allow DLL + SystemRootPath.')
        elif skip_reason.startswith('sensor_'):
            lines.append('-> Missing/bad sensor_*.csv (EA export).')
        elif skip_reason.startswith('market_'):
            lines.append('-> Missing/bad market_*.csv (EA export).')
        elif skip_reason.startswith('status_'):
            lines.append('-> status_*.json missing/bad — EA status export.')
        elif skip_reason.startswith('universe_'):
            lines.append('-> universe.json bad.')
        elif skip_reason.startswith('load_failed'):
            lines.append('-> File load failed (path/permissions).')
    else:
        lines.append('VERDICT: DATA OK — cycle should NOT be empty SKIP')
        lines.append('If PALAID still prints empty SKIP, restart Python with latest main.')
    return lines, skip_reason


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Diagnose live SKIP cycles')
    parser.add_argument('--root', type=Path, default=None)
    args = parser.parse_args(argv)
    root = (args.root or Path(__file__).resolve().parents[1]).resolve()
    config_path = root / 'config' / 'system.json'
    if not config_path.is_file():
        print(f'missing config: {config_path}')
        return 1

    paths_boot = SystemPaths(root)
    config = load_system_config(config_path, system_paths=paths_boot)
    paths = build_system_paths(config, runtime_root=root)
    copied = mirror_common_bridge_to_deployment(paths)
    bridge = common_files_bridge_root()

    print('=== SKIP DIAGNOSE ===')
    print(f'root: {paths.root}')
    print(f'time: {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")} UTC')
    print(f'common bridge: {bridge} ({("exists" if bridge is not None and bridge.is_dir() else "none")})')
    if copied:
        print(f'mirrored from Common\\Files\\CheckSystem: {len(copied)} file(s)')
    print()

    instances = discover_instances(config, paths)
    if not instances:
        print('VERDICT: SKIP  reason=no_instances')
        return 2

    exit_code = 0
    for instance in instances:
        lines, skip_reason = diagnose_instance(paths, instance, threshold_ms=config.runtime.data_stale_threshold_ms)
        print('\n'.join(lines))
        print()
        if skip_reason:
            exit_code = 2
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
