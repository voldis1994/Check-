from __future__ import annotations
import json
from dataclasses import dataclass, field
from pathlib import Path
@dataclass(slots=True)
class Metrics:
    counters: dict[str,int]=field(default_factory=dict)
    def inc(self, name: str, value: int=1) -> None: self.counters[name]=self.counters.get(name,0)+value
    def snapshot(self) -> dict[str,int]: return dict(self.counters)
    def save(self, path: Path) -> None: path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(self.snapshot(),indent=2,sort_keys=True),encoding='utf-8')
