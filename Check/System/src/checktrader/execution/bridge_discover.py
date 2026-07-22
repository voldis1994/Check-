"""Discover MT4 file-bridge directories written by CHECK_SYSTEM_V2 EA."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class BridgeLocation:
    bridge_root: Path  # .../runtime/bridge
    source: str


def _snapshot_score(bridge: Path) -> tuple[int, float]:
    """Prefer locations that already have market+status JSON; then newest mtime."""
    market = bridge / "market"
    status = bridge / "status"
    market_files = list(market.glob("*.json")) if market.exists() else []
    status_files = list(status.glob("*.json")) if status.exists() else []
    count = (1 if market_files else 0) + (1 if status_files else 0)
    newest = 0.0
    for path in market_files + status_files:
        try:
            newest = max(newest, path.stat().st_mtime)
        except OSError:
            continue
    return count, newest


def bridge_has_snapshots(bridge: Path) -> bool:
    return _snapshot_score(bridge)[0] >= 2


def discover_mt4_bridges() -> list[BridgeLocation]:
    """Find CHECK_SYSTEM bridge folders under MetaQuotes Terminal data dirs."""
    appdata = os.environ.get("APPDATA", "")
    if not appdata:
        return []
    terminal_root = Path(appdata) / "MetaQuotes" / "Terminal"
    if not terminal_root.is_dir():
        return []
    found: list[BridgeLocation] = []
    for terminal in terminal_root.iterdir():
        if not terminal.is_dir():
            continue
        auto_root = terminal / "MQL4" / "Files" / "CHECK_SYSTEM"
        auto = auto_root / "runtime" / "bridge"
        if auto_root.exists() or auto.exists():
            found.append(BridgeLocation(auto, f"mt4-files:{terminal.name}"))
        for bridge in terminal.glob("**/CHECK_SYSTEM/runtime/bridge"):
            loc = BridgeLocation(bridge, f"mt4-scan:{terminal.name}")
            if all(loc.bridge_root != existing.bridge_root for existing in found):
                found.append(loc)
    return found


def list_active_bridges(*, configured_bridge: Path) -> list[BridgeLocation]:
    """
    Every bridge that currently has market+status snapshots.

    Multi-account AUTO: each MT4 terminal with CHECK_SYSTEM_V2 attached shows up
    here and is traded in the same START_LIVE process.
    """
    configured_bridge.mkdir(parents=True, exist_ok=True)
    candidates = [BridgeLocation(configured_bridge, "config")] + discover_mt4_bridges()
    seen: set[Path] = set()
    active: list[BridgeLocation] = []
    for loc in candidates:
        try:
            key = loc.bridge_root.resolve()
        except OSError:
            key = loc.bridge_root
        if key in seen:
            continue
        seen.add(key)
        loc.bridge_root.mkdir(parents=True, exist_ok=True)
        (loc.bridge_root / "market").mkdir(parents=True, exist_ok=True)
        (loc.bridge_root / "status").mkdir(parents=True, exist_ok=True)
        (loc.bridge_root / "commands").mkdir(parents=True, exist_ok=True)
        (loc.bridge_root / "acknowledgements").mkdir(parents=True, exist_ok=True)
        if bridge_has_snapshots(loc.bridge_root):
            active.append(loc)
    # Freshest first (stable ordering for logs)
    active.sort(key=lambda item: _snapshot_score(item.bridge_root), reverse=True)
    return active


def resolve_bridge_directory(*, configured_bridge: Path) -> BridgeLocation:
    """
    Prefer configured System runtime/bridge when it has snapshots;
    otherwise use the freshest MT4 Files/CHECK_SYSTEM bridge.
    """
    active = list_active_bridges(configured_bridge=configured_bridge)
    if active:
        return active[0]
    configured_bridge.mkdir(parents=True, exist_ok=True)
    return BridgeLocation(configured_bridge, "config")


def stick_or_resolve_bridge(
    *,
    configured_bridge: Path,
    locked: BridgeLocation | None,
    missing_cycles: int,
    unlock_after_missing: int = 40,
) -> tuple[BridgeLocation, int, bool]:
    """Legacy single-bridge helper (tests / tools). Prefer list_active_bridges for live."""
    if locked is not None:
        if bridge_has_snapshots(locked.bridge_root):
            return locked, 0, False
        missing = missing_cycles + 1
        if missing < unlock_after_missing:
            return locked, missing, False

    loc = resolve_bridge_directory(configured_bridge=configured_bridge)
    return loc, 0, True


def bridge_wait_hint(configured_bridge: Path) -> str:
    lines = [
        f"waiting for market/status under: {configured_bridge}",
        "Checklist:",
        "  1) EA CHECK_SYSTEM_V2 on each account M1 chart",
        "  2) AutoTrading ON + Allow live trading + Allow DLL imports",
        "  3) BridgeRootPath empty (AUTO) on every EA",
        "  4) MetaEditor F7 compile succeeded (0 errors)",
        "  5) Experts: CHECK_SYSTEM_V2 initialized ... bridge=...",
        "  6) Multi-account: one START_LIVE trades ALL discovered MT4 bridges",
    ]
    discovered = discover_mt4_bridges()
    if discovered:
        lines.append("Discovered MT4 bridge candidates:")
        for loc in discovered[:8]:
            score = _snapshot_score(loc.bridge_root)
            lines.append(f"  - {loc.bridge_root} files_score={score}")
    else:
        lines.append("No MT4 CHECK_SYSTEM bridge found under %APPDATA%\\MetaQuotes\\Terminal yet.")
    return " | ".join(lines[:2]) + "\n" + "\n".join(lines[2:])
