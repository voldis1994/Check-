"""Non-UI helpers for the CHECK SYSTEM desktop dashboard."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
STOP_NAME = "STOP_TRADING"


def resolve_config(preferred: str | Path | None = None) -> Path:
    candidates: list[Path] = []
    if preferred is not None:
        path = Path(preferred)
        candidates.append(path if path.is_absolute() else ROOT / path)
    candidates.extend([ROOT / "config" / "system.json", ROOT / "config" / "system.example.json"])
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("No config found under config/system.json or config/system.example.json")


def runtime_dir(config_data: dict[str, Any] | None = None) -> Path:
    if config_data:
        raw = ((config_data.get("paths") or {}).get("runtime_dir")) or "runtime"
        path = Path(str(raw))
        return path if path.is_absolute() else ROOT / path
    return ROOT / "runtime"


def audit_file(config_data: dict[str, Any] | None = None) -> Path:
    if config_data:
        raw = ((config_data.get("paths") or {}).get("audit_file")) or "runtime/audit.jsonl"
        path = Path(str(raw))
        return path if path.is_absolute() else ROOT / path
    return ROOT / "runtime" / "audit.jsonl"


def load_config_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def stop_file_path(rt: Path) -> Path:
    return rt / STOP_NAME


def write_stop(rt: Path) -> Path:
    rt.mkdir(parents=True, exist_ok=True)
    path = stop_file_path(rt)
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    path.write_text(f"STOP_TRADING created_at_utc={stamp}\n", encoding="ascii")
    return path


def clear_stop(rt: Path) -> bool:
    path = stop_file_path(rt)
    if path.exists():
        path.unlink()
        return True
    return False


def discover_bridge_dirs(configured: Path | None = None) -> list[Path]:
    found: dict[str, Path] = {}

    def add(path: Path) -> None:
        if not path.exists() or not path.is_dir():
            return
        market_dir = path / "market"
        if not market_dir.is_dir():
            return
        if not any(market_dir.glob("*.json")):
            return
        found[str(path.resolve())] = path.resolve()

    if configured is not None:
        add(configured)
    add(ROOT / "runtime" / "bridge")

    appdata = os.environ.get("APPDATA")
    if appdata:
        base = Path(appdata) / "MetaQuotes" / "Terminal"
        if base.exists():
            for pattern in (
                "**/MQL4/Files/CHECK_SYSTEM/runtime/bridge",
                "**/MQL4/Files/CHECK_SYSTEM_V3/runtime/bridge",
            ):
                for match in base.glob(pattern):
                    add(match)

    return list(found.values())


def _preferred_json(folder: Path, *, role: str) -> Path | None:
    """Prefer latest.json, then v3 account_symbol role files, ignore legacy names when possible."""
    if not folder.exists():
        return None
    latest = folder / "latest.json"
    if latest.exists():
        return latest

    files = [p for p in folder.glob("*.json") if p.is_file()]
    if not files:
        return None

    def score(path: Path) -> tuple[int, float]:
        name = path.name.lower()
        # Higher score wins; then newer mtime.
        if name == "latest.json":
            tier = 3
        elif name.endswith(f"_{role}.json"):
            tier = 2
        elif name.startswith(f"{role}_"):
            tier = 0  # legacy market_SYMBOL_*.json / status_ACCOUNT.json
        else:
            tier = 1
        return (tier, path.stat().st_mtime)

    return sorted(files, key=score, reverse=True)[0]


def _latest_json(folder: Path) -> Path | None:
    return _preferred_json(folder, role="market")


def _latest_status_json(folder: Path) -> Path | None:
    return _preferred_json(folder, role="status")


def _age_seconds(path: Path | None) -> float | None:
    if path is None or not path.exists():
        return None
    return max(0.0, time.time() - path.stat().st_mtime)


def format_age(seconds: float | None) -> str:
    if seconds is None:
        return "missing"
    if seconds < 2:
        return "fresh"
    if seconds < 60:
        label = f"{seconds:.0f}s ago"
    elif seconds < 3600:
        label = f"{seconds / 60:.1f}m ago"
    else:
        label = f"{seconds / 3600:.1f}h ago"
    if seconds > 30:
        return f"STALE {label}"
    return label


@dataclass(slots=True)
class BridgeSnapshot:
    path: Path
    market_age_s: float | None
    status_age_s: float | None
    commands: int
    acks: int
    market_file: str | None
    status_file: str | None
    account_id: str = "-"


@dataclass(slots=True)
class HealthSnapshot:
    config_path: Path
    mode: str
    trading_enabled: bool
    symbol: str
    stop_present: bool
    bridges: list[BridgeSnapshot] = field(default_factory=list)
    last_audit: dict[str, Any] | None = None


def read_last_audit(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            return data
    return None


def read_last_audits_by_account(path: Path, *, limit_accounts: int = 8) -> dict[str, dict[str, Any]]:
    """Newest audit row per account_number (or '-')."""
    if not path.exists():
        return {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}
    found: dict[str, dict[str, Any]] = {}
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(data, dict):
            continue
        acct = str(data.get("account_number") or "-")
        if acct in found:
            continue
        found[acct] = data
        if len(found) >= limit_accounts:
            break
    return found


def collect_health(config_path: Path) -> HealthSnapshot:
    data = load_config_json(config_path)
    runtime = data.get("runtime") or {}
    instrument = data.get("instrument") or {}
    paths = data.get("paths") or {}
    configured_bridge = paths.get("bridge_dir")
    bridge_path = Path(configured_bridge) if configured_bridge else None
    if bridge_path is not None and not bridge_path.is_absolute():
        bridge_path = ROOT / bridge_path

    rt = runtime_dir(data)
    bridges: list[BridgeSnapshot] = []
    for bridge in discover_bridge_dirs(bridge_path):
        market = _latest_json(bridge / "market")
        status = _latest_status_json(bridge / "status")
        commands = list((bridge / "commands").glob("*.json")) if (bridge / "commands").exists() else []
        acks = list((bridge / "acknowledgements").glob("*.json")) if (bridge / "acknowledgements").exists() else []
        account_id = "-"
        if status is not None:
            try:
                payload = json.loads(status.read_text(encoding="utf-8"))
                body = payload.get("payload", payload) if isinstance(payload, dict) else {}
                if isinstance(body, dict):
                    account_id = str(body.get("account_number") or body.get("account_id") or "-")
            except (OSError, json.JSONDecodeError):
                account_id = "-"
        bridges.append(
            BridgeSnapshot(
                path=bridge,
                market_age_s=_age_seconds(market),
                status_age_s=_age_seconds(status),
                commands=len(commands),
                acks=len(acks),
                market_file=market.name if market else None,
                status_file=status.name if status else None,
                account_id=account_id,
            )
        )

    return HealthSnapshot(
        config_path=config_path,
        mode=str(runtime.get("mode", "paper")),
        trading_enabled=bool(runtime.get("trading_enabled", False)),
        symbol=str(instrument.get("symbol", "AUTO")),
        stop_present=stop_file_path(rt).exists(),
        bridges=bridges,
        last_audit=read_last_audit(audit_file(data)),
    )


def format_audit_line(entry: dict[str, Any]) -> str:
    stamp = str(entry.get("completed_at") or entry.get("started_at") or "")
    if stamp.endswith("+00:00"):
        stamp = stamp[:-6] + "Z"
    decision = entry.get("decision") or "-"
    reason = entry.get("reason_code") or entry.get("human_readable_reason") or "-"
    regime = entry.get("market_regime") or "-"
    strategy = entry.get("selected_strategy") or "-"
    symbol = entry.get("symbol") or "-"
    account = entry.get("account_number") or "-"
    metrics = entry.get("metrics") or {}
    counts = ""
    if isinstance(metrics, dict) and ("m1_count" in metrics or "m15_count" in metrics):
        counts = f"  m1={metrics.get('m1_count', '-')} m15={metrics.get('m15_count', '-')}"
    return (
        f"{stamp}  {symbol}  acct={account}  decision={decision}  "
        f"reason={reason}  regime={regime}  strategy={strategy}{counts}"
    )


class EngineProcess:
    """Owns one checktrader child process and streams its stdout/stderr."""

    def __init__(self) -> None:
        self.proc: subprocess.Popen[str] | None = None
        self.mode: str | None = None
        self.started_at: float | None = None

    @property
    def running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    @property
    def pid(self) -> int | None:
        if self.proc is None or self.proc.poll() is not None:
            return None
        return self.proc.pid

    def start(self, *, mode: str, config_path: Path) -> None:
        if self.running:
            raise RuntimeError("Engine already running")

        env = os.environ.copy()
        src = str(SRC)
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = src if not existing else src + os.pathsep + existing
        env["PYTHONUNBUFFERED"] = "1"

        cmd = [
            sys.executable,
            "-m",
            "checktrader",
            "--config",
            str(config_path),
            "--mode",
            mode,
        ]
        self.proc = subprocess.Popen(
            cmd,
            cwd=str(ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        self.mode = mode
        self.started_at = time.time()

    def stop_soft(self, rt: Path) -> Path:
        return write_stop(rt)

    def stop_hard(self, timeout_s: float = 8.0) -> None:
        if self.proc is None:
            return
        if self.proc.poll() is None:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=timeout_s)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=3)
        self.proc = None
        self.mode = None
        self.started_at = None

    def poll_exit(self) -> int | None:
        if self.proc is None:
            return None
        code = self.proc.poll()
        if code is not None:
            self.mode = None
            self.started_at = None
        return code


def validate_live_config(config_path: Path) -> tuple[bool, str]:
    cmd = [sys.executable, str(ROOT / "tools" / "validate_config.py"), "--config", str(config_path), "--live"]
    completed = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace")
    if completed.returncode == 0:
        return True, (completed.stdout or "CONFIG VALID").strip()
    detail = (completed.stderr or completed.stdout or "live validation failed").strip()
    return False, detail


def run_deploy_mt4() -> tuple[int, str]:
    script = ROOT / "scripts" / "deploy_mt4.ps1"
    if not script.exists():
        return 1, f"Missing {script}"
    if os.name == "nt":
        cmd = [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
        ]
    else:
        return 1, "DEPLOY_MT4 is Windows-only (PowerShell)."
    completed = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = ((completed.stdout or "") + (completed.stderr or "")).strip()
    return completed.returncode, out or f"exit={completed.returncode}"
