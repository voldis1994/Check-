"""CHECK platform store — EXE-owned settings + per-client MT4 workspaces.

Layout:
  config/platform.json          global trading settings (lot, SL ATR, BE, trail, …)
  clients/registry.json         index of accounts
  clients/<id>/client.json      login / server / paths
  clients/<id>/bridge/runtime/bridge/{market,status,commands,acknowledgements,archive}
  clients/<id>/launch_mt4.bat   Windows launcher with /login /password /server
  clients/<id>/lot.json         optional lot override (same shape as runtime/accounts)
"""

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
CLIENTS_ROOT = ROOT / "clients"
PLATFORM_FILE = ROOT / "config" / "platform.json"
REGISTRY_FILE = CLIENTS_ROOT / "registry.json"

DEFAULT_PLATFORM: dict[str, Any] = {
    "managed_by_exe": True,
    "fixed_lot": 0.02,
    "min_lot": 0.01,
    "max_lot": 100.0,
    "force_stop_atr": 1.0,
    "min_stop_atr": 0.6,
    "breakeven_trigger_atr": 0.75,
    "breakeven_offset_atr": 0.05,
    "trailing_start_atr": 0.50,
    "trailing_lock_atr": 0.75,
    "force_entry_when_idle": True,
    "breakout_enabled": True,
    "trend_enabled": True,
    "symbol": "AUTO",
    "mt4_terminal_exe": "",
    "cycle_interval_seconds": 5.0,
}


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _slug(text: str) -> str:
    s = re.sub(r"[^A-Za-z0-9_-]+", "_", text.strip())
    s = s.strip("_")[:48]
    return s or "client"


def load_platform() -> dict[str, Any]:
    if not PLATFORM_FILE.exists():
        return dict(DEFAULT_PLATFORM)
    try:
        data = json.loads(PLATFORM_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dict(DEFAULT_PLATFORM)
    if not isinstance(data, dict):
        return dict(DEFAULT_PLATFORM)
    out = dict(DEFAULT_PLATFORM)
    out.update(data)
    out["managed_by_exe"] = True
    return out


def save_platform(data: dict[str, Any]) -> Path:
    PLATFORM_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(DEFAULT_PLATFORM)
    payload.update(data)
    payload["managed_by_exe"] = True
    payload["updated_at"] = _now()
    PLATFORM_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return PLATFORM_FILE


def load_registry() -> dict[str, Any]:
    if not REGISTRY_FILE.exists():
        return {"version": 1, "clients": []}
    try:
        data = json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"version": 1, "clients": []}
    if not isinstance(data, dict):
        return {"version": 1, "clients": []}
    clients = data.get("clients")
    if not isinstance(clients, list):
        clients = []
    return {"version": 1, "clients": clients}


def save_registry(reg: dict[str, Any]) -> Path:
    CLIENTS_ROOT.mkdir(parents=True, exist_ok=True)
    payload = {"version": 1, "clients": list(reg.get("clients") or []), "updated_at": _now()}
    REGISTRY_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return REGISTRY_FILE


def list_clients() -> list[dict[str, Any]]:
    return [c for c in load_registry().get("clients", []) if isinstance(c, dict)]


def client_dir(client_id: str) -> Path:
    return CLIENTS_ROOT / client_id


def bridge_dir_for(client_id: str) -> Path:
    return client_dir(client_id) / "bridge" / "runtime" / "bridge"


def ensure_bridge_tree(bridge: Path) -> None:
    for name in ("market", "status", "commands", "acknowledgements", "archive"):
        (bridge / name).mkdir(parents=True, exist_ok=True)


def _write_launch_bat(client_path: Path, *, mt4_exe: str, login: str, password: str, server: str) -> Path:
    bat = client_path / "launch_mt4.bat"
    exe = mt4_exe.strip() or r"%ProgramFiles%\MetaTrader 4\terminal.exe"
    # Escape carets for cmd; keep simple quoting.
    lines = [
        "@echo off",
        "setlocal",
        f'title CHECK MT4 — {login}',
        f'set "MT4={exe}"',
        'if not exist "%MT4%" (',
        "  echo MT4 terminal.exe not found:",
        "  echo %MT4%",
        "  echo Set mt4_terminal_exe in CHECK COMMAND Settings.",
        "  pause",
        "  exit /b 1",
        ")",
        f'start "" "%MT4%" /login:{login} /password:{password} /server:{server}',
        "exit /b 0",
        "",
    ]
    bat.write_text("\n".join(lines), encoding="utf-8")
    return bat


def add_client(
    *,
    login: str,
    password: str,
    server: str,
    label: str = "",
    lot: float | None = None,
    mt4_terminal_exe: str | None = None,
) -> dict[str, Any]:
    login = str(login).strip()
    password = str(password)
    server = str(server).strip()
    if not login or not server:
        raise ValueError("login and server are required")
    if not password:
        raise ValueError("password is required")

    base_id = _slug(label or login)
    client_id = base_id
    n = 2
    while client_dir(client_id).exists():
        client_id = f"{base_id}_{n}"
        n += 1

    path = client_dir(client_id)
    path.mkdir(parents=True, exist_ok=False)
    bridge = bridge_dir_for(client_id)
    ensure_bridge_tree(bridge)

    platform = load_platform()
    exe = (mt4_terminal_exe if mt4_terminal_exe is not None else platform.get("mt4_terminal_exe")) or ""
    fixed_lot = float(lot) if lot is not None else float(platform.get("fixed_lot") or 0.02)

    client = {
        "id": client_id,
        "label": (label or login).strip(),
        "login": login,
        "password": password,
        "server": server,
        "enabled": True,
        "lot": fixed_lot,
        "mt4_terminal_exe": exe,
        "bridge_dir": str(bridge.relative_to(ROOT)).replace("\\", "/"),
        "created_at": _now(),
        "updated_at": _now(),
    }
    (path / "client.json").write_text(json.dumps(client, indent=2) + "\n", encoding="utf-8")
    (path / "lot.json").write_text(
        json.dumps({"fixed_lot": fixed_lot, "updated_at": _now(), "source": "platform"}, indent=2) + "\n",
        encoding="utf-8",
    )
    _write_launch_bat(path, mt4_exe=str(exe), login=login, password=password, server=server)

    # Mirror lot into runtime/accounts/<login> so engine account_lot picks it up by account_id
    rt_lot = ROOT / "runtime" / "accounts" / login / "lot.json"
    rt_lot.parent.mkdir(parents=True, exist_ok=True)
    rt_lot.write_text(
        json.dumps({"fixed_lot": fixed_lot, "updated_at": _now(), "source": "platform"}, indent=2) + "\n",
        encoding="utf-8",
    )

    # Bridge pointer file for EA (human-readable)
    (path / "BRIDGE_PATH.txt").write_text(
        f"Point CHECK_SYSTEM_V3 BridgeRootPath to:\n{bridge.parent.parent.resolve()}\n"
        f"(folder that contains runtime/bridge)\n",
        encoding="utf-8",
    )

    reg = load_registry()
    clients = [c for c in reg["clients"] if isinstance(c, dict) and c.get("id") != client_id]
    clients.append(
        {
            "id": client_id,
            "label": client["label"],
            "login": login,
            "server": server,
            "enabled": True,
            "path": str(path.relative_to(ROOT)).replace("\\", "/"),
        }
    )
    reg["clients"] = clients
    save_registry(reg)
    return client


def read_client(client_id: str) -> dict[str, Any] | None:
    path = client_dir(client_id) / "client.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def update_client(client_id: str, **fields: Any) -> dict[str, Any]:
    client = read_client(client_id)
    if client is None:
        raise FileNotFoundError(client_id)
    for key in ("label", "login", "password", "server", "enabled", "lot", "mt4_terminal_exe"):
        if key in fields and fields[key] is not None:
            client[key] = fields[key]
    client["updated_at"] = _now()
    path = client_dir(client_id)
    (path / "client.json").write_text(json.dumps(client, indent=2) + "\n", encoding="utf-8")
    if "lot" in fields and fields["lot"] is not None:
        lot = float(fields["lot"])
        (path / "lot.json").write_text(
            json.dumps({"fixed_lot": lot, "updated_at": _now(), "source": "platform"}, indent=2) + "\n",
            encoding="utf-8",
        )
        login = str(client.get("login") or client_id)
        rt_lot = ROOT / "runtime" / "accounts" / login / "lot.json"
        rt_lot.parent.mkdir(parents=True, exist_ok=True)
        rt_lot.write_text(
            json.dumps({"fixed_lot": lot, "updated_at": _now(), "source": "platform"}, indent=2) + "\n",
            encoding="utf-8",
        )
    _write_launch_bat(
        path,
        mt4_exe=str(client.get("mt4_terminal_exe") or ""),
        login=str(client.get("login") or ""),
        password=str(client.get("password") or ""),
        server=str(client.get("server") or ""),
    )
    reg = load_registry()
    for row in reg["clients"]:
        if isinstance(row, dict) and row.get("id") == client_id:
            row["label"] = client.get("label")
            row["login"] = client.get("login")
            row["server"] = client.get("server")
            row["enabled"] = client.get("enabled", True)
    save_registry(reg)
    return client


def delete_client(client_id: str) -> bool:
    path = client_dir(client_id)
    client = read_client(client_id)
    if path.exists():
        shutil.rmtree(path, ignore_errors=False)
    reg = load_registry()
    reg["clients"] = [c for c in reg["clients"] if not (isinstance(c, dict) and c.get("id") == client_id)]
    save_registry(reg)
    if client:
        login = str(client.get("login") or "")
        if login:
            lot_path = ROOT / "runtime" / "accounts" / login / "lot.json"
            if lot_path.exists():
                lot_path.unlink()
    return True


def launch_client_mt4(client_id: str) -> tuple[bool, str]:
    client = read_client(client_id)
    if client is None:
        return False, f"unknown client {client_id}"
    bat = client_dir(client_id) / "launch_mt4.bat"
    exe = str(client.get("mt4_terminal_exe") or load_platform().get("mt4_terminal_exe") or "").strip()
    login = str(client.get("login") or "")
    password = str(client.get("password") or "")
    server = str(client.get("server") or "")
    if sys.platform.startswith("win"):
        if bat.exists():
            subprocess.Popen(["cmd", "/c", str(bat)], cwd=str(client_dir(client_id)))  # noqa: S603
            return True, f"launched {bat.name}"
        if exe:
            subprocess.Popen(  # noqa: S603
                [exe, f"/login:{login}", f"/password:{password}", f"/server:{server}"]
            )
            return True, f"launched {exe}"
        return False, "Set mt4_terminal_exe in Settings (path to terminal.exe)"
    # Non-Windows: record intent only
    return False, "MT4 launch is Windows-only — open launch_mt4.bat on the trading PC"


def discover_client_bridges() -> list[Path]:
    out: list[Path] = []
    if not CLIENTS_ROOT.is_dir():
        return out
    for child in CLIENTS_ROOT.iterdir():
        if not child.is_dir():
            continue
        bridge = child / "bridge" / "runtime" / "bridge"
        if (bridge / "market").is_dir():
            out.append(bridge.resolve())
    return out


def apply_platform_to_system_json(system_path: Path) -> bool:
    """Write EXE platform settings into system.json and mark platform_managed."""
    platform = load_platform()
    if not system_path.exists():
        return False
    try:
        data = json.loads(system_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(data, dict):
        return False

    runtime = dict(data.get("runtime") or {})
    runtime["platform_managed"] = True
    if "cycle_interval_seconds" in platform:
        try:
            runtime["cycle_interval_seconds"] = float(platform["cycle_interval_seconds"])
        except (TypeError, ValueError):
            pass
    data["runtime"] = runtime

    pos = dict(data.get("position") or {})
    sizing = dict(data.get("position_sizing") or {})
    lot = float(platform.get("fixed_lot") or sizing.get("fixed_lot") or 0.02)
    pos["default_lot"] = lot
    sizing["fixed_lot"] = lot
    sizing["min_lot"] = float(platform.get("min_lot") or sizing.get("min_lot") or 0.01)
    sizing["max_lot"] = float(platform.get("max_lot") or sizing.get("max_lot") or 100.0)
    data["position"] = pos
    data["position_sizing"] = sizing

    strategies = dict(data.get("strategies") or {})
    strategies["force_stop_atr"] = float(platform.get("force_stop_atr") or 1.0)
    strategies["min_stop_atr"] = float(platform.get("min_stop_atr") or 0.6)
    strategies["force_entry_when_idle"] = bool(platform.get("force_entry_when_idle", True))
    tc = dict(strategies.get("trend_continuation") or {})
    tc["enabled"] = bool(platform.get("trend_enabled", True))
    strategies["trend_continuation"] = tc
    bo = dict(strategies.get("breakout") or {})
    bo["enabled"] = bool(platform.get("breakout_enabled", True))
    strategies["breakout"] = bo
    rr = dict(strategies.get("range_reversion") or {})
    rr["enabled"] = False
    strategies["range_reversion"] = rr
    data["strategies"] = strategies

    mgmt = dict(data.get("management") or {})
    mgmt["breakeven_trigger_atr"] = float(platform.get("breakeven_trigger_atr") or 0.75)
    mgmt["breakeven_offset_atr"] = float(platform.get("breakeven_offset_atr") or 0.05)
    mgmt["trailing_start_atr"] = float(platform.get("trailing_start_atr") or 0.50)
    mgmt["trailing_lock_atr"] = float(platform.get("trailing_lock_atr") or 0.75)
    data["management"] = mgmt

    instrument = dict(data.get("instrument") or {})
    instrument["symbol"] = str(platform.get("symbol") or instrument.get("symbol") or "AUTO")
    instrument["timeframe_execution"] = "M1"
    data["instrument"] = instrument

    # Prefer discovering client bridges
    paths = dict(data.get("paths") or {})
    roots = list(paths.get("bridge_discovery_roots") or [])
    clients_glob = str((CLIENTS_ROOT / "*").resolve())
    if clients_glob not in roots:
        roots.append(str(CLIENTS_ROOT.resolve()))
    paths["bridge_discovery_roots"] = roots
    data["paths"] = paths

    system_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return True
