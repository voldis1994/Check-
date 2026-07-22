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


def resolve_bridge_directory(*, configured_bridge: Path) -> BridgeLocation:
    """
    Prefer configured System runtime/bridge when it has snapshots;
    otherwise use the freshest MT4 Files/CHECK_SYSTEM bridge.
    """
    configured_bridge.mkdir(parents=True, exist_ok=True)
    candidates = [BridgeLocation(configured_bridge, "config")] + discover_mt4_bridges()
    # Ensure directories exist for writing commands into chosen location later
    best = BridgeLocation(configured_bridge, "config")
    best_score = _snapshot_score(configured_bridge)
    for loc in candidates[1:]:
        loc.bridge_root.mkdir(parents=True, exist_ok=True)
        (loc.bridge_root / "market").mkdir(parents=True, exist_ok=True)
        (loc.bridge_root / "status").mkdir(parents=True, exist_ok=True)
        (loc.bridge_root / "commands").mkdir(parents=True, exist_ok=True)
        (loc.bridge_root / "acknowledgements").mkdir(parents=True, exist_ok=True)
        score = _snapshot_score(loc.bridge_root)
        if score > best_score:
            best = loc
            best_score = score
    return best


def bridge_wait_hint(configured_bridge: Path) -> str:
    lines = [
        f"waiting for market/status under: {configured_bridge}",
        "Checklist:",
        "  1) EA CHECK_SYSTEM_V2 attached to M1 chart",
        "  2) AutoTrading ON (toolbar) + Allow live trading + Allow DLL imports",
        "  3) BridgeRootPath empty (AUTO) OR set to Check\\System folder",
        "  4) MetaEditor F7 compile succeeded (0 errors)",
        "  5) Experts tab must show: CHECK_SYSTEM_V2 initialized ... bridge=...",
    ]
    discovered = discover_mt4_bridges()
    if discovered:
        lines.append("Discovered MT4 bridge candidates:")
        for loc in discovered[:5]:
            score = _snapshot_score(loc.bridge_root)
            lines.append(f"  - {loc.bridge_root} files_score={score}")
    else:
        lines.append("No MT4 CHECK_SYSTEM bridge found under %APPDATA%\\MetaQuotes\\Terminal yet.")
    return " | ".join(lines[:2]) + "\n" + "\n".join(lines[2:])
