#!/usr/bin/env python3
"""Validate SYSTEM v2 config file."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from checktrader.config.loader import load_system_config
from checktrader.domain.errors import ConfigurationError


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate config/local/system.json")
    parser.add_argument("--config", type=Path, default=Path("config/local/system.json"))
    parser.add_argument(
        "--allow-empty-accounts",
        action="store_true",
        help="Allow empty allowed_account_numbers (dev/health soft check)",
    )
    args = parser.parse_args()
    try:
        config = load_system_config(args.config, require_live_accounts=not args.allow_empty_accounts)
    except ConfigurationError as exc:
        print(f"FAIL: {exc}")
        return 1
    except Exception as exc:  # noqa: BLE001 — CLI surface
        print(f"FAIL: {exc}")
        return 1
    accounts = config.account.allowed_account_numbers
    print(f"OK version={config.version} instance={config.runtime.instance_id}")
    print(f"  symbol={config.instrument.symbol} magic={config.position.magic_number}")
    print(f"  sizing={config.risk.sizing_mode} accounts={accounts or ['(empty)']}")
    print(f"  bridge={config.paths.bridge} state={config.paths.state}")
    if not accounts and not args.allow_empty_accounts:
        print("FAIL: allowed_account_numbers empty")
        return 1
    if not accounts:
        print("WARN: allowed_account_numbers empty (allowed by flag)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
