"""Sync config/system.json trading profile from system.example.json."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from checktrader.config.migrate import sync_system_json  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(ROOT / "config" / "system.json"))
    parser.add_argument("--example", default=str(ROOT / "config" / "system.example.json"))
    args = parser.parse_args()
    changed = sync_system_json(args.config, example_path=args.example)
    if changed:
        print(f"Synced regimes/strategies into {args.config}")
    else:
        print(f"Already current: {args.config}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
