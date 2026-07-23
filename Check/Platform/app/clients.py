"""CHECK Platform v4 — clients, MT4 deploy, launch, compile."""

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


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _slug(text: str) -> str:
    s = re.sub(r"[^A-Za-z0-9_-]+", "_", text.strip()).strip("_")[:40]
    return s or "client"


def clients_root() -> Path:
    return paths.app_root() / "clients"


def registry_path() -> Path:
    return clients_root() / "registry.json"


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


def bridge_path(cid: str) -> Path:
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


def ea_source() -> Path:
    return paths.app_root() / "mt4" / "CHECK.mq4"


def find_terminal_exe(explicit: str = "") -> Path | None:
    """Resolve terminal.exe from explicit path, then common install folders."""
    candidates: list[Path] = []
    raw = (explicit or "").strip().strip('"')
    if raw:
        candidates.append(Path(os.path.expandvars(raw)))

    pf = os.environ.get("ProgramFiles", r"C:\Program Files")
    pf86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    local = os.environ.get("LOCALAPPDATA", "")
    names = (
        "MetaTrader 4",
        "MetaTrader",
        "MetaTrader 4 IC Markets",
        "IC Markets MetaTrader 4",
        "Pepperstone MetaTrader 4",
        "FXCM MetaTrader 4",
        "XM Global MT4",
        "Admiral Markets MetaTrader 4",
        "Exness MetaTrader 4",
        "FTMO MetaTrader 4",
    )
    for base in (pf, pf86, local):
        if not base:
            continue
        root = Path(base)
        for name in names:
            candidates.append(root / name / "terminal.exe")
        try:
            if root.is_dir():
                for child in root.iterdir():
                    if child.is_dir():
                        candidates.append(child / "terminal.exe")
        except OSError:
            pass

    seen: set[str] = set()
    for c in candidates:
        try:
            key = str(c.resolve()) if c.exists() else str(c)
        except OSError:
            key = str(c)
        if key in seen:
            continue
        seen.add(key)
        try:
            if c.is_file():
                return c.resolve()
        except OSError:
            continue
    return None


def find_metaeditor(mt4_exe: str = "", explicit: str = "") -> Path | None:
    if explicit and Path(os.path.expandvars(explicit)).exists():
        return Path(os.path.expandvars(explicit))
    candidates: list[Path] = []
    term = find_terminal_exe(mt4_exe) if mt4_exe else find_terminal_exe()
    if term is not None:
        candidates.append(term.parent / "metaeditor.exe")
    if mt4_exe:
        p = Path(os.path.expandvars(mt4_exe))
        candidates.append(p.parent / "metaeditor.exe")
    pf = os.environ.get("ProgramFiles", r"C:\Program Files")
    pf86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    for base in (pf, pf86):
        candidates.append(Path(base) / "MetaTrader 4" / "metaeditor.exe")
    for c in candidates:
        if c.exists():
            return c
    return None


def write_launch_bat(cid: str, *, login: str, password: str, server: str, mt4_exe: str) -> Path:
    """Write ASCII-only launch bat (Windows cmd encoding-safe)."""
    path = client_path(cid)
    path.mkdir(parents=True, exist_ok=True)
    bat = path / "launch_mt4.bat"
    exe = mt4_exe.replace('"', "")
    lines = [
        "@echo off",
        "chcp 65001 >nul",
        f'set "MT4={exe}"',
        'if not exist "%MT4%" (',
        "  echo Missing terminal.exe",
        "  echo Set path in CHECK - SETTINGS - MT4 terminal.exe - SAVE",
        "  echo Then press LAUNCH MT4 again",
        "  pause",
        "  exit /b 1",
        ")",
        f'start "" "%MT4%" /login:{login} /password:{password} /server:{server}',
        "",
    ]
    bat.write_text("\n".join(lines), encoding="ascii", errors="replace")
    return bat


def resolve_client_mt4(client: dict[str, Any] | None = None) -> Path | None:
    from app import settings as settings_mod

    cfg = settings_mod.load()
    for candidate in (
        (client or {}).get("mt4_exe"),
        cfg.get("mt4_exe"),
        "",
    ):
        found = find_terminal_exe(str(candidate or ""))
        if found is not None:
            return found
    return find_terminal_exe()



def compile_ea(*, mt4_exe: str = "", metaeditor_exe: str = "") -> tuple[bool, str]:
    """Best-effort compile CHECK.mq4 → CHECK.ex4 via MetaEditor."""
    ea = ea_source()
    if not ea.exists():
        return False, f"missing {ea}"
    editor = find_metaeditor(mt4_exe, metaeditor_exe)
    if editor is None:
        return False, "metaeditor.exe not found — set path in Settings or compile manually (F7)"
    if not sys.platform.startswith("win"):
        return False, "compile is Windows-only"
    try:
        subprocess.run(  # noqa: S603
            [str(editor), f"/compile:{ea}", "/log"],
            check=False,
            timeout=120,
            cwd=str(ea.parent),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"compile failed: {exc}"
    ex4 = ea.with_suffix(".ex4")
    # Also look in Experts after deploy
    if ex4.exists():
        return True, f"compiled {ex4.name}"
    return False, "MetaEditor ran — if Navigator has no CHECK, open CHECK.mq4 and press F7"


def deploy_mt4(*, mt4_exe: str = "", metaeditor_exe: str = "") -> tuple[int, str]:
    """Copy CHECK.mq4 (+ .ex4 if present) into every MT4 Experts + seed Files/CHECK."""
    ea_src = ea_source()
    if not ea_src.exists():
        return 0, f"missing EA: {ea_src}"

    appdata = os.environ.get("APPDATA")
    if not appdata:
        return 0, "APPDATA not set (run on Windows trading PC)"

    terminal_root = Path(appdata) / "MetaQuotes" / "Terminal"
    if not terminal_root.is_dir():
        return 0, f"no terminals under {terminal_root} — open MT4 once, then DEPLOY"

    # Try compile first so Experts get .ex4 when possible
    compiled, compile_msg = compile_ea(mt4_exe=mt4_exe, metaeditor_exe=metaeditor_exe)
    ex4_src = ea_src.with_suffix(".ex4")

    count = 0
    for term in terminal_root.iterdir():
        if not term.is_dir():
            continue
        mql4 = term / "MQL4"
        if not mql4.is_dir():
            continue
        experts = mql4 / "Experts"
        experts.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ea_src, experts / "CHECK.mq4")
        if ex4_src.exists():
            shutil.copy2(ex4_src, experts / "CHECK.ex4")
        check_files = mql4 / "Files" / "CHECK"
        for name in ("market", "status", "commands", "acks"):
            (check_files / name).mkdir(parents=True, exist_ok=True)
        count += 1

    if count == 0:
        return 0, "no MQL4 folders found — install/open MT4 once, then DEPLOY again"

    extra = compile_msg if compiled else (
        "Compile manually: MetaEditor → Experts\\CHECK.mq4 → F7. " + compile_msg
    )
    return count, f"Deployed to {count} terminal(s). {extra} Attach CHECK to M1, AutoTrading ON, BridgePath empty."


def add(
    *,
    login: str,
    password: str,
    server: str,
    label: str = "",
    lot: float = 0.02,
    mt4_terminal_exe: str = "",
    metaeditor_exe: str = "",
) -> dict[str, Any]:
    paths.ensure_layout()
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
    found = find_terminal_exe(mt4_terminal_exe) or find_terminal_exe()
    exe = str(found) if found else (mt4_terminal_exe.strip() or r"%ProgramFiles%\MetaTrader 4\terminal.exe")

    client = {
        "id": cid,
        "label": (label or login).strip(),
        "login": login,
        "password": password,
        "server": server,
        "lot": float(lot),
        "mt4_exe": exe,
        "bridge": str(bridge),
        "created_at": _now(),
    }
    (path / "client.json").write_text(json.dumps(client, indent=2) + "\n", encoding="utf-8")
    (path / "SETUP.txt").write_text(
        "CHECK Platform - account ready\n"
        "==============================\n"
        "1. SETTINGS: set terminal.exe path and SAVE (or DETECT)\n"
        "2. Click LAUNCH MT4\n"
        "3. In MT4: Navigator -> Experts -> CHECK -> drag onto M1 chart\n"
        "4. Inputs: BridgePath = EMPTY, MagicNumber = 40001\n"
        "5. Allow AutoTrading (toolbar button)\n"
        "6. Back in CHECK -> START LIVE\n"
        f"\nLogin: {login}\nServer: {server}\n",
        encoding="utf-8",
    )
    write_launch_bat(cid, login=login, password=password, server=server, mt4_exe=exe)
    if ea_source().exists():
        shutil.copy2(ea_source(), path / "CHECK.mq4")

    deployed, deploy_msg = deploy_mt4(mt4_exe=exe, metaeditor_exe=metaeditor_exe)
    client["deployed_terminals"] = deployed
    client["deploy_msg"] = deploy_msg
    (path / "client.json").write_text(json.dumps(client, indent=2) + "\n", encoding="utf-8")

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


def refresh_launch_bats(mt4_exe: str = "") -> int:
    """Rewrite all client launch bats after Settings save."""
    n = 0
    for row in list_clients():
        cid = str(row.get("id") or "")
        full = read(cid)
        if not full:
            continue
        exe = find_terminal_exe(mt4_exe) or find_terminal_exe(str(full.get("mt4_exe") or "")) or find_terminal_exe()
        if exe is None:
            continue
        full["mt4_exe"] = str(exe)
        (client_path(cid) / "client.json").write_text(json.dumps(full, indent=2) + "\n", encoding="utf-8")
        write_launch_bat(
            cid,
            login=str(full.get("login") or ""),
            password=str(full.get("password") or ""),
            server=str(full.get("server") or ""),
            mt4_exe=str(exe),
        )
        n += 1
    return n


def launch(cid: str) -> tuple[bool, str]:
    client = read(cid)
    if not client:
        return False, "unknown client"

    exe = resolve_client_mt4(client)
    if exe is None:
        return (
            False,
            "terminal.exe not found.\n\n"
            "Go to SETTINGS -> click ... next to MT4 terminal.exe\n"
            "(or DETECT) -> SAVE -> LAUNCH MT4 again.\n\n"
            "Typical path:\n"
            "C:\\Program Files\\MetaTrader 4\\terminal.exe\n"
            "or your broker MT4 folder.",
        )

    login = str(client.get("login") or "")
    password = str(client.get("password") or "")
    server = str(client.get("server") or "")
    client["mt4_exe"] = str(exe)
    (client_path(cid) / "client.json").write_text(json.dumps(client, indent=2) + "\n", encoding="utf-8")
    write_launch_bat(cid, login=login, password=password, server=server, mt4_exe=str(exe))

    if sys.platform.startswith("win"):
        try:
            subprocess.Popen(  # noqa: S603
                [str(exe), f"/login:{login}", f"/password:{password}", f"/server:{server}"],
                cwd=str(exe.parent),
            )
        except OSError as exc:
            return False, f"Could not start MT4: {exc}"
        return True, f"MT4 started: {exe}\n\nAttach CHECK to M1 chart, AutoTrading ON, then START LIVE"

    return False, f"On Windows PC run: {client_path(cid) / 'launch_mt4.bat'}\nResolved: {exe}"


def all_bridges() -> list[Path]:
    found: dict[str, Path] = {}

    def add(path: Path) -> None:
        if path.is_dir() and (path / "market").is_dir():
            found[str(path.resolve())] = path.resolve()

    cr = clients_root()
    if cr.is_dir():
        for child in cr.iterdir():
            if child.is_dir():
                add(child / "bridge")

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


def setup_status() -> dict[str, Any]:
    """First-run checklist for the UI."""
    cfg_path = paths.app_root() / "config" / "settings.json"
    from app import settings as settings_mod

    cfg = settings_mod.load()
    mt4 = find_terminal_exe(str(cfg.get("mt4_exe") or ""))
    bridges = all_bridges()
    live = []
    for b in bridges:
        from app import bridge as bridge_mod

        age = bridge_mod.age_s(b / "market" / "latest.json")
        if age is not None and age < 30:
            live.append(b)
    return {
        "settings_saved": cfg_path.exists(),
        "mt4_exe_set": mt4 is not None or bool(str(cfg.get("mt4_exe") or "").strip()),
        "mt4_exe_found": mt4 is not None,
        "clients": len(list_clients()),
        "bridges": len(bridges),
        "live_bridges": len(live),
        "ready": len(live) > 0,
    }
