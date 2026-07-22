from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

SUBDIRS = ("market", "status", "commands", "acknowledgements", "archive")


def resolve_bridge(path: Path) -> Path:
    if (path / "runtime" / "bridge").is_dir():
        return path / "runtime" / "bridge"
    return path


def load_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def newest_json(directory: Path) -> dict[str, Any] | None:
    files = sorted(directory.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return None
    data = load_json(files[0])
    return {
        "file": str(files[0]),
        "mtime": files[0].stat().st_mtime,
        "protocol_version": data.get("protocol_version") if data else None,
        "message_type": data.get("message_type") if data else None,
        "message_id": data.get("message_id") if data else None,
        "generated_at_utc": data.get("generated_at_utc") if data else None,
    }


def inspect(bridge: Path) -> dict[str, Any]:
    bridge = resolve_bridge(bridge)
    result: dict[str, Any] = {"bridge": str(bridge), "exists": bridge.exists(), "subdirs": {}}
    for name in SUBDIRS:
        directory = bridge / name
        files = list(directory.glob("*.json")) if directory.is_dir() else []
        result["subdirs"][name] = {
            "exists": directory.is_dir(),
            "json_count": len(files),
            "latest": newest_json(directory) if directory.is_dir() else None,
        }
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect a CHECK SYSTEM v3 MT4 bridge directory.")
    parser.add_argument("--bridge", default="runtime/bridge", help="Path to bridge directory or bridge root.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    print(json.dumps(inspect(Path(args.bridge)), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
