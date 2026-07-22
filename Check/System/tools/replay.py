#!/usr/bin/env python3
"""Replay a single cycle from saved market + status JSON files."""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from checktrader.application.cycle import run_cycle
from checktrader.config.loader import load_system_config
from checktrader.market_data.loader import parse_market_snapshot
from checktrader.market_data.status import parse_status_snapshot
from checktrader.state.store import InstanceRuntimeState, load_instance_state


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay one decision cycle offline")
    parser.add_argument("--config", type=Path, default=Path("config/local/system.json"))
    parser.add_argument("--market", type=Path, required=True)
    parser.add_argument("--status", type=Path, required=True)
    parser.add_argument("--state", type=Path, default=None)
    parser.add_argument("--allow-empty-accounts", action="store_true")
    parser.add_argument("--kill-switch", action="store_true")
    args = parser.parse_args()
    config = load_system_config(args.config, require_live_accounts=not args.allow_empty_accounts)
    root = Path(config.paths.root).resolve()
    if args.state and args.state.exists():
        state = load_instance_state(args.state)
    else:
        state_path = root / config.paths.state / "instance.json"
        state = load_instance_state(state_path) if state_path.exists() else InstanceRuntimeState()
    market = parse_market_snapshot(json.loads(args.market.read_text(encoding="utf-8")))
    status = parse_status_snapshot(json.loads(args.status.read_text(encoding="utf-8")))
    now = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
    bridge = root / config.paths.bridge
    bridge.mkdir(parents=True, exist_ok=True)
    result = run_cycle(
        config=config,
        state=state,
        market=market,
        status=status,
        bridge_root=bridge,
        now_utc=now,
        kill_switch=args.kill_switch,
    )
    print(json.dumps({"reason": result.reason.value, "action": result.action.value}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
