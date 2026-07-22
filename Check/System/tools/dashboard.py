"""CHECK SYSTEM desktop control — modern ops console (Tkinter, no browser)."""

from __future__ import annotations

import contextlib
import json
import queue
import sys
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
from pathlib import Path
from tkinter import messagebox

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

from dashboard_core import (  # noqa: E402
    EngineProcess,
    audit_file,
    clear_stop,
    collect_health,
    format_age,
    format_audit_line,
    load_config_json,
    read_last_audits_by_account,
    resolve_config,
    run_deploy_mt4,
    runtime_dir,
    validate_live_config,
    write_stop,
)

# Visual system: Baltic signal deck — cool mist + forge teal + live copper.
# Avoid purple gradients, cream/terracotta, neon glow, Inter/Roboto.
THEME = {
    "bg0": "#D7E2EA",
    "bg1": "#EAF1F6",
    "ink": "#0B1320",
    "muted": "#5A6B7D",
    "line": "#B7C7D4",
    "brand": "#06281F",
    "teal": "#0B6E4F",
    "teal_soft": "#C8E8DA",
    "copper": "#B45309",
    "copper_soft": "#F6E1C8",
    "danger": "#9F1239",
    "danger_soft": "#FCE7EE",
    "feed": "#0E1624",
    "feed_fg": "#D7E0EA",
    "feed_dim": "#7B8B9C",
    "cycle": "#E8C07D",
    "ok": "#34D399",
    "warn": "#FBBF24",
}


def _pick_font(candidates: list[str], size: int, weight: str = "normal") -> tuple:
    available = set(tkfont.families())
    for name in candidates:
        if name in available:
            return (name, size, weight) if weight != "normal" else (name, size)
    return ("TkDefaultFont", size, weight) if weight != "normal" else ("TkDefaultFont", size)


class DashboardApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("CHECK SYSTEM")
        self.root.geometry("1280x800")
        self.root.minsize(1020, 680)
        self.root.configure(bg=THEME["bg0"])

        self.font_brand = _pick_font(["Bahnschrift", "Segoe UI Variable Display", "Calibri"], 42, "bold")
        self.font_sub = _pick_font(["Bahnschrift SemiLight", "Calibri", "Segoe UI"], 12)
        self.font_ui = _pick_font(["Bahnschrift", "Segoe UI", "Calibri"], 11)
        self.font_ui_b = _pick_font(["Bahnschrift SemiBold", "Bahnschrift", "Segoe UI"], 11, "bold")
        self.font_mono = _pick_font(["Cascadia Mono", "Consolas", "Courier New"], 10)
        self.font_mono_b = _pick_font(["Cascadia Mono", "Consolas", "Courier New"], 11, "bold")
        self.font_stat = _pick_font(["Bahnschrift", "Segoe UI"], 13, "bold")

        self.config_path = resolve_config()
        self.engine = EngineProcess()
        self.log_queue: queue.Queue[str] = queue.Queue()
        self._reader_thread: threading.Thread | None = None
        self._audit_offset = 0
        self._stopping = False
        self._stale_warned = False
        self._pulse_on = False
        self._brand_phase = 0
        self._account_widgets: list[dict[str, tk.Variable | tk.Label | tk.Frame]] = []

        self._build_ui()
        self._tail_audit_init()
        self.refresh_status()
        self.root.after(80, self._intro_motion)
        self.root.after(400, self._tick)
        self.root.after(700, self._pulse_tick)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self) -> None:
        shell = tk.Frame(self.root, bg=THEME["bg0"])
        shell.pack(fill=tk.BOTH, expand=True)

        # Atmospheric top band
        hero = tk.Frame(shell, bg=THEME["bg1"], height=148)
        hero.pack(fill=tk.X)
        hero.pack_propagate(False)
        mist = tk.Frame(hero, bg=THEME["line"], height=2)
        mist.pack(fill=tk.X, side=tk.BOTTOM)

        hero_inner = tk.Frame(hero, bg=THEME["bg1"])
        hero_inner.pack(fill=tk.BOTH, expand=True, padx=28, pady=18)

        left_hero = tk.Frame(hero_inner, bg=THEME["bg1"])
        left_hero.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.brand = tk.Label(
            left_hero,
            text="CHECK SYSTEM",
            bg=THEME["bg1"],
            fg=THEME["brand"],
            font=self.font_brand,
            anchor="w",
        )
        self.brand.pack(anchor=tk.W)
        self.brand_rule = tk.Frame(left_hero, bg=THEME["teal"], height=3, width=24)
        self.brand_rule.pack(anchor=tk.W, pady=(4, 8))

        tk.Label(
            left_hero,
            text="MT4 bridge · multi-account · open / manage / close",
            bg=THEME["bg1"],
            fg=THEME["muted"],
            font=self.font_sub,
            anchor="w",
        ).pack(anchor=tk.W)

        right_hero = tk.Frame(hero_inner, bg=THEME["bg1"])
        right_hero.pack(side=tk.RIGHT, anchor=tk.E)

        self.state_dot = tk.Canvas(right_hero, width=14, height=14, bg=THEME["bg1"], highlightthickness=0)
        self.state_dot.pack(side=tk.LEFT, padx=(0, 10))
        self._dot_id = self.state_dot.create_oval(2, 2, 12, 12, fill=THEME["danger"], outline="")

        self.state_label = tk.Label(
            right_hero,
            text="STOPPED",
            bg=THEME["bg1"],
            fg=THEME["danger"],
            font=self.font_stat,
            anchor="e",
        )
        self.state_label.pack(side=tk.LEFT)

        # Control rail — primary interactions only
        rail = tk.Frame(shell, bg=THEME["bg0"])
        rail.pack(fill=tk.X, padx=28, pady=(16, 8))

        self.btn_paper = self._action_btn(rail, "Start Paper", THEME["teal"], THEME["teal_soft"], self.start_paper)
        self.btn_paper.pack(side=tk.LEFT, padx=(0, 10))
        self.btn_live = self._action_btn(rail, "Start Live", THEME["copper"], THEME["copper_soft"], self.start_live)
        self.btn_live.pack(side=tk.LEFT, padx=(0, 10))
        self.btn_stop = self._action_btn(rail, "Stop", THEME["danger"], THEME["danger_soft"], self.stop_engine)
        self.btn_stop.pack(side=tk.LEFT, padx=(0, 10))
        self.btn_deploy = self._ghost_btn(rail, "Deploy MT4", self.deploy_mt4)
        self.btn_deploy.pack(side=tk.LEFT, padx=(0, 10))
        self.btn_refresh = self._ghost_btn(rail, "Refresh", self.refresh_status)
        self.btn_refresh.pack(side=tk.LEFT)

        self.meta_var = tk.StringVar(value="config · —")
        tk.Label(rail, textvariable=self.meta_var, bg=THEME["bg0"], fg=THEME["muted"], font=self.font_ui).pack(
            side=tk.RIGHT
        )

        # Body: accounts + activity
        body = tk.Frame(shell, bg=THEME["bg0"])
        body.pack(fill=tk.BOTH, expand=True, padx=28, pady=(8, 18))

        left = tk.Frame(body, bg=THEME["bg0"], width=380)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 18))
        left.pack_propagate(False)

        tk.Label(
            left,
            text="ACCOUNTS",
            bg=THEME["bg0"],
            fg=THEME["muted"],
            font=self.font_ui_b,
            anchor="w",
        ).pack(fill=tk.X, pady=(0, 8))

        self.accounts_host = tk.Frame(left, bg=THEME["bg0"])
        self.accounts_host.pack(fill=tk.BOTH, expand=True)

        self.signal_title = tk.Label(
            left,
            text="LAST SIGNAL",
            bg=THEME["bg0"],
            fg=THEME["muted"],
            font=self.font_ui_b,
            anchor="w",
        )
        self.signal_title.pack(fill=tk.X, pady=(16, 6))

        self.decision_var = tk.StringVar(value="—")
        self.reason_var = tk.StringVar(value="—")
        self.regime_var = tk.StringVar(value="—")
        self.strategy_var = tk.StringVar(value="—")

        for label, var in (
            ("Decision", self.decision_var),
            ("Reason", self.reason_var),
            ("Regime", self.regime_var),
            ("Strategy", self.strategy_var),
        ):
            row = tk.Frame(left, bg=THEME["bg0"])
            row.pack(fill=tk.X, pady=2)
            tk.Label(row, text=label, width=10, anchor="w", bg=THEME["bg0"], fg=THEME["muted"], font=self.font_ui).pack(
                side=tk.LEFT
            )
            tk.Label(
                row,
                textvariable=var,
                anchor="w",
                bg=THEME["bg0"],
                fg=THEME["ink"],
                font=self.font_mono_b,
                wraplength=250,
                justify=tk.LEFT,
            ).pack(side=tk.LEFT, fill=tk.X, expand=True)

        right = tk.Frame(body, bg=THEME["bg0"])
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        head = tk.Frame(right, bg=THEME["bg0"])
        head.pack(fill=tk.X, pady=(0, 8))
        tk.Label(head, text="ACTIVITY", bg=THEME["bg0"], fg=THEME["muted"], font=self.font_ui_b, anchor="w").pack(
            side=tk.LEFT
        )
        self.activity_hint = tk.Label(head, text="live feed", bg=THEME["bg0"], fg=THEME["muted"], font=self.font_ui)
        self.activity_hint.pack(side=tk.RIGHT)

        feed_wrap = tk.Frame(right, bg=THEME["feed"])
        feed_wrap.pack(fill=tk.BOTH, expand=True)
        self.activity = tk.Text(
            feed_wrap,
            wrap=tk.NONE,
            bg=THEME["feed"],
            fg=THEME["feed_fg"],
            insertbackground=THEME["feed_fg"],
            font=self.font_mono,
            relief=tk.FLAT,
            padx=16,
            pady=14,
            borderwidth=0,
            highlightthickness=0,
        )
        scroll = tk.Scrollbar(feed_wrap, orient=tk.VERTICAL, command=self.activity.yview, bg=THEME["feed"])
        self.activity.configure(yscrollcommand=scroll.set, state=tk.DISABLED)
        self.activity.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.activity.tag_configure("dim", foreground=THEME["feed_dim"])
        self.activity.tag_configure("cycle", foreground=THEME["cycle"])
        self.activity.tag_configure("ok", foreground=THEME["ok"])
        self.activity.tag_configure("warn", foreground=THEME["warn"])
        self.activity.tag_configure("err", foreground="#FB7185")
        self.activity.tag_configure("flash", background="#1F2A3C")

        foot = tk.Frame(shell, bg=THEME["bg0"])
        foot.pack(fill=tk.X, padx=28, pady=(0, 14))
        tk.Label(
            foot,
            text="Stop raksta STOP_TRADING. Live vajag AutoTrading + DLL. Abi konti iet katrā ciklā.",
            bg=THEME["bg0"],
            fg=THEME["muted"],
            font=self.font_ui,
            anchor="w",
        ).pack(fill=tk.X)

    def _action_btn(self, parent: tk.Misc, text: str, fg: str, bg: str, command) -> tk.Button:
        btn = tk.Button(
            parent,
            text=text,
            command=command,
            font=self.font_ui_b,
            fg=fg,
            bg=bg,
            activeforeground=fg,
            activebackground=bg,
            relief=tk.FLAT,
            padx=18,
            pady=10,
            cursor="hand2",
            bd=0,
            highlightthickness=0,
        )
        btn.bind("<Enter>", lambda _e, b=btn, c=fg: b.configure(bg=THEME["bg1"], highlightbackground=c))
        btn.bind("<Leave>", lambda _e, b=btn, c=bg: b.configure(bg=c))
        return btn

    def _ghost_btn(self, parent: tk.Misc, text: str, command) -> tk.Button:
        return tk.Button(
            parent,
            text=text,
            command=command,
            font=self.font_ui,
            fg=THEME["ink"],
            bg=THEME["bg1"],
            activeforeground=THEME["ink"],
            activebackground=THEME["bg1"],
            relief=tk.FLAT,
            padx=14,
            pady=10,
            cursor="hand2",
            bd=0,
            highlightthickness=1,
            highlightbackground=THEME["line"],
            highlightcolor=THEME["teal"],
        )

    def _clear_accounts(self) -> None:
        for child in self.accounts_host.winfo_children():
            child.destroy()
        self._account_widgets.clear()

    def _render_accounts(self, bridges, audits_by_acct: dict) -> None:
        self._clear_accounts()
        if not bridges:
            tk.Label(
                self.accounts_host,
                text="Nav bridge — palaid EA abos MT4",
                bg=THEME["bg0"],
                fg=THEME["danger"],
                font=self.font_ui,
                anchor="w",
            ).pack(fill=tk.X)
            return

        for bridge in bridges:
            block = tk.Frame(self.accounts_host, bg=THEME["bg0"])
            block.pack(fill=tk.X, pady=(0, 14))
            top = tk.Frame(block, bg=THEME["bg0"])
            top.pack(fill=tk.X)
            tk.Label(
                top,
                text=str(bridge.account_id),
                bg=THEME["bg0"],
                fg=THEME["ink"],
                font=self.font_mono_b,
                anchor="w",
            ).pack(side=tk.LEFT)
            age = format_age(bridge.market_age_s)
            age_fg = THEME["teal"] if "STALE" not in age and age != "missing" else THEME["copper"]
            if age == "missing":
                age_fg = THEME["danger"]
            tk.Label(top, text=age, bg=THEME["bg0"], fg=age_fg, font=self.font_ui_b, anchor="e").pack(side=tk.RIGHT)

            tk.Frame(block, bg=THEME["line"], height=1).pack(fill=tk.X, pady=(6, 6))

            audit = audits_by_acct.get(str(bridge.account_id)) or audits_by_acct.get("-") or {}
            detail = (
                f"{audit.get('decision') or '—'}  ·  {audit.get('reason_code') or '—'}\n"
                f"mkt {bridge.market_file or '—'}  ·  {bridge.path.name}"
            )
            tk.Label(
                block,
                text=detail,
                bg=THEME["bg0"],
                fg=THEME["muted"],
                font=self.font_mono,
                justify=tk.LEFT,
                anchor="w",
            ).pack(fill=tk.X)

    def _append_activity(self, line: str) -> None:
        tag = "dim"
        upper = line.upper()
        if line.startswith("CYCLE"):
            tag = "cycle"
        elif "ERROR" in upper or "FAILED" in upper:
            tag = "err"
        elif "WARN" in upper or "STALE" in upper:
            tag = "warn"
        elif "CTRL" in upper or "EXPORT OK" in upper or "cycle ok" in line.lower():
            tag = "ok"

        self.activity.configure(state=tk.NORMAL)
        start = self.activity.index(tk.END)
        self.activity.insert(tk.END, line.rstrip() + "\n", (tag, "flash"))
        end = self.activity.index(tk.END)
        total = int(float(self.activity.index("end-1c").split(".")[0]))
        if total > 2000:
            self.activity.delete("1.0", f"{total - 2000}.0")
        self.activity.see(tk.END)
        self.activity.configure(state=tk.DISABLED)
        # Motion: brief highlight on new lines
        self.root.after(220, lambda s=start, e=end: self._clear_flash(s, e))

    def _clear_flash(self, start: str, end: str) -> None:
        with contextlib.suppress(tk.TclError):
            self.activity.tag_remove("flash", start, end)

    def _intro_motion(self) -> None:
        # Brand underline grows in
        self._brand_phase += 1
        width = min(220, 24 + self._brand_phase * 18)
        self.brand_rule.configure(width=width)
        if width < 220:
            self.root.after(28, self._intro_motion)

    def _pulse_tick(self) -> None:
        running = self.engine.running
        if running:
            self._pulse_on = not self._pulse_on
            color = THEME["ok"] if self._pulse_on else THEME["teal"]
            mode = (self.engine.mode or "").lower()
            if mode == "live":
                color = THEME["copper"] if self._pulse_on else "#D97706"
            self.state_dot.itemconfigure(self._dot_id, fill=color)
        self.root.after(650, self._pulse_tick)

    def _tail_audit_init(self) -> None:
        path = audit_file(load_config_json(self.config_path) if self.config_path.exists() else None)
        if path.exists():
            self._audit_offset = path.stat().st_size

    def _poll_audit(self) -> None:
        try:
            data = load_config_json(self.config_path)
        except Exception:  # noqa: BLE001
            return
        path = audit_file(data)
        if not path.exists():
            return
        size = path.stat().st_size
        if size < self._audit_offset:
            self._audit_offset = 0
        if size == self._audit_offset:
            return
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            handle.seek(self._audit_offset)
            chunk = handle.read()
            self._audit_offset = handle.tell()
        for raw in chunk.splitlines():
            raw = raw.strip()
            if not raw:
                continue
            try:
                entry = json.loads(raw)
            except Exception:  # noqa: BLE001
                self._append_activity(f"AUDIT  {raw[:240]}")
                continue
            if isinstance(entry, dict):
                self._append_activity("CYCLE  " + format_audit_line(entry))

    def _start_reader(self) -> None:
        if self.engine.proc is None or self.engine.proc.stdout is None:
            return

        def _feed() -> None:
            assert self.engine.proc is not None
            assert self.engine.proc.stdout is not None
            for line in self.engine.proc.stdout:
                self.log_queue.put(line.rstrip("\n"))
            code = self.engine.proc.poll()
            self.log_queue.put(f"[engine exited code={code}]")

        self._reader_thread = threading.Thread(target=_feed, daemon=True)
        self._reader_thread.start()

    def _drain_logs(self) -> None:
        while True:
            try:
                line = self.log_queue.get_nowait()
            except queue.Empty:
                break
            self._append_activity("ENGINE " + line)

    def refresh_status(self) -> None:
        try:
            self.config_path = resolve_config(self.config_path)
            health = collect_health(self.config_path)
            audits_by_acct = read_last_audits_by_account(audit_file(load_config_json(self.config_path)))
        except Exception as exc:  # noqa: BLE001
            self.state_label.configure(text=f"ERROR · {exc}", fg=THEME["danger"])
            return

        running = self.engine.running
        pid = self.engine.pid
        engine_mode = self.engine.mode or health.mode
        ages = [b.market_age_s for b in health.bridges if b.market_age_s is not None]
        stale = bool(ages) and all(a > 30 for a in ages)
        partial_stale = bool(ages) and any(a > 30 for a in ages) and not stale
        n_accounts = len(health.bridges)

        try:
            config_display = str(self.config_path.relative_to(ROOT))
        except ValueError:
            config_display = str(self.config_path)
        self.meta_var.set(
            f"{config_display}  ·  mode={health.mode}  ·  trading={'on' if health.trading_enabled else 'off'}"
        )

        if running and stale:
            self.state_label.configure(text=f"LIVE STALE · {n_accounts} accounts · pid {pid}", fg=THEME["copper"])
            self.state_dot.itemconfigure(self._dot_id, fill=THEME["copper"])
        elif running and partial_stale:
            self.state_label.configure(
                text=f"{engine_mode.upper()} · {n_accounts} accounts · daži STALE · pid {pid}",
                fg=THEME["copper"],
            )
        elif running:
            color = THEME["copper"] if engine_mode == "live" else THEME["teal"]
            self.state_label.configure(
                text=f"{engine_mode.upper()} · {n_accounts} accounts · pid {pid}",
                fg=color,
            )
            self.state_dot.itemconfigure(self._dot_id, fill=color)
        else:
            text = "STOPPED · STOP_TRADING" if health.stop_present else "STOPPED"
            self.state_label.configure(text=text, fg=THEME["danger"])
            self.state_dot.itemconfigure(self._dot_id, fill=THEME["danger"])

        self._render_accounts(health.bridges, audits_by_acct)

        audit = health.last_audit or {}
        self.decision_var.set(str(audit.get("decision") or "—"))
        self.reason_var.set(str(audit.get("reason_code") or audit.get("human_readable_reason") or "—"))
        self.regime_var.set(str(audit.get("market_regime") or "—"))
        self.strategy_var.set(str(audit.get("selected_strategy") or "—"))

        if stale and not self._stale_warned:
            self._stale_warned = True
            self._append_activity("WARN   Bridge STALE — pārbaudi abus MT4 EA / EXPORT OK")
        if not stale:
            self._stale_warned = False

        state = tk.DISABLED if running else tk.NORMAL
        self.btn_paper.configure(state=state)
        self.btn_live.configure(state=state)
        self.btn_stop.configure(state=tk.NORMAL)

    def start_paper(self) -> None:
        self._start_mode("paper")

    def start_live(self) -> None:
        ok, detail = validate_live_config(self.config_path)
        if not ok:
            messagebox.showerror(
                "Live config invalid",
                "Live start blocked.\n\n"
                "Set in config/system.json:\n"
                '  runtime.mode = "live"\n'
                "  runtime.trading_enabled = true\n\n"
                f"{detail}",
            )
            self._append_activity(f"ERROR  live validation failed: {detail}")
            return
        if not messagebox.askyesno(
            "Confirm LIVE",
            "Start LIVE trading on all discovered accounts?\n\n"
            "Confirm MT4 AutoTrading ON, DLL imports allowed,\n"
            "EA on M1 for each account.",
        ):
            return
        self._start_mode("live")

    def _start_mode(self, mode: str) -> None:
        try:
            cfg = load_config_json(self.config_path)
            rt = runtime_dir(cfg)
            cleared = clear_stop(rt)
            self.engine.start(mode=mode, config_path=self.config_path)
            self._start_reader()
            msg = f"Started {mode} with {self.config_path.name}"
            if cleared:
                msg += " (cleared STOP_TRADING)"
            self._append_activity("CTRL   " + msg)
            # Motion: reset and replay brand underline
            self._brand_phase = 0
            self.brand_rule.configure(width=24)
            self.root.after(20, self._intro_motion)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Start failed", str(exc))
            self._append_activity(f"ERROR  start failed: {exc}")
        self.refresh_status()

    def stop_engine(self) -> None:
        try:
            cfg = load_config_json(self.config_path)
            rt = runtime_dir(cfg)
            path = write_stop(rt)
            self._append_activity(f"CTRL   wrote {path.name}")
            if self.engine.running:
                self._stopping = True

                def _wait_then_kill() -> None:
                    deadline = time.time() + 10
                    while time.time() < deadline and self.engine.running:
                        time.sleep(0.2)
                    if self.engine.running:
                        self.engine.stop_hard()
                        self.log_queue.put("[hard-stopped process]")
                    self._stopping = False

                threading.Thread(target=_wait_then_kill, daemon=True).start()
            self._append_activity("CTRL   stop requested — also disable AutoTrading in MT4 for live")
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Stop failed", str(exc))
        self.refresh_status()

    def deploy_mt4(self) -> None:
        self._append_activity("CTRL   deploying MT4 files…")
        code, out = run_deploy_mt4()
        for line in out.splitlines() or [f"exit={code}"]:
            self._append_activity("DEPLOY " + line)
        if code != 0:
            messagebox.showerror("Deploy failed", out[-1000:] or f"exit {code}")
        else:
            messagebox.showinfo("Deploy", "MT4 files deployed.\nOpen EA from Data Folder and press F7.")
        self.refresh_status()

    def _tick(self) -> None:
        self._drain_logs()
        self._poll_audit()
        if self.engine.proc is not None and not self.engine.running and not self._stopping:
            code = self.engine.poll_exit()
            if code is not None:
                self.engine.proc = None
        self.refresh_status()
        self.root.after(500, self._tick)

    def _on_close(self) -> None:
        if self.engine.running:
            if not messagebox.askyesno("Engine running", "Engine is still running. Stop and exit?"):
                return
            try:
                cfg = load_config_json(self.config_path)
                write_stop(runtime_dir(cfg))
            except Exception:  # noqa: BLE001
                pass
            self.engine.stop_hard(timeout_s=5)
        self.root.destroy()


def main() -> int:
    try:
        resolve_config()
    except FileNotFoundError as exc:
        print(exc, file=sys.stderr)
        return 1

    root = tk.Tk()
    DashboardApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
