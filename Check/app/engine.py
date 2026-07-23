"""CHECK engine — risk, automation, copier, journal, loss streak."""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Callable

from app import analytics, automation, bridge, clients, copier, paths, settings as settings_mod
from app.risk import as_bool, as_float, block_new_entries, merge_account_risk
from app.strategy import evaluate, manage_sl


@dataclass
class Engine:
    on_log: Callable[[str], None] | None = None
    on_alert: Callable[[str], None] | None = None
    _thread: threading.Thread | None = None
    _stop: threading.Event = field(default_factory=threading.Event)
    running: bool = False
    mode: str = "off"
    last_reason: str = "—"
    last_signal: str = ""
    _last_open_at: dict[str, float] = field(default_factory=dict)
    _pending_open: dict[str, str] = field(default_factory=dict)
    _day_equity: dict[str, tuple[str, float]] = field(default_factory=dict)
    _seen_pos: dict[str, dict[int, dict[str, Any]]] = field(default_factory=dict)

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

    def alert(self, msg: str) -> None:
        self.log(f"ALERT {msg}")
        if self.on_alert:
            self.on_alert(msg)

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
        auto = automation.load()
        now = datetime.now()
        if not automation.within_trading_hours(auto, now.weekday(), now.hour):
            self.last_reason = "OUT_OF_HOURS"
            return
        if as_bool(auto.get("news_filter_enabled"), False):
            # hard gate when ON (user enables only when needed)
            self.last_reason = "NEWS_FILTER"
            # still manage positions / automations below for open trades
            manage_only = True
        else:
            manage_only = False

        bridges = clients.all_bridges()
        if not bridges:
            self.last_reason = "NO_BRIDGE"
            return

        total_open = 0
        snapshots: list[tuple[Path, dict, dict | None, dict]] = []
        for b in bridges:
            market = bridge.load_market(b)
            status = bridge.load_status(b)
            if not market:
                continue
            account = self._resolve_account(b, market, status)
            positions = (status or {}).get("positions") or []
            if isinstance(positions, list):
                total_open += len(positions)
            snapshots.append((b, market, status, account))

        # portfolio close-all automations
        self._run_portfolio_automations(snapshots, auto)

        for b, market, status, account in snapshots:
            self._cycle_bridge(b, cfg, market, status, account, total_open, manage_only=manage_only)

    def _run_portfolio_automations(self, snapshots, auto: dict[str, Any]) -> None:
        float_pl = 0.0
        tickets: list[tuple[Path, int]] = []
        for b, _m, status, _a in snapshots:
            for pos in (status or {}).get("positions") or []:
                if isinstance(pos, dict):
                    float_pl += float(pos.get("profit") or 0)
                    tickets.append((b, int(pos.get("ticket") or 0)))
        if as_bool(auto.get("close_all_profit_enabled"), False):
            lim = as_float(auto.get("close_all_profit"), 0)
            if lim > 0 and float_pl >= lim:
                self._close_all(tickets, f"AUTO_PROFIT_{float_pl:.2f}")
                return
        if as_bool(auto.get("close_all_loss_enabled"), False):
            lim = as_float(auto.get("close_all_loss"), 0)
            if lim > 0 and float_pl <= -lim:
                self._close_all(tickets, f"AUTO_LOSS_{float_pl:.2f}")

    def _close_all(self, tickets: list[tuple[Path, int]], reason: str) -> None:
        for b, ticket in tickets:
            if ticket <= 0:
                continue
            payload = {"action": "CLOSE", "ticket": ticket, "reason": reason}
            if self.mode == "paper":
                self.log(f"PAPER CLOSE {ticket} ({reason})")
            else:
                bridge.write_command(b, payload)
                self.log(f"CLOSE {ticket} ({reason})")
        self.alert(reason)

    def _key(self, b: Path) -> str:
        return str(b.resolve())

    def _resolve_account(self, b: Path, market: dict, status: dict | None) -> dict[str, Any]:
        acc = clients.account_for_bridge(b)
        if acc:
            return merge_account_risk(acc)
        login = str((status or {}).get("account") or market.get("account") or "")
        if login:
            by_login = clients.account_by_login(login)
            if by_login:
                return merge_account_risk(by_login)
        return merge_account_risk(None)

    def _daily_pl(self, key: str, equity: float | None) -> float | None:
        if equity is None:
            return None
        today = date.today().isoformat()
        prev = self._day_equity.get(key)
        if prev is None or prev[0] != today:
            self._day_equity[key] = (today, equity)
            return 0.0
        return equity - prev[1]

    def _track_closes(self, key: str, account: dict[str, Any], positions: list) -> None:
        cur: dict[int, dict[str, Any]] = {}
        for pos in positions:
            if isinstance(pos, dict) and pos.get("ticket"):
                cur[int(pos["ticket"])] = pos
        prev = self._seen_pos.get(key, {})
        for ticket, pos in prev.items():
            if ticket not in cur:
                pl = float(pos.get("profit") or 0)
                analytics.append_journal(
                    {
                        "type": "CLOSE",
                        "ticket": ticket,
                        "symbol": pos.get("symbol"),
                        "side": pos.get("side"),
                        "pl": pl,
                        "ts": datetime.now(UTC).isoformat(),
                        "account": account.get("id") or account.get("login"),
                    }
                )
                cid = str(account.get("id") or "")
                if cid:
                    losses = int(account.get("consecutive_losses") or 0)
                    if pl < 0:
                        losses += 1
                    else:
                        losses = 0
                    try:
                        clients.update_risk(cid, consecutive_losses=losses)
                        account["consecutive_losses"] = losses
                        auto = automation.load()
                        if as_bool(auto.get("reduce_lot_after_loss_enabled"), False) and pl < 0:
                            clients.update_risk(cid, lot=as_float(auto.get("reduce_lot_to"), 0.01))
                    except ValueError:
                        pass
                self.alert(f"Trade closed ticket={ticket} pl={pl:.2f}")
        self._seen_pos[key] = cur

    def _copy_open(self, master_account: dict[str, Any], payload: dict[str, Any]) -> None:
        cfg = copier.load()
        if not as_bool(cfg.get("enabled"), False):
            return
        master_id = str(cfg.get("master_id") or "")
        if not master_id or str(master_account.get("id") or "") != master_id:
            return
        side = str(payload.get("side") or "BUY")
        if as_bool(cfg.get("reverse"), False):
            side = "SELL" if side == "BUY" else "BUY"
        for fol in cfg.get("followers") or []:
            if not isinstance(fol, dict) or not as_bool(fol.get("enabled"), False):
                continue
            fid = str(fol.get("id") or "")
            full = clients.read(fid)
            if not full:
                continue
            b = Path(str(full.get("bridge") or ""))
            if not b.is_dir():
                mt4 = Path(str(full.get("mt4_dir") or ""))
                b = mt4 / "MQL4" / "Files" / "CHECK"
            if not b.is_dir():
                continue
            lot = as_float(fol.get("lot"), as_float(full.get("lot"), 0.02))
            copy = dict(payload)
            copy["side"] = side
            copy["lot"] = lot
            if not as_bool(cfg.get("copy_sl"), True):
                copy["sl"] = 0
            if self.mode == "paper":
                self.log(f"PAPER COPY → {fid} {side} lot={lot}")
            else:
                bridge.write_command(b, copy)
                self.log(f"COPY → {fid} {side} lot={lot}")

    def _cycle_bridge(
        self,
        b: Path,
        cfg: dict[str, Any],
        market: dict[str, Any],
        status: dict[str, Any] | None,
        account: dict[str, Any],
        total_open: int,
        *,
        manage_only: bool = False,
    ) -> None:
        key = self._key(b)
        age = bridge.age_s(b / "market" / "latest.json")
        if age is not None and age > 60:
            self.last_reason = f"STALE_{age:.0f}s"
            return

        symbol = str(market.get("symbol") or "")
        want = str(cfg.get("symbol") or "AUTO")
        if want not in {"", "AUTO"} and symbol and symbol.upper() != want.upper():
            return

        positions = (status or {}).get("positions") or []
        if not isinstance(positions, list):
            positions = []
        self._track_closes(key, account, positions)

        lot = as_float(account.get("lot"), 0.02)
        point = float(market.get("point") or 0.00001)
        digits = int(market.get("digits") or 5)
        try:
            spread_pts = float(market["spread"]) if market.get("spread") is not None else None
        except (TypeError, ValueError, KeyError):
            spread_pts = None
        equity = as_float(status.get("equity"), 0) if status and status.get("equity") is not None else None
        daily_pl = self._daily_pl(key, equity)
        losses = int(account.get("consecutive_losses") or 0)

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

        if manage_only:
            return
        if bridge.pending_commands(b) > 0 or key in self._pending_open:
            self.last_reason = "WAIT_CMD"
            return
        if time.time() - self._last_open_at.get(key, 0) < 15:
            self.last_reason = "COOLDOWN"
            return

        blocked = block_new_entries(
            account=account,
            global_cfg=cfg,
            positions=positions,
            spread_points=spread_pts,
            equity=equity,
            daily_pl=daily_pl,
            consecutive_losses=losses,
            total_open=total_open,
        )
        if blocked:
            self.last_reason = blocked
            return

        sig = evaluate(market, account, cfg)
        if sig is None:
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
        self.last_signal = sig.reason
        analytics.append_journal(
            {
                "type": "OPEN",
                "side": sig.side,
                "symbol": symbol,
                "lot": lot,
                "sl": sig.sl,
                "reason": sig.reason,
                "ts": datetime.now(UTC).isoformat(),
                "account": account.get("id") or account.get("login"),
                "mode": self.mode,
            }
        )
        if self.mode == "paper":
            self.last_reason = f"PAPER_{sig.reason}"
            self.log(f"PAPER OPEN {sig.side} {symbol} lot={lot} sl={sig.sl:.{digits}f} ({sig.reason})")
            self._copy_open(account, payload)
            return

        cmd_id = bridge.write_command(b, payload)
        self._pending_open[key] = cmd_id
        bridge.clear_old_acks(b)
        self.last_reason = sig.reason
        self.log(f"OPEN {sig.side} {symbol} lot={lot} sl={sig.sl:.{digits}f} ({sig.reason}) id={cmd_id}")
        self._copy_open(account, payload)
        self.alert(f"Opened {sig.side} {symbol}")
