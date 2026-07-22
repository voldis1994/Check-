#!/usr/bin/env python3
"""Inspect MT4 bridge directories for freshness and basic shape."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path


def _age_sec(path: Path) -> float:
    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
    return (datetime.now(tz=UTC) - mtime).total_seconds()


def _latest(directory: Path) -> Path | None:
    if not directory.is_dir():
        return None
    files = sorted(directory.glob("*.json"), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect runtime/bridge heartbeat")
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--max-age-sec", type=float, default=5.0)
    args = parser.parse_args()
    root = args.root.resolve()
    bridge = root / "runtime" / "bridge"
    ok = True
    for name in ("market", "status", "commands", "acknowledgements"):
        directory = bridge / name
        latest = _latest(directory)
        if latest is None:
            print(f"MISSING {name}: no json under {directory}")
            if name in {"market", "status"}:
                ok = False
            continue
        age = _age_sec(latest)
        flag = "OK" if age <= args.max_age_sec or name in {"commands", "acknowledgements"} else "STALE"
        if flag == "STALE":
            ok = False
        summary = ""
        try:
            payload = json.loads(latest.read_text(encoding="utf-8"))
            summary = (
                f" type={payload.get('message_type')} seq={payload.get('sequence')}"
                f" at={payload.get('generated_at_utc')}"
            )
            if name == "status":
                summary += f" account={payload.get('account_number')}"
            if name == "market":
                summary += f" symbol={payload.get('symbol')}"
        except (OSError, json.JSONDecodeError) as exc:
            flag = "BAD_JSON"
            ok = False
            summary = f" error={exc}"
        print(f"{flag:8} {name}: {latest.name} age={age:.1f}s{summary}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
