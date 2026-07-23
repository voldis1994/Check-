"""CHECK SYSTEM frozen / desktop entry point.

Used by START_DASHBOARD.bat and by PyInstaller → dist/CHECK_SYSTEM.exe
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _bootstrap() -> Path:
    """Resolve System root whether running from source or frozen exe."""
    if getattr(sys, "frozen", False):
        # One-folder or one-file: exe next to System tree or inside _internal.
        here = Path(sys.executable).resolve().parent
        for candidate in (here, here.parent, here / "System", here.parent / "System"):
            if (candidate / "config").is_dir() or (candidate / "tools").is_dir():
                return candidate
        return here
    return Path(__file__).resolve().parents[1]


def main() -> int:
    root = _bootstrap()
    os.chdir(root)
    src = root / "src"
    tools = root / "tools"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
    if str(tools) not in sys.path:
        sys.path.insert(0, str(tools))

    cfg = root / "config" / "system.json"
    example = root / "config" / "system.example.json"
    if not cfg.exists() and example.exists():
        cfg.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")

    try:
        from checktrader.config.migrate import sync_system_json

        if cfg.exists() and example.exists():
            sync_system_json(cfg, example)
    except Exception:  # noqa: BLE001
        pass

    import dashboard

    dashboard.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
