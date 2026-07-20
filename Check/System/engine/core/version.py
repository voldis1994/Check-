from __future__ import annotations
from functools import lru_cache
from pathlib import Path

MODULE_NAME = 'core.version'
FALLBACK_SYSTEM_VERSION = '0.0.0'


@lru_cache(maxsize=1)
def read_system_version(root: str | Path | None = None) -> str:
    """Read Check/System/VERSION (release tag). Falls back if missing."""
    if root is None:
        candidate = Path(__file__).resolve().parents[2] / 'VERSION'
    else:
        candidate = Path(root).expanduser().resolve() / 'VERSION'
    try:
        text = candidate.read_text(encoding='utf-8').strip()
    except OSError:
        return FALLBACK_SYSTEM_VERSION
    return text or FALLBACK_SYSTEM_VERSION
