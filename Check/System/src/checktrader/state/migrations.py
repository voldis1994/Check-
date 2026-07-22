from __future__ import annotations
from typing import Any
SCHEMA_VERSION=3
def migrate_state(data: dict[str, Any]) -> dict[str, Any]:
    if int(data.get('schema_version',SCHEMA_VERSION))>SCHEMA_VERSION: raise ValueError('state schema is newer than this application')
    data['schema_version']=SCHEMA_VERSION; data.setdefault('setups',[]); data.setdefault('positions',[]); data.setdefault('limits',{}); return data
