from __future__ import annotations
import json, logging
from datetime import UTC, datetime
from typing import Any
class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        p: dict[str,Any]={'timestamp':datetime.now(UTC).isoformat(),'level':record.levelname,'logger':record.name,'message':record.getMessage()}
        if isinstance(record.args,dict): p.update(record.args)
        if record.exc_info: p['exception']=self.formatException(record.exc_info)
        return json.dumps(p,sort_keys=True)
def configure_logging(level: str='INFO') -> None:
    h=logging.StreamHandler(); h.setFormatter(JsonFormatter()); root=logging.getLogger(); root.handlers.clear(); root.addHandler(h); root.setLevel(level.upper())
