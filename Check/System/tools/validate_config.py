from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from checktrader.config.loader import load_config  # noqa: E402
from checktrader.config.validation import validate_live_ready  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate CHECK SYSTEM v3 configuration.")
    parser.add_argument("--config", default="config/system.example.json", help="Configuration JSON path.")
    parser.add_argument("--schema", default="config/system.schema.json", help="JSON Schema path.")
    parser.add_argument("--live", action="store_true", help="Require live-ready settings.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config_path = Path(args.config)
    schema_path = Path(args.schema)
    if not config_path.is_absolute():
        config_path = ROOT / config_path
    if not schema_path.is_absolute():
        schema_path = ROOT / schema_path

    try:
        config = load_config(config_path, schema_path if schema_path.exists() else None, validate_live=False)
        if args.live:
            validate_live_ready(config)
    except Exception as exc:  # noqa: BLE001 - CLI should print validation failures clearly.
        if args.json:
            print(json.dumps({"ok": False, "error": str(exc)}, indent=2, sort_keys=True))
        else:
            print(f"CONFIG INVALID: {exc}", file=sys.stderr)
        return 1

    result = {
        "ok": True,
        "config": str(config_path),
        "version": config.version,
        "protocol_version": config.protocol_version,
        "mode": config.runtime.mode,
        "trading_enabled": config.runtime.trading_enabled,
        "symbol": config.instrument.symbol,
    }
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(
            "CONFIG VALID "
            f"version={config.version} protocol={config.protocol_version} "
            f"mode={config.runtime.mode} symbol={config.instrument.symbol}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
