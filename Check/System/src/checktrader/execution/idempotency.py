from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta


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
