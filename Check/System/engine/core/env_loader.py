from __future__ import annotations
from pathlib import Path

def load_dotenv_file(path: Path) -> int:
    if not path.is_file():
        return 0
    loaded = 0
    for raw_line in path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if not key:
            continue
        import os
        if key not in os.environ or not os.environ.get(key):
            os.environ[key] = value
            loaded += 1
    return loaded
