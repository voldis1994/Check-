"""Audit trail helpers."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def audit_event(event: str, **fields: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ts_utc": datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
        "event": event,
    }
    payload.update(fields)
    return payload


def append_audit_line(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def collect_audit_records(logs_dir: Path, *, limit: int = 5000) -> list[dict[str, Any]]:
    """Collect JSONL audit-like lines and structured log snippets from runtime/logs."""
    if not logs_dir.is_dir():
        return []
    records: list[dict[str, Any]] = []
    files = sorted(logs_dir.glob("*"), key=lambda p: p.stat().st_mtime)
    for path in files:
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".jsonl", ".log", ".json", ".txt"}:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith("{"):
                try:
                    row = json.loads(line)
                    if isinstance(row, dict):
                        row.setdefault("_source", path.name)
                        records.append(row)
                        continue
                except json.JSONDecodeError:
                    pass
            records.append({"_source": path.name, "line": line})
    if limit > 0 and len(records) > limit:
        return records[-limit:]
    return records


__all__ = ["audit_event", "append_audit_line", "collect_audit_records"]
