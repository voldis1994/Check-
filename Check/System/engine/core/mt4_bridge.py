"""Mirror MT4 Common\\Files\\CheckSystem exports into the deployment root.

SYSTEM_EA writes either to C:\\Check\\System via DLL, or — when DLL is blocked —
to %APPDATA%\\MetaQuotes\\Terminal\\Common\\Files\\CheckSystem\\...
Python prefers the deployment root paths, so mirror keeps them in sync.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from engine.core.paths import SystemPaths

COMMON_BRIDGE_PREFIX = 'CheckSystem'


def common_files_bridge_root() -> Path | None:
    appdata = os.environ.get('APPDATA')
    if not appdata:
        return None
    root = Path(appdata) / 'MetaQuotes' / 'Terminal' / 'Common' / 'Files' / COMMON_BRIDGE_PREFIX
    return root if root.is_dir() else root


def mirror_common_bridge_to_deployment(paths: SystemPaths) -> list[str]:
    """Copy newer files from Common\\Files\\CheckSystem into deployment root.

    Returns relative paths that were copied/updated.
    """
    bridge = common_files_bridge_root()
    if bridge is None or not bridge.is_dir():
        return []

    copied: list[str] = []
    for src in bridge.rglob('*'):
        if not src.is_file():
            continue
        if src.name.endswith('.tmp'):
            continue
        rel = src.relative_to(bridge)
        dest = paths.root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            try:
                if dest.stat().st_mtime_ns >= src.stat().st_mtime_ns and dest.stat().st_size == src.stat().st_size:
                    continue
            except OSError:
                pass
        shutil.copy2(src, dest)
        copied.append(str(rel).replace('\\', '/'))
    return copied
