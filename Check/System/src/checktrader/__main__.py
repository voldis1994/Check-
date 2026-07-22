"""CLI entrypoint: python -m checktrader"""

from __future__ import annotations

import argparse
from pathlib import Path

from checktrader.application.live_loop import run_trading_loop


def main() -> None:
    parser = argparse.ArgumentParser(prog="checktrader", description="SYSTEM v2 live trading bridge")
    parser.add_argument("--config", type=Path, default=Path("config/local/system.json"))
    parser.add_argument("--once", action="store_true", help="Run a single cycle and exit")
    parser.add_argument(
        "--allow-empty-accounts",
        action="store_true",
        help="Deprecated no-op: empty allow-list is AUTO multi-account (default)",
    )
    args = parser.parse_args()
    # Empty allowed_account_numbers is production AUTO (all MT4 accounts).
    run_trading_loop(config_path=args.config, once=args.once, require_live_accounts=False)


if __name__ == "__main__":
    main()
