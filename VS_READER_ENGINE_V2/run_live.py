#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

from engine.core.lifecycle import parse_market_filename, run_live_main
from engine.core.paths import SystemPaths

CONFIG_RELATIVE_PATH = Path("config") / "system.json"


def _resolve_project_root() -> Path:
    return Path(__file__).resolve().parent


def _sync_config_root_path(config_path: Path, project_root: Path) -> None:
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    system = payload.get("system")
    if not isinstance(system, dict):
        return

    desired_root = str(project_root.resolve())
    current_root = str(Path(str(system.get("root_path", ""))).expanduser().resolve())
    if current_root == desired_root:
        return

    system["root_path"] = desired_root
    config_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        f"Updated config system.root_path -> {desired_root}",
        file=sys.stderr,
    )


def _sync_config_instances_from_clients(config_path: Path, project_root: Path) -> None:
    clients_dir = project_root / "data" / "clients"
    if not clients_dir.is_dir():
        return

    account_dirs = sorted(entry for entry in clients_dir.iterdir() if entry.is_dir())
    if not account_dirs:
        return

    payload = json.loads(config_path.read_text(encoding="utf-8"))
    instances = payload.get("instances")
    if not isinstance(instances, list) or not instances:
        return

    primary_account = account_dirs[0].name
    discovered_symbol: str | None = None
    discovered_magic: int | None = None
    for entry in account_dirs[0].iterdir():
        if not entry.is_file():
            continue
        parsed = parse_market_filename(entry.name)
        if parsed is not None:
            discovered_symbol, discovered_magic = parsed
            break

    changed = False
    first = instances[0]
    if not isinstance(first, dict):
        return

    if len(account_dirs) == 1 and first.get("account_id") != primary_account:
        first["account_id"] = primary_account
        changed = True
    if discovered_symbol is not None and first.get("symbol") != discovered_symbol:
        first["symbol"] = discovered_symbol
        changed = True
    if discovered_magic is not None and first.get("magic") != discovered_magic:
        first["magic"] = discovered_magic
        changed = True

    if not changed:
        return

    config_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        "Updated config instances from MT4 data: "
        f"account_id={first.get('account_id')}, "
        f"symbol={first.get('symbol')}, magic={first.get('magic')}",
        file=sys.stderr,
    )


def _prepare_config(config_path: Path, project_root: Path) -> None:
    _sync_config_root_path(config_path, project_root)
    _sync_config_instances_from_clients(config_path, project_root)


def setup_only(project_root: Path | None = None) -> int:
    root = project_root or _resolve_project_root()
    config_path = root / CONFIG_RELATIVE_PATH
    if not config_path.is_file():
        print(f"setup failed: config file not found at {config_path}", file=sys.stderr)
        return 1

    _prepare_config(config_path, root)
    SystemPaths(root).ensure_directories()
    return 0


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "--setup-only":
        return setup_only()

    project_root = _resolve_project_root()
    config_path = project_root / CONFIG_RELATIVE_PATH
    if not config_path.is_file():
        print(
            f"startup failed: config file not found at {config_path}",
            file=sys.stderr,
        )
        return 1

    _prepare_config(config_path, project_root)
    return run_live_main(root_path=project_root, config_path=config_path)


if __name__ == "__main__":
    sys.exit(main())
