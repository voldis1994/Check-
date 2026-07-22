"""Application bootstrap."""

from __future__ import annotations

from pathlib import Path

from checktrader.config.loader import load_system_config
from checktrader.config.models import SystemConfig
from checktrader.state.store import InstanceRuntimeState, load_instance_state


def ensure_runtime_dirs(root: Path) -> None:
    for rel in (
        "runtime/bridge/market",
        "runtime/bridge/status",
        "runtime/bridge/commands",
        "runtime/bridge/acknowledgements",
        "runtime/bridge/archive",
        "runtime/state",
        "runtime/logs",
    ):
        (root / rel).mkdir(parents=True, exist_ok=True)


def bootstrap(
    config_path: Path, *, require_live_accounts: bool = True
) -> tuple[SystemConfig, InstanceRuntimeState, Path]:
    config = load_system_config(config_path, require_live_accounts=require_live_accounts)
    root = Path(config.paths.root).resolve()
    ensure_runtime_dirs(root)
    state = load_instance_state(root / config.paths.state / "instance.json")
    return config, state, root
