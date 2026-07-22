"""Seed config/local/system.json with this machine's System root + AUTO symbol."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


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
    data.setdefault("paths", {})["root"] = str(root)
    data.setdefault("instrument", {})["symbol"] = "AUTO"
    data.setdefault("position_sizing", {}).update(
        {
            "mode": "fixed_lot",
            "fixed_lot": 0.01,
            "allow_broker_lot_normalization": False,
        }
    )
    if "runtime" in data and "instance_id" in data["runtime"]:
        # Keep existing instance_id unless still the old EURUSD default
        if data["runtime"]["instance_id"] in {"EURUSD_M1_PRIMARY", ""}:
            data["runtime"]["instance_id"] = "PRIMARY"
    config_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {config_path}")
    print(f"  paths.root={root}")
    print("  instrument.symbol=AUTO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
