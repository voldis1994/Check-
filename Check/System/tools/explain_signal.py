from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def read_last_jsonl(path: Path) -> dict[str, Any]:
    last = ""
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            last = line
    if not last:
        raise ValueError(f"no audit entries found in {path}")
    data = json.loads(last)
    if not isinstance(data, dict):
        raise ValueError("last audit entry is not an object")
    return data


def value_name(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict) and "value" in value:
        return str(value["value"])
    return str(value)


def explain(entry: dict[str, Any]) -> dict[str, Any]:
    signal = entry.get("signal") if isinstance(entry.get("signal"), dict) else {}
    risk = entry.get("risk") if isinstance(entry.get("risk"), dict) else {}
    management = entry.get("management") if isinstance(entry.get("management"), dict) else {}
    reasons = entry.get("reasons") if isinstance(entry.get("reasons"), list) else []

    reason = (
        value_name(signal.get("reason"))
        or value_name(risk.get("reason"))
        or value_name(management.get("reason"))
        or (value_name(reasons[-1]) if reasons else "")
    )

    return {
        "cycle_id": entry.get("cycle_id"),
        "started_at": entry.get("started_at"),
        "completed_at": entry.get("completed_at"),
        "symbol": entry.get("symbol"),
        "regime": value_name(entry.get("regime")),
        "strategy": value_name(entry.get("strategy") or signal.get("strategy")),
        "decision_reason": reason,
        "side": value_name(signal.get("side")),
        "entry_price": signal.get("entry_price"),
        "stop_loss": signal.get("stop_loss"),
        "take_profit": signal.get("take_profit"),
        "risk_decision": value_name(risk.get("decision")),
        "management_decision": value_name(management.get("decision")),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Explain the latest CHECK SYSTEM v3 audit signal.")
    parser.add_argument("--audit", default="runtime/audit.jsonl", help="Audit JSONL path.")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        info = explain(read_last_jsonl(Path(args.audit)))
    except Exception as exc:  # noqa: BLE001 - CLI should be direct.
        print(f"Unable to explain audit: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(info, indent=2, sort_keys=True))
    else:
        print(f"cycle: {info['cycle_id']}")
        print(f"symbol: {info['symbol']}")
        print(f"regime: {info['regime']}")
        print(f"strategy: {info['strategy']}")
        print(f"reason: {info['decision_reason']}")
        if info["side"]:
            print(
                "signal: "
                f"{info['side']} entry={info['entry_price']} "
                f"stop={info['stop_loss']} take_profit={info['take_profit']}"
            )
        if info["risk_decision"]:
            print(f"risk: {info['risk_decision']}")
        if info["management_decision"]:
            print(f"management: {info['management_decision']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
