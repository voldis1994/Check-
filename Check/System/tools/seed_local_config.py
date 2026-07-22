"""Seed config/local/system.json — always force AUTO symbol + AUTO multi-account."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def apply_auto_defaults(data: dict, root: Path) -> dict:
    data.setdefault("paths", {})["root"] = str(root)
    data.setdefault("instrument", {})["symbol"] = "AUTO"
    # Empty list = trust every MT4 account (multi-account AUTO).
    data.setdefault("account", {})["allowed_account_numbers"] = []
    data["account"]["allowed_account_numbers"] = []
    data.setdefault("position_sizing", {}).update(
        {
            "mode": "fixed_lot",
            "fixed_lot": float(data.get("position_sizing", {}).get("fixed_lot", 0.01) or 0.01),
            "allow_broker_lot_normalization": False,
        }
    )
    data.setdefault("execution", {}).update(
        {
            "maximum_status_age_ms": 4000,
            "maximum_market_age_ms": 3500,
        }
    )
    data.setdefault("runtime", {})
    if data["runtime"].get("instance_id") in {None, "", "EURUSD_M1_PRIMARY"}:
        data["runtime"]["instance_id"] = "PRIMARY"
    data["runtime"]["trading_enabled"] = True
    return data


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True, help="Check/System absolute root")
    parser.add_argument("--config", type=Path, default=None)
    args = parser.parse_args()
    root = args.root.resolve()
    config_path = args.config or (root / "config" / "local" / "system.json")
    example = root / "config" / "system.example.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    if config_path.exists():
        data = json.loads(config_path.read_text(encoding="utf-8"))
    elif example.exists():
        data = json.loads(example.read_text(encoding="utf-8"))
    else:
        from checktrader.config.defaults import default_system_dict

        data = default_system_dict()
    data = apply_auto_defaults(data, root)
    config_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {config_path}")
    print(f"  paths.root={root}")
    print("  instrument.symbol=AUTO")
    print("  account.allowed_account_numbers=[]  (AUTO multi-account)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
