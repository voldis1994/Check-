from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path


@dataclass(slots=True)
class CommandDedupe:
    window_seconds: float
    seen: dict[str, datetime] = field(default_factory=dict)

    def remember(self, command_id: str, now: datetime) -> bool:
        self.prune(now)
        if command_id in self.seen:
            return False
        self.seen[command_id] = now
        return True

    def prune(self, now: datetime) -> None:
        cutoff = now - timedelta(seconds=self.window_seconds)
        self.seen = {k: v for k, v in self.seen.items() if v >= cutoff}

    def save(self, path: Path) -> None:
        """Persist seen command ids to disk."""
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(
            json.dumps({k: v.isoformat() for k, v in self.seen.items()}, sort_keys=True),
            encoding="utf-8",
        )
        tmp.replace(path)

    @classmethod
    def load(cls, path: Path, window_seconds: float) -> CommandDedupe:
        """Load from disk if available, otherwise start fresh."""
        if not path.exists():
            return cls(window_seconds)
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            seen = {k: datetime.fromisoformat(v) for k, v in raw.items() if isinstance(v, str)}
        except (json.JSONDecodeError, ValueError, AttributeError):
            seen = {}
        return cls(window_seconds, seen)
