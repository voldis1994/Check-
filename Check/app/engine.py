"""CHECK v5 engine — per-account points risk, no ATR."""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from app import bridge, clients, paths, settings as settings_mod
from app.strategy import evaluate, manage_sl


@dataclass
class Engine:
    on_log: Callable[[str], None] | None = None
    _thread: threading.Thread | None = None
    _stop: threading.Event = field(default_factory=threading.Event)
    running: bool = False
    mode: str = "off"
    last_reason: str = "—"
    _last_open_at: dict[str, float] = field(default_factory=dict)
    _pending_open: dict[str, str] = field(default_factory=dict)

    def _audit_path(self) -> Path:
        return paths.app_root() / "runtime" / "audit.jsonl"

    def _stop_path(self) -> Path:
        return paths.app_root() / "runtime" / "STOP"

    def log(self, msg: str) -> None:
        line = f"{datetime.now(UTC).strftime('%H:%M:%S')} {msg}"
        if self.on_log:
            self.on_log(line)
        try:
            paths.ensure_layout()
            with self._audit_path().open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({"ts": datetime.now(UTC).isoformat(), "msg": msg, "mode": self.mode}) + "\n")
        except OSError:
            pass

    def start(self, mode: str = "live") -> None:
        if self.running:
            return
        paths.ensure_layout()
        self._stop_path().unlink(missing_ok=True)
        self._stop.clear()
        self.mode = mode if mode in {"live", "paper"} else "live"
        self.running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        self.log(f"ENGINE START mode={self.mode}")

    def stop(self) -> None:
        paths.ensure_layout()
        self._stop_path().write_text("1\n", encoding="utf-8")
        self._stop.set()
        self.running = False
        self.mode = "off"
        self.log("ENGINE STOP")

    def _loop(self) -> None:
        while not self._stop.is_set():
            if self._stop_path().exists():
                self.running = False
                self.mode = "off"
                self.log("STOP file")
                break
            try:
                self._cycle()
            except Exception as exc:  # noqa: BLE001
                self.log(f"ERR {exc}")
            cfg = settings_mod.load()
            time.sleep(max(1.0, float(cfg.get("cycle_sec") or 3)))

    def _cycle(self) -> None:
        cfg = settings_mod.load()
        bridges = clients.all_bridges()
        if not bridges:
            self.last_reason = "NO_BRIDGE"
            return
        for b in bridges:
            self._cycle_bridge(b, cfg)

    def _key(self, b: Path) -> str:
        return str(b.resolve())

    def _resolve_account(self, b: Path, market: dict, status: dict | None) -> dict[str, Any]:
        acc = clients.account_for_bridge(b)
        if acc:
            return acc
        login = str((status or {}).get("account") or market.get("account") or "")
        if login:
            by_login = clients.account_by_login(login)
            if by_login:
                return by_login
        # fallback empty risk blocks opens (sl_points 0)
        return dict(clients.ACCOUNT_DEFAULTS)

    def _cycle_bridge(self, b: Path, cfg: dict[str, Any]) -> None:
        key = self._key(b)
        market = bridge.load_market(b)
        status = bridge.load_status(b)
        if not market:
            self.last_reason = "NO_MARKET"
            return
        age = bridge.age_s(b / "market" / "latest.json")
        if age is not None and age > 60:
            self.last_reason = f"STALE_{age:.0f}s"
            return

        symbol = str(market.get("symbol") or "")
        want = str(cfg.get("symbol") or "AUTO")
        if want not in {"", "AUTO"} and symbol and symbol.upper() != want.upper():
            return

        account = self._resolve_account(b, market, status)
        positions = (status or {}).get("positions") or []
        lot = float(account.get("lot") or 0.02)
        point = float(market.get("point") or 0.00001)
        digits = int(market.get("digits") or 5)

        pending_id = self._pending_open.get(key)
        if pending_id:
            ack = bridge.latest_ack(b, pending_id)
            if ack is not None:
                self.log(f"ACK {pending_id} ok={ack.get('ok')} ticket={ack.get('ticket')}")
                self._pending_open.pop(key, None)
            elif time.time() - self._last_open_at.get(key, 0) > 30:
                self._pending_open.pop(key, None)

        for pos in positions:
            if not isinstance(pos, dict):
                continue
            side = str(pos.get("side") or "")
            entry = float(pos.get("open") or 0)
            price = float(pos.get("price") or market.get("bid") or entry)
            sl = float(pos.get("sl") or 0)
            new_sl = manage_sl(side, entry, price, sl, point, account)
            if new_sl is None:
                continue
            payload = {
                "action": "MODIFY",
                "ticket": int(pos.get("ticket") or 0),
                "sl": round(new_sl, digits),
                "tp": float(pos.get("tp") or 0),
            }
            if self.mode == "paper":
                self.log(f"PAPER MODIFY {pos.get('ticket')} sl={new_sl:.{digits}f}")
            else:
                bridge.write_command(b, payload)
                self.log(f"MODIFY {pos.get('ticket')} sl={new_sl:.{digits}f}")
            self.last_reason = "TRAIL_BE"

        if positions:
            self._pending_open.pop(key, None)
            return

        if bridge.pending_commands(b) > 0 or key in self._pending_open:
            self.last_reason = "WAIT_CMD"
            return
        if time.time() - self._last_open_at.get(key, 0) < 15:
            self.last_reason = "COOLDOWN"
            return

        sig = evaluate(market, account, cfg)
        if sig is None:
            if float(account.get("sl_points") or 0) <= 0:
                self.last_reason = "SET_SL_POINTS"
            else:
                self.last_reason = "FLAT"
            return

        payload = {
            "action": "OPEN",
            "symbol": symbol,
            "side": sig.side,
            "lot": lot,
            "sl": round(sig.sl, digits),
            "tp": 0,
            "magic": int(cfg.get("magic") or 50001),
            "reason": sig.reason,
        }
        self._last_open_at[key] = time.time()
        if self.mode == "paper":
            self.last_reason = f"PAPER_{sig.reason}"
            self.log(
                f"PAPER OPEN {sig.side} {symbol} lot={lot} sl={sig.sl:.{digits}f} "
                f"sl_pts={account.get('sl_points')} ({sig.reason})"
            )
            return

        cmd_id = bridge.write_command(b, payload)
        self._pending_open[key] = cmd_id
        bridge.clear_old_acks(b)
        self.last_reason = sig.reason
        self.log(
            f"OPEN {sig.side} {symbol} lot={lot} sl={sig.sl:.{digits}f} "
            f"sl_pts={account.get('sl_points')} ({sig.reason}) id={cmd_id}"
        )
