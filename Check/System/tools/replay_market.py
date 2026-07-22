from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_history(path: Path) -> dict[str, list[dict[str, Any]]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("history root must be an object")
    out: dict[str, list[dict[str, Any]]] = {}
    for timeframe, rows in data.items():
        if isinstance(rows, list):
            out[str(timeframe)] = [row for row in rows if isinstance(row, dict)]
    return out


def summarize(history: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for timeframe, rows in sorted(history.items()):
        first = rows[0].get("time") if rows else None
        last = rows[-1].get("time") if rows else None
        summary[timeframe] = {"bars": len(rows), "first": first, "last": last}
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Minimal CHECK SYSTEM v3 market-history replay stub.")
    parser.add_argument("--history", default="runtime/history/history.json", help="History JSON file.")
    parser.add_argument("--limit", type=int, default=0, help="Optional number of M1 bars to preview.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    history_path = Path(args.history)
    history = load_history(history_path)
    result: dict[str, Any] = {"history": str(history_path), "summary": summarize(history)}
    if args.limit > 0:
        result["preview_m1"] = history.get("M1", [])[: args.limit]
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
