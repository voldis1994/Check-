from __future__ import annotations
import json
from pathlib import Path
from checktrader.domain.models import CycleAudit
class AuditWriter:
    def __init__(self, path: Path) -> None: self.path=path
    def write(self, audit: CycleAudit) -> None:
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.path.open('a',encoding='utf-8') as h: h.write(json.dumps(audit.to_dict(),sort_keys=True)+'\n')
