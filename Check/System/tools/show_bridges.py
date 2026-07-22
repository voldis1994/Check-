"""Print every active MT4 CHECK_SYSTEM bridge + account (multi-account status)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from checktrader.config.loader import load_system_config
from checktrader.execution.bridge_discover import list_active_bridges
from checktrader.execution.snapshot_select import select_latest_snapshot


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("config/local/system.json"))
    args = parser.parse_args()
    config = load_system_config(args.config, require_live_accounts=False)
    root = Path(config.paths.root).resolve()
    configured = (root / config.paths.bridge).resolve()
    bridges = list_active_bridges(configured_bridge=configured)
    print(f"Active MT4 bridges: {len(bridges)}")
    if not bridges:
        print("  (none) — attach CHECK_SYSTEM_V2 on each account M1, DLL ON, AutoTrading ON")
        return 1
    for loc in bridges:
        status = select_latest_snapshot(loc.bridge_root / "status")
        market = select_latest_snapshot(loc.bridge_root / "market")
        account = "?"
        symbol = "?"
        if status is not None:
            account = str(status.payload.get("account_number", "?"))
        if market is not None:
            symbol = str(market.payload.get("symbol", "?"))
        print(f"  account={account} symbol={symbol} source={loc.source}")
        print(f"    path={loc.bridge_root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
