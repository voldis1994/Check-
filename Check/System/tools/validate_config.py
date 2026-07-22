#!/usr/bin/env python3
"""Validate SYSTEM v2 config file."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from checktrader.application.account_resolve import is_auto_account_list
from checktrader.config.loader import load_system_config
from checktrader.domain.errors import ConfigurationError


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate config/local/system.json")
    parser.add_argument("--config", type=Path, default=Path("config/local/system.json"))
    parser.add_argument(
        "--allow-empty-accounts",
        action="store_true",
        help="Deprecated: empty/AUTO allow-list is always accepted (trusts MT4)",
    )
    args = parser.parse_args()
    try:
        config = load_system_config(args.config, require_live_accounts=False)
    except ConfigurationError as exc:
        print(f"FAIL: {exc}")
        return 1
    except Exception as exc:  # noqa: BLE001 — CLI surface
        print(f"FAIL: {exc}")
        return 1
    accounts = config.account.allowed_account_numbers
    print(f"OK version={config.version} instance={config.runtime.instance_id}")
    print(f"  symbol={config.instrument.symbol} magic={config.position.magic_number}")
    print(
        f"  sizing={config.position_sizing.mode} lot={config.position_sizing.fixed_lot} "
        f"accounts={accounts or ['AUTO(from MT4)']}"
    )
    print(f"  bridge={config.paths.bridge} state={config.paths.state}")
    if is_auto_account_list(accounts):
        print("INFO: account allow-list is AUTO — engine trusts MT4 status account_number")
    return 0


if __name__ == "__main__":
    sys.exit(main())
