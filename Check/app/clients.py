"""Accounts + portable MT4 clones from template master."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app import paths

# Default points — user edits per account in UI
ACCOUNT_DEFAULTS = {
    "lot": 0.02,
    "sl_points": 150,
    "be_start_points": 50,
    "be_offset_points": 5,
    "trail_start_points": 80,
    "trail_lock_points": 40,
}


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _slug(text: str) -> str:
    s = re.sub(r"[^A-Za-z0-9_-]+", "_", text.strip()).strip("_")[:40]
    return s or "client"


def clients_root() -> Path:
    return paths.app_root() / "clients"


def instances_root() -> Path:
    return paths.app_root() / "instances"


def registry_path() -> Path:
    return clients_root() / "registry.json"


def master_mt4() -> Path | None:
    marker = paths.app_root() / "runtime" / "master_mt4.txt"
    if marker.exists():
        p = Path(marker.read_text(encoding="utf-8").strip())
        if (p / "terminal.exe").exists():
            return p
    master = instances_root() / "_master"
    if (master / "terminal.exe").exists():
        return master
    # fallback: search template
    template = paths.app_root() / "template"
    if template.is_dir():
        for hit in template.rglob("terminal.exe"):
            return hit.parent
    return None


def _reg() -> dict[str, Any]:
    path = registry_path()
    if not path.exists():
        return {"clients": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"clients": []}
    if not isinstance(data, dict):
        return {"clients": []}
    data.setdefault("clients", [])
    return data


def _save_reg(reg: dict[str, Any]) -> None:
    paths.ensure_layout()
    clients_root().mkdir(parents=True, exist_ok=True)
    reg["updated_at"] = _now()
    registry_path().write_text(json.dumps(reg, indent=2) + "\n", encoding="utf-8")


def list_clients() -> list[dict[str, Any]]:
    return [c for c in _reg().get("clients", []) if isinstance(c, dict)]


def client_path(cid: str) -> Path:
    return clients_root() / cid


def read(cid: str) -> dict[str, Any] | None:
    path = client_path(cid) / "client.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def write_client(cid: str, data: dict[str, Any]) -> None:
    path = client_path(cid)
    path.mkdir(parents=True, exist_ok=True)
    (path / "client.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def ea_source() -> Path:
    return paths.app_root() / "mt4" / "CHECK.mq4"


def _seed_bridge(mt4_dir: Path) -> Path:
    bridge = mt4_dir / "MQL4" / "Files" / "CHECK"
    for name in ("market", "status", "commands", "acks"):
        (bridge / name).mkdir(parents=True, exist_ok=True)
    return bridge


def _install_ea(mt4_dir: Path) -> None:
    experts = mt4_dir / "MQL4" / "Experts"
    experts.mkdir(parents=True, exist_ok=True)
    src = ea_source()
    if src.exists():
        shutil.copy2(src, experts / "CHECK.mq4")
    ex4 = src.with_suffix(".ex4")
    master = master_mt4()
    if ex4.exists():
        shutil.copy2(ex4, experts / "CHECK.ex4")
    elif master and (master / "MQL4" / "Experts" / "CHECK.ex4").exists():
        shutil.copy2(master / "MQL4" / "Experts" / "CHECK.ex4", experts / "CHECK.ex4")
    _seed_bridge(mt4_dir)


def clone_mt4_for_account(cid: str) -> Path:
    """Clone master/template MT4 into instances/<cid>."""
    master = master_mt4()
    if master is None:
        raise FileNotFoundError(
            "No MT4 template. Put original MT4 in Check\\template\\ then run SETUP.bat"
        )
    dest = instances_root() / cid
    if not dest.exists():
        shutil.copytree(master, dest, dirs_exist_ok=False)
    _install_ea(dest)
    return dest


def add(
    *,
    login: str,
    password: str,
    server: str,
    label: str = "",
    lot: float = 0.02,
    sl_points: float = 150,
    be_start_points: float = 50,
    be_offset_points: float = 5,
    trail_start_points: float = 80,
    trail_lock_points: float = 40,
) -> dict[str, Any]:
    paths.ensure_layout()
    login = login.strip()
    server = server.strip()
    if not login or not server or not password:
        raise ValueError("login, password, server required")

    base = _slug(label or login)
    cid = base
    n = 2
    while client_path(cid).exists() or (instances_root() / cid).exists():
        cid = f"{base}_{n}"
        n += 1

    mt4_dir = clone_mt4_for_account(cid)
    bridge = _seed_bridge(mt4_dir)
    terminal = mt4_dir / "terminal.exe"

    client = {
        "id": cid,
        "label": (label or login).strip(),
        "login": login,
        "password": password,
        "server": server,
        "lot": float(lot),
        "sl_points": float(sl_points),
        "be_start_points": float(be_start_points),
        "be_offset_points": float(be_offset_points),
        "trail_start_points": float(trail_start_points),
        "trail_lock_points": float(trail_lock_points),
        "mt4_dir": str(mt4_dir),
        "mt4_exe": str(terminal),
        "bridge": str(bridge),
        "created_at": _now(),
    }
    write_client(cid, client)
    (client_path(cid) / "SETUP.txt").write_text(
        "CHECK account ready\n"
        "1. LAUNCH MT4 for this account\n"
        "2. Attach CHECK on M1 (BridgePath empty)\n"
        "3. AutoTrading ON\n"
        "4. START LIVE\n"
        f"\nSL/BE/TRAIL points are set on this account only.\n"
        f"sl={sl_points} be_start={be_start_points} trail_start={trail_start_points}\n",
        encoding="utf-8",
    )

    reg = _reg()
    reg["clients"] = [c for c in reg["clients"] if c.get("id") != cid]
    reg["clients"].append({"id": cid, "login": login, "server": server, "label": client["label"]})
    _save_reg(reg)
    return client


def update_risk(cid: str, **fields: Any) -> dict[str, Any]:
    client = read(cid)
    if not client:
        raise ValueError("unknown client")
    allowed = {
        "lot",
        "sl_points",
        "be_start_points",
        "be_offset_points",
        "trail_start_points",
        "trail_lock_points",
        "label",
        "password",
        "server",
    }
    for k, v in fields.items():
        if k in allowed:
            client[k] = v
    write_client(cid, client)
    return client


def delete(cid: str) -> None:
    path = client_path(cid)
    if path.exists():
        shutil.rmtree(path)
    inst = instances_root() / cid
    if inst.exists():
        shutil.rmtree(inst)
    reg = _reg()
    reg["clients"] = [c for c in reg["clients"] if c.get("id") != cid]
    _save_reg(reg)


def launch(cid: str) -> tuple[bool, str]:
    client = read(cid)
    if not client:
        return False, "unknown client"
    exe = Path(str(client.get("mt4_exe") or ""))
    if not exe.exists():
        # try re-clone
        try:
            mt4_dir = clone_mt4_for_account(cid)
            exe = mt4_dir / "terminal.exe"
            client["mt4_dir"] = str(mt4_dir)
            client["mt4_exe"] = str(exe)
            client["bridge"] = str(_seed_bridge(mt4_dir))
            write_client(cid, client)
        except FileNotFoundError as exc:
            return False, str(exc)
    if not exe.exists():
        return False, f"terminal.exe missing: {exe}\nRun SETUP.bat after placing MT4 in template\\"

    login = str(client.get("login") or "")
    password = str(client.get("password") or "")
    server = str(client.get("server") or "")
    _install_ea(exe.parent)

    if sys.platform.startswith("win"):
        try:
            subprocess.Popen(  # noqa: S603
                [str(exe), f"/login:{login}", f"/password:{password}", f"/server:{server}"],
                cwd=str(exe.parent),
            )
        except OSError as exc:
            return False, f"Could not start MT4: {exc}"
        return True, (
            f"MT4 started for {cid}\n{exe}\n\n"
            "Attach CHECK on M1 | BridgePath empty | AutoTrading ON"
        )
    return False, f"Windows only. terminal: {exe}"


def all_bridges() -> list[Path]:
    found: dict[str, Path] = {}

    def add_bridge(path: Path) -> None:
        if path.is_dir() and (path / "market").is_dir():
            found[str(path.resolve())] = path.resolve()

    for row in list_clients():
        full = read(str(row.get("id")))
        if not full:
            continue
        b = Path(str(full.get("bridge") or ""))
        if b.is_dir():
            add_bridge(b)
        mt4 = Path(str(full.get("mt4_dir") or ""))
        if mt4.is_dir():
            add_bridge(mt4 / "MQL4" / "Files" / "CHECK")

    # also discover under instances
    root = instances_root()
    if root.is_dir():
        for match in root.glob("*/MQL4/Files/CHECK"):
            add_bridge(match)

    appdata = os.environ.get("APPDATA")
    if appdata:
        base = Path(appdata) / "MetaQuotes" / "Terminal"
        if base.is_dir():
            for match in base.glob("**/MQL4/Files/CHECK"):
                add_bridge(match)
    return list(found.values())


def account_for_bridge(bridge: Path) -> dict[str, Any] | None:
    bkey = str(bridge.resolve())
    for row in list_clients():
        full = read(str(row.get("id")))
        if not full:
            continue
        candidates = []
        if full.get("bridge"):
            candidates.append(Path(str(full["bridge"])))
        if full.get("mt4_dir"):
            candidates.append(Path(str(full["mt4_dir"])) / "MQL4" / "Files" / "CHECK")
        for c in candidates:
            try:
                if c.exists() and str(c.resolve()) == bkey:
                    return full
            except OSError:
                continue
        # match by login/account in status later — also by folder name
        if full.get("id") and full["id"] in bkey.replace("\\", "/"):
            return full
    return None


def account_by_login(login: str) -> dict[str, Any] | None:
    for row in list_clients():
        full = read(str(row.get("id")))
        if full and str(full.get("login")) == str(login):
            return full
    return None


def setup_status() -> dict[str, Any]:
    master = master_mt4()
    bridges = all_bridges()
    live = []
    for b in bridges:
        from app import bridge as bridge_mod

        age = bridge_mod.age_s(b / "market" / "latest.json")
        if age is not None and age < 30:
            live.append(b)
    return {
        "template_ok": master is not None,
        "clients": len(list_clients()),
        "bridges": len(bridges),
        "live_bridges": len(live),
        "ready": len(live) > 0,
        "master": str(master) if master else "",
    }
