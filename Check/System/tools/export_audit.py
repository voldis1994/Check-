#!/usr/bin/env python3
"""Export recent audit / log lines for offline review."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from checktrader.observability.audit import collect_audit_records


def main() -> int:
    parser = argparse.ArgumentParser(description="Export audit/log records to JSONL")
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--logs", type=Path, default=None, help="Override logs directory")
    parser.add_argument("--out", type=Path, default=Path("runtime/logs/audit_export.jsonl"))
    parser.add_argument("--limit", type=int, default=5000)
    args = parser.parse_args()
    root = args.root.resolve()
    logs_dir = args.logs or (root / "runtime" / "logs")
    records = collect_audit_records(logs_dir, limit=args.limit)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as handle:
        for row in records:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"Wrote {len(records)} records to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
