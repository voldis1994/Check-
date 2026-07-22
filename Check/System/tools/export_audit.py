from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any


def read_audit(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        data = json.loads(line)
        if not isinstance(data, dict):
            raise ValueError(f"audit line {line_number} is not an object")
        rows.append(data)
    return rows


def value_name(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict) and "value" in value:
        return str(value["value"])
    return str(value)


def flatten(row: dict[str, Any]) -> dict[str, Any]:
    signal = row.get("signal") if isinstance(row.get("signal"), dict) else {}
    risk = row.get("risk") if isinstance(row.get("risk"), dict) else {}
    command = row.get("command") if isinstance(row.get("command"), dict) else {}
    management = row.get("management") if isinstance(row.get("management"), dict) else {}
    return {
        "cycle_id": row.get("cycle_id"),
        "started_at": row.get("started_at"),
        "completed_at": row.get("completed_at"),
        "symbol": row.get("symbol"),
        "regime": value_name(row.get("regime")),
        "strategy": value_name(row.get("strategy") or signal.get("strategy")),
        "signal_side": value_name(signal.get("side")),
        "signal_reason": value_name(signal.get("reason")),
        "entry_price": signal.get("entry_price"),
        "stop_loss": signal.get("stop_loss"),
        "take_profit": signal.get("take_profit"),
        "risk_decision": value_name(risk.get("decision")),
        "risk_reason": value_name(risk.get("reason")),
        "risk_lot": risk.get("lot"),
        "command_id": command.get("command_id"),
        "command_action": value_name(command.get("action")),
        "management_decision": value_name(management.get("decision")),
        "management_reason": value_name(management.get("reason")),
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    flat = [flatten(row) for row in rows]
    fieldnames = list(flat[0].keys()) if flat else list(flatten({}).keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(flat)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export CHECK SYSTEM v3 audit JSONL.")
    parser.add_argument("--audit", default="runtime/audit.jsonl", help="Audit JSONL path.")
    parser.add_argument("--out", required=True, help="Output file path.")
    parser.add_argument("--format", choices=("json", "csv"), default="json", help="Output format.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        rows = read_audit(Path(args.audit))
        out = Path(args.out)
        if args.format == "json":
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(rows, indent=2, sort_keys=True), encoding="utf-8")
        else:
            write_csv(out, rows)
    except Exception as exc:  # noqa: BLE001 - CLI should report export failures.
        print(f"Unable to export audit: {exc}", file=sys.stderr)
        return 1

    print(f"Exported {len(rows)} audit rows to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
