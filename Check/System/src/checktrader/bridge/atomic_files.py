from __future__ import annotations
import json, os
from pathlib import Path
from typing import Any
from uuid import uuid4

def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True); tmp=path.with_name(f'.{path.name}.{uuid4().hex}.tmp')
    with tmp.open('w',encoding='utf-8') as h: json.dump(payload,h,separators=(',',':'),sort_keys=True); h.flush(); os.fsync(h.fileno())
    os.replace(tmp,path); fd=os.open(path.parent, os.O_RDONLY)
    try: os.fsync(fd)
    finally: os.close(fd)
def read_json(path: Path) -> dict[str, Any]|None:
    if not path.exists(): return None
    data=json.loads(path.read_text(encoding='utf-8')); return data if isinstance(data,dict) else None
