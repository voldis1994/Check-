#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine.deployment.path_contract import (
    format_path_contract_report,
    run_path_contract_validation,
    sync_deployment_paths,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Synchronize config/system.json and MQL4 SYSTEM_ROOT_PATH to one deployment root",
    )
    parser.add_argument(
        "--root",
        dest="root_path",
        default=None,
        help="Deployment root (directory containing run_live.py). Defaults to auto-detect.",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Validate path contract without writing files",
    )
    args = parser.parse_args(argv)

    if args.check_only:
        report = run_path_contract_validation(args.root_path)
        print(format_path_contract_report(report))
        return 0 if report.passed else 1

    root = sync_deployment_paths(args.root_path)
    report = run_path_contract_validation(root)
    print(f"Synchronized deployment root -> {root}")
    print(format_path_contract_report(report))
    print()
    print("MT4 EA reminder:")
    print(f'  Set input SystemRootPath = "{root}"')
    print("  Or leave empty if SYSTEM_RootConfig.mqh already matches (after recompile EA).")
    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main())
