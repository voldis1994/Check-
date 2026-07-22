#!/usr/bin/env python3
"""Compare instance state to latest status snapshot positions."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from checktrader.config.loader import load_system_config
from checktrader.execution.reconciliation import reconcile_position_from_broker
from checktrader.market_data.status import parse_status_snapshot
from checktrader.state.store import load_instance_state


def _latest(directory: Path) -> Path | None:
    files = sorted(directory.glob("*.json"), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None


def main() -> int:
    parser = argparse.ArgumentParser(description="Reconcile managed state vs broker status")
    parser.add_argument("--config", type=Path, default=Path("config/local/system.json"))
    parser.add_argument("--allow-empty-accounts", action="store_true")
    args = parser.parse_args()
    config = load_system_config(args.config, require_live_accounts=not args.allow_empty_accounts)
    root = Path(config.paths.root).resolve()
    state = load_instance_state(root / config.paths.state / "instance.json")
    status_path = _latest(root / config.paths.bridge / "status")
    if status_path is None:
        print("FAIL: no status snapshot")
        return 1
    payload = json.loads(status_path.read_text(encoding="utf-8"))
    status = parse_status_snapshot(payload)
    magic = config.position.magic_number
    symbol = config.instrument.symbol
    broker = None
    for pos in status.positions:
        if pos.symbol == symbol and pos.magic == magic:
            broker = pos
            break
    managed, reason = reconcile_position_from_broker(state.position, broker)
    print(f"status_file={status_path.name} account={status.account_number}")
    print(f"managed_state={state.position.state.value} ticket={state.position.ticket}")
    print(f"broker_ticket={None if broker is None else broker.ticket} broker_sl={None if broker is None else broker.stop_loss}")
    print(f"reconcile_reason={reason.value} resulting_state={managed.state.value}")
    if status.account_number not in config.account.allowed_account_numbers:
        print(f"WARN: account {status.account_number} not in allow-list {config.account.allowed_account_numbers}")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
