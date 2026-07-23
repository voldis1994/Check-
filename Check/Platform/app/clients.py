"""CHECK Platform v4 — per-client MT4 workspaces."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CLIENTS = ROOT / "clients"
REGISTRY = CLIENTS / "registry.json"


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _slug(text: str) -> str:
    s = re.sub(r"[^A-Za-z0-9_-]+", "_", text.strip()).strip("_")[:40]
    return s or "client"


def _reg() -> dict[str, Any]:
    if not REGISTRY.exists():
        return {"clients": []}
    try:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"clients": []}
    if not isinstance(data, dict):
        return {"clients": []}
    data.setdefault("clients", [])
    return data


def _save_reg(reg: dict[str, Any]) -> None:
    CLIENTS.mkdir(parents=True, exist_ok=True)
    reg["updated_at"] = _now()
    REGISTRY.write_text(json.dumps(reg, indent=2) + "\n", encoding="utf-8")


def list_clients() -> list[dict[str, Any]]:
    return [c for c in _reg().get("clients", []) if isinstance(c, dict)]


def client_path(cid: str) -> Path:
    return CLIENTS / cid


def bridge_path(cid: str) -> Path:
    """EA BridgePath points here (contains market/status/commands/acks)."""
    return client_path(cid) / "bridge"


def ensure_bridge(cid: str) -> Path:
    root = bridge_path(cid)
    for name in ("market", "status", "commands", "acks"):
        (root / name).mkdir(parents=True, exist_ok=True)
    return root


def read(cid: str) -> dict[str, Any] | None:
    path = client_path(cid) / "client.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def add(*, login: str, password: str, server: str, label: str = "", lot: float = 0.02, mt4_exe: str = "") -> dict[str, Any]:
    login = login.strip()
    server = server.strip()
    if not login or not server or not password:
        raise ValueError("login, password, server required")
    base = _slug(label or login)
    cid = base
    n = 2
    while client_path(cid).exists():
        cid = f"{base}_{n}"
        n += 1
    path = client_path(cid)
    path.mkdir(parents=True, exist_ok=False)
    bridge = ensure_bridge(cid)
    client = {
        "id": cid,
        "label": (label or login).strip(),
        "login": login,
        "password": password,
        "server": server,
        "lot": float(lot),
        "mt4_exe": mt4_exe,
        "bridge": str(bridge),
        "created_at": _now(),
    }
    (path / "client.json").write_text(json.dumps(client, indent=2) + "\n", encoding="utf-8")
    (path / "BRIDGE.txt").write_text(
        "MT4 setup (automatic path):\n"
        "1. LAUNCH MT4 from CHECK\n"
        "2. MetaEditor → open clients/<id>/CHECK.mq4 (copied here) → Compile (F7)\n"
        "3. Attach CHECK to M1 chart | AutoTrading ON\n"
        "4. Leave BridgePath EMPTY (uses MQL4/Files/CHECK) — Python auto-finds it\n"
        "   OR set BridgePath to this folder for isolated bridge:\n"
        f"   {bridge.resolve()}\n",
        encoding="utf-8",
    )
    exe = mt4_exe.strip() or r"%ProgramFiles%\MetaTrader 4\terminal.exe"
    bat = path / "launch_mt4.bat"
    bat.write_text(
        "\n".join(
            [
                "@echo off",
                f'set "MT4={exe}"',
                'if not exist "%MT4%" (echo Missing terminal.exe & pause & exit /b 1)',
                f'start "" "%MT4%" /login:{login} /password:{password} /server:{server}',
                "",
            ]
        ),
        encoding="utf-8",
    )
    # Deploy EA copy next to client for easy MetaEditor open
    ea_src = ROOT / "mt4" / "CHECK.mq4"
    if ea_src.exists():
        shutil.copy2(ea_src, path / "CHECK.mq4")

    reg = _reg()
    reg["clients"] = [c for c in reg["clients"] if c.get("id") != cid]
    reg["clients"].append({"id": cid, "login": login, "server": server, "label": client["label"]})
    _save_reg(reg)
    return client


def delete(cid: str) -> None:
    path = client_path(cid)
    if path.exists():
        shutil.rmtree(path)
    reg = _reg()
    reg["clients"] = [c for c in reg["clients"] if c.get("id") != cid]
    _save_reg(reg)


def launch(cid: str) -> tuple[bool, str]:
    client = read(cid)
    if not client:
        return False, "unknown client"
    bat = client_path(cid) / "launch_mt4.bat"
    if sys.platform.startswith("win") and bat.exists():
        subprocess.Popen(["cmd", "/c", str(bat)], cwd=str(client_path(cid)))  # noqa: S603
        return True, "MT4 launch started"
    return False, "Open launch_mt4.bat on Windows trading PC"


def all_bridges() -> list[Path]:
    """Client workspace bridges + live MT4 Files/CHECK folders under APPDATA."""
    found: dict[str, Path] = {}

    def add(path: Path) -> None:
        if not path.is_dir():
            return
        if not (path / "market").is_dir():
            return
        found[str(path.resolve())] = path.resolve()

    if CLIENTS.is_dir():
        for child in CLIENTS.iterdir():
            if child.is_dir():
                add(child / "bridge")

    import os

    appdata = os.environ.get("APPDATA")
    if appdata:
        base = Path(appdata) / "MetaQuotes" / "Terminal"
        if base.is_dir():
            for match in base.glob("**/MQL4/Files/CHECK"):
                add(match)

    return list(found.values())


def lot_for_account(account: str, default: float) -> float:
    for row in list_clients():
        full = read(str(row.get("id")))
        if full and str(full.get("login")) == str(account):
            try:
                return float(full.get("lot") or default)
            except (TypeError, ValueError):
                return default
    return default
