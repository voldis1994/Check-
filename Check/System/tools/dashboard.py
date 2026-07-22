"""CHECK SYSTEM pro desktop console — dark signal deck (Tkinter, no browser)."""

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
    audit_activity,
    audit_day_stats,
    audit_file,
    clear_stop,
    collect_health,
    format_age,
    format_audit_line,
    load_config_json,
    load_equity_series,
    resolve_config,
    run_deploy_mt4,
    runtime_dir,
    validate_live_config,
    write_stop,
)

try:
    from checktrader.config.migrate import sync_system_json
except Exception:  # noqa: BLE001
    sync_system_json = None  # type: ignore[assignment]

# Dark pro console inspired by the operator mockup — CHECK SYSTEM brand, real data only.
C = {
    "bg": "#0B1220",
    "panel": "#121A2B",
    "panel2": "#172235",
    "line": "#243147",
    "ink": "#E8EEF7",
    "muted": "#8B9BB0",
    "blue": "#3B82F6",
    "blue_dim": "#1D4ED8",
    "green": "#22C55E",
    "green_dim": "#166534",
    "red": "#EF4444",
    "red_dim": "#7F1D1D",
    "amber": "#F59E0B",
    "cyan": "#22D3EE",
}


def _font(cands: list[str], size: int, weight: str = "normal") -> tuple:
    fam = set(tkfont.families())
    for name in cands:
        if name in fam:
            return (name, size, weight) if weight != "normal" else (name, size)
    return ("TkDefaultFont", size, weight) if weight != "normal" else ("TkDefaultFont", size)


def _money(v: float, currency: str = "") -> str:
    suffix = f" {currency}" if currency else ""
    return f"{v:,.2f}{suffix}"


class DashboardApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("CHECK SYSTEM")
        self.root.geometry("1440x900")
        self.root.minsize(1200, 760)
        self.root.configure(bg=C["bg"])

        self.f_brand = _font(["Bahnschrift", "Segoe UI Variable Display", "Calibri"], 20, "bold")
        self.f_h1 = _font(["Bahnschrift", "Segoe UI"], 28, "bold")
        self.f_h2 = _font(["Bahnschrift SemiBold", "Segoe UI"], 12, "bold")
        self.f_ui = _font(["Bahnschrift", "Segoe UI"], 10)
        self.f_ui_b = _font(["Bahnschrift SemiBold", "Segoe UI"], 10, "bold")
        self.f_metric = _font(["Bahnschrift", "Segoe UI"], 22, "bold")
        self.f_mono = _font(["Cascadia Mono", "Consolas"], 9)
        self.f_mono_b = _font(["Cascadia Mono", "Consolas"], 10, "bold")

        self.config_path = resolve_config()
        self.engine = EngineProcess()
        self.log_queue: queue.Queue[str] = queue.Queue()
        self._reader_thread: threading.Thread | None = None
        self._audit_offset = 0
        self._stopping = False
        self._selected_account: str | None = None
        self._page = "dashboard"
        self._pulse = False
        self._health = None
        self._nav_btns: dict[str, tk.Button] = {}

        self._build()
        self._tail_audit_init()
        self.refresh()
        self.root.after(450, self._tick)
        self.root.after(700, self._pulse_tick)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── chrome ──────────────────────────────────────────────────────────────
    def _build(self) -> None:
        shell = tk.Frame(self.root, bg=C["bg"])
        shell.pack(fill=tk.BOTH, expand=True)

        self.sidebar = tk.Frame(shell, bg=C["panel"], width=230)
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y)
        self.sidebar.pack_propagate(False)
        self._build_sidebar()

        main = tk.Frame(shell, bg=C["bg"])
        main.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.header = tk.Frame(main, bg=C["bg"], height=78)
        self.header.pack(fill=tk.X, padx=22, pady=(16, 8))
        self.header.pack_propagate(False)
        self._build_header()

        self.content = tk.Frame(main, bg=C["bg"])
        self.content.pack(fill=tk.BOTH, expand=True, padx=22, pady=(0, 8))

        self.footer = tk.Frame(main, bg=C["panel"], height=36)
        self.footer.pack(fill=tk.X, side=tk.BOTTOM)
        self.footer.pack_propagate(False)
        self._build_footer()

        self.pages: dict[str, tk.Frame] = {}
        self.pages["dashboard"] = self._page_dashboard(self.content)
        self.pages["trades"] = self._page_trades(self.content)
        self.pages["logs"] = self._page_logs(self.content)
        self._show_page("dashboard")

    def _build_sidebar(self) -> None:
        top = tk.Frame(self.sidebar, bg=C["panel"])
        top.pack(fill=tk.X, padx=16, pady=18)
        mark = tk.Canvas(top, width=34, height=34, bg=C["panel"], highlightthickness=0)
        mark.pack(side=tk.LEFT)
        mark.create_rectangle(2, 2, 32, 32, fill=C["blue"], outline="")
        mark.create_text(17, 17, text="C", fill="white", font=self.f_ui_b)
        tk.Label(top, text="CHECK", bg=C["panel"], fg=C["ink"], font=self.f_brand).pack(side=tk.LEFT, padx=(10, 0))

        tk.Label(self.sidebar, text="ACCOUNTS", bg=C["panel"], fg=C["muted"], font=self.f_ui_b, anchor="w").pack(
            fill=tk.X, padx=16, pady=(8, 4)
        )
        self.account_list = tk.Frame(self.sidebar, bg=C["panel"])
        self.account_list.pack(fill=tk.X, padx=10)

        tk.Frame(self.sidebar, bg=C["line"], height=1).pack(fill=tk.X, padx=16, pady=14)

        for key, label in (
            ("dashboard", "Dashboard"),
            ("trades", "Live Trades"),
            ("logs", "Activity Logs"),
        ):
            btn = tk.Button(
                self.sidebar,
                text=f"  {label}",
                anchor="w",
                command=lambda k=key: self._show_page(k),
                bg=C["panel"],
                fg=C["ink"],
                activebackground=C["panel2"],
                activeforeground=C["ink"],
                relief=tk.FLAT,
                bd=0,
                font=self.f_ui_b,
                padx=12,
                pady=10,
                cursor="hand2",
            )
            btn.pack(fill=tk.X, padx=8, pady=2)
            self._nav_btns[key] = btn

        bottom = tk.Frame(self.sidebar, bg=C["panel"])
        bottom.pack(side=tk.BOTTOM, fill=tk.X, padx=16, pady=16)
        tk.Label(bottom, text="CHECK SYSTEM v3", bg=C["panel"], fg=C["muted"], font=self.f_ui, anchor="w").pack(
            fill=tk.X
        )
        tk.Label(
            bottom, text="Python engine + MT4 bridge", bg=C["panel"], fg=C["muted"], font=self.f_ui, anchor="w"
        ).pack(fill=tk.X)

    def _build_header(self) -> None:
        left = tk.Frame(self.header, bg=C["bg"])
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.page_title = tk.Label(left, text="DASHBOARD", bg=C["bg"], fg=C["ink"], font=self.f_h1, anchor="w")
        self.page_title.pack(anchor=tk.W)
        self.page_sub = tk.Label(
            left,
            text="Real-time overview of CHECK SYSTEM across all MT4 accounts.",
            bg=C["bg"],
            fg=C["muted"],
            font=self.f_ui,
            anchor="w",
        )
        self.page_sub.pack(anchor=tk.W)

        right = tk.Frame(self.header, bg=C["bg"])
        right.pack(side=tk.RIGHT)
        self.badge_system = self._badge(right, "SYSTEM", "STOPPED", C["red"])
        self.badge_system.pack(side=tk.LEFT, padx=6)
        self.badge_engine = self._badge(right, "ENGINE", "IDLE", C["amber"])
        self.badge_engine.pack(side=tk.LEFT, padx=6)
        self.badge_bridge = self._badge(right, "BRIDGE", "—", C["muted"])
        self.badge_bridge.pack(side=tk.LEFT, padx=6)

    def _badge(self, parent: tk.Misc, title: str, value: str, color: str) -> tk.Frame:
        box = tk.Frame(parent, bg=C["panel2"], padx=10, pady=6)
        tk.Label(box, text=title, bg=C["panel2"], fg=C["muted"], font=self.f_ui).pack(anchor=tk.W)
        row = tk.Frame(box, bg=C["panel2"])
        row.pack(anchor=tk.W)
        dot = tk.Canvas(row, width=10, height=10, bg=C["panel2"], highlightthickness=0)
        dot.pack(side=tk.LEFT, padx=(0, 6))
        did = dot.create_oval(1, 1, 9, 9, fill=color, outline="")
        lab = tk.Label(row, text=value, bg=C["panel2"], fg=C["ink"], font=self.f_ui_b)
        lab.pack(side=tk.LEFT)
        box._dot = dot  # type: ignore[attr-defined]
        box._did = did  # type: ignore[attr-defined]
        box._lab = lab  # type: ignore[attr-defined]
        return box

    def _set_badge(self, badge: tk.Frame, value: str, color: str) -> None:
        badge._lab.configure(text=value)  # type: ignore[attr-defined]
        badge._dot.itemconfigure(badge._did, fill=color)  # type: ignore[attr-defined]

    def _build_footer(self) -> None:
        self.footer_var = tk.StringVar(value="Waiting for bridge…")
        tk.Label(
            self.footer,
            textvariable=self.footer_var,
            bg=C["panel"],
            fg=C["muted"],
            font=self.f_mono,
            anchor="w",
            padx=16,
        ).pack(fill=tk.BOTH, expand=True)

    def _panel(self, parent: tk.Misc, title: str | None = None) -> tk.Frame:
        wrap = tk.Frame(parent, bg=C["panel"], highlightbackground=C["line"], highlightthickness=1)
        if title:
            tk.Label(wrap, text=title, bg=C["panel"], fg=C["muted"], font=self.f_h2, anchor="w").pack(
                fill=tk.X, padx=14, pady=(12, 6)
            )
        return wrap

    def _metric_card(self, parent: tk.Misc, title: str) -> tuple[tk.Frame, tk.StringVar, tk.StringVar, tk.Label]:
        card = tk.Frame(parent, bg=C["panel"], highlightbackground=C["line"], highlightthickness=1)
        tk.Label(card, text=title, bg=C["panel"], fg=C["muted"], font=self.f_ui, anchor="w").pack(
            fill=tk.X, padx=14, pady=(12, 0)
        )
        val = tk.StringVar(value="—")
        sub = tk.StringVar(value="")
        tk.Label(card, textvariable=val, bg=C["panel"], fg=C["ink"], font=self.f_metric, anchor="w").pack(
            fill=tk.X, padx=14, pady=(4, 0)
        )
        sub_lab = tk.Label(card, textvariable=sub, bg=C["panel"], fg=C["muted"], font=self.f_ui, anchor="w")
        sub_lab.pack(fill=tk.X, padx=14, pady=(0, 12))
        return card, val, sub, sub_lab

    # ── pages ───────────────────────────────────────────────────────────────
    def _page_dashboard(self, parent: tk.Misc) -> tk.Frame:
        page = tk.Frame(parent, bg=C["bg"])

        metrics = tk.Frame(page, bg=C["bg"])
        metrics.pack(fill=tk.X, pady=(0, 12))
        self.m_balance = self._metric_card(metrics, "BALANCE")
        self.m_equity = self._metric_card(metrics, "EQUITY")
        self.m_float = self._metric_card(metrics, "FLOATING P/L")
        self.m_trades = self._metric_card(metrics, "TODAY ACTIONS")
        for i, card in enumerate((self.m_balance, self.m_equity, self.m_float, self.m_trades)):
            card[0].pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0 if i == 0 else 8, 0))

        mid = tk.Frame(page, bg=C["bg"])
        mid.pack(fill=tk.BOTH, expand=True, pady=(0, 12))

        left = self._panel(mid, "EQUITY CURVE")
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))
        self.equity_canvas = tk.Canvas(left, bg=C["panel"], highlightthickness=0, height=220)
        self.equity_canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 12))
        self.equity_canvas.bind("<Configure>", lambda _e: self._draw_equity())

        center = self._panel(mid, "ENGINE STATE")
        center.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=8)
        self.state_vars = {
            "symbol": tk.StringVar(value="—"),
            "regime": tk.StringVar(value="—"),
            "strategy": tk.StringVar(value="—"),
            "decision": tk.StringVar(value="—"),
            "reason": tk.StringVar(value="—"),
            "spread": tk.StringVar(value="—"),
            "accounts": tk.StringVar(value="—"),
        }
        body = tk.Frame(center, bg=C["panel"])
        body.pack(fill=tk.BOTH, expand=True, padx=14, pady=(0, 8))
        for key, label in (
            ("accounts", "Accounts"),
            ("symbol", "Symbol"),
            ("regime", "Market Regime"),
            ("strategy", "Strategy"),
            ("decision", "Last Decision"),
            ("reason", "Reason"),
            ("spread", "Spread"),
        ):
            row = tk.Frame(body, bg=C["panel"])
            row.pack(fill=tk.X, pady=3)
            tk.Label(row, text=label, width=14, anchor="w", bg=C["panel"], fg=C["muted"], font=self.f_ui).pack(
                side=tk.LEFT
            )
            tk.Label(
                row,
                textvariable=self.state_vars[key],
                anchor="w",
                bg=C["panel"],
                fg=C["ink"],
                font=self.f_mono_b,
                wraplength=220,
                justify=tk.LEFT,
            ).pack(side=tk.LEFT, fill=tk.X, expand=True)

        gauge_row = tk.Frame(center, bg=C["panel"])
        gauge_row.pack(fill=tk.X, padx=14, pady=(0, 12))
        self.health_canvas = tk.Canvas(gauge_row, width=96, height=96, bg=C["panel"], highlightthickness=0)
        self.health_canvas.pack(side=tk.LEFT)
        gauge_meta = tk.Frame(gauge_row, bg=C["panel"])
        gauge_meta.pack(side=tk.LEFT, padx=(12, 0), fill=tk.X, expand=True)
        tk.Label(gauge_meta, text="BRIDGE HEALTH", bg=C["panel"], fg=C["muted"], font=self.f_ui_b, anchor="w").pack(
            fill=tk.X
        )
        self.health_label = tk.StringVar(value="—")
        tk.Label(
            gauge_meta, textvariable=self.health_label, bg=C["panel"], fg=C["ink"], font=self.f_metric, anchor="w"
        ).pack(fill=tk.X)
        self.health_detail = tk.StringVar(value="Freshness of selected account bridge")
        tk.Label(
            gauge_meta, textvariable=self.health_detail, bg=C["panel"], fg=C["muted"], font=self.f_ui, anchor="w"
        ).pack(fill=tk.X)

        right = self._panel(mid, "QUICK ACTIONS")
        right.pack(side=tk.LEFT, fill=tk.Y, padx=(8, 0))
        actions = tk.Frame(right, bg=C["panel"])
        actions.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))
        self.btn_live = self._action(actions, "START LIVE", C["green"], C["green_dim"], self.start_live)
        self.btn_live.pack(fill=tk.X, pady=4)
        self.btn_paper = self._action(actions, "START PAPER", C["blue"], C["blue_dim"], self.start_paper)
        self.btn_paper.pack(fill=tk.X, pady=4)
        self.btn_stop = self._action(actions, "STOP", C["red"], C["red_dim"], self.stop_engine)
        self.btn_stop.pack(fill=tk.X, pady=4)
        self.btn_deploy = self._ghost(actions, "Deploy MT4", self.deploy_mt4)
        self.btn_deploy.pack(fill=tk.X, pady=(12, 4))
        self.btn_refresh = self._ghost(actions, "Refresh", self.refresh)
        self.btn_refresh.pack(fill=tk.X, pady=4)

        bottom = tk.Frame(page, bg=C["bg"])
        bottom.pack(fill=tk.BOTH, expand=True)
        trades = self._panel(bottom, "RECENT CYCLES")
        trades.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))
        self.recent_box = tk.Text(
            trades,
            height=10,
            bg=C["panel"],
            fg=C["ink"],
            font=self.f_mono,
            relief=tk.FLAT,
            highlightthickness=0,
            padx=12,
            pady=8,
        )
        self.recent_box.pack(fill=tk.BOTH, expand=True, padx=4, pady=(0, 8))
        self.recent_box.configure(state=tk.DISABLED)

        perf = self._panel(bottom, "OPEN POSITIONS")
        perf.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8, 0))
        self.pos_box = tk.Text(
            perf,
            height=10,
            bg=C["panel"],
            fg=C["ink"],
            font=self.f_mono,
            relief=tk.FLAT,
            highlightthickness=0,
            padx=12,
            pady=8,
        )
        self.pos_box.pack(fill=tk.BOTH, expand=True, padx=4, pady=(0, 8))
        self.pos_box.configure(state=tk.DISABLED)
        return page

    def _page_trades(self, parent: tk.Misc) -> tk.Frame:
        page = tk.Frame(parent, bg=C["bg"])
        panel = self._panel(page, "LIVE POSITIONS · ALL ACCOUNTS")
        panel.pack(fill=tk.BOTH, expand=True)
        self.trades_box = tk.Text(
            panel,
            bg=C["panel"],
            fg=C["ink"],
            font=self.f_mono,
            relief=tk.FLAT,
            highlightthickness=0,
            padx=14,
            pady=10,
        )
        self.trades_box.pack(fill=tk.BOTH, expand=True, padx=4, pady=(0, 10))
        self.trades_box.configure(state=tk.DISABLED)
        return page

    def _page_logs(self, parent: tk.Misc) -> tk.Frame:
        page = tk.Frame(parent, bg=C["bg"])
        panel = self._panel(page, "ACTIVITY FEED")
        panel.pack(fill=tk.BOTH, expand=True)
        wrap = tk.Frame(panel, bg=C["panel"])
        wrap.pack(fill=tk.BOTH, expand=True, padx=4, pady=(0, 10))
        self.activity = tk.Text(
            wrap,
            bg="#0A101A",
            fg=C["ink"],
            font=self.f_mono,
            relief=tk.FLAT,
            highlightthickness=0,
            padx=14,
            pady=10,
        )
        scroll = tk.Scrollbar(wrap, command=self.activity.yview)
        self.activity.configure(yscrollcommand=scroll.set, state=tk.DISABLED)
        self.activity.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.activity.tag_configure("cycle", foreground=C["amber"])
        self.activity.tag_configure("ok", foreground=C["green"])
        self.activity.tag_configure("err", foreground=C["red"])
        self.activity.tag_configure("dim", foreground=C["muted"])
        return page

    def _action(self, parent: tk.Misc, text: str, fg: str, bg: str, cmd) -> tk.Button:
        return tk.Button(
            parent,
            text=text,
            command=cmd,
            bg=bg,
            fg="white",
            activebackground=fg,
            activeforeground="white",
            font=self.f_ui_b,
            relief=tk.FLAT,
            bd=0,
            padx=12,
            pady=14,
            cursor="hand2",
        )

    def _ghost(self, parent: tk.Misc, text: str, cmd) -> tk.Button:
        return tk.Button(
            parent,
            text=text,
            command=cmd,
            bg=C["panel2"],
            fg=C["ink"],
            activebackground=C["line"],
            activeforeground=C["ink"],
            font=self.f_ui,
            relief=tk.FLAT,
            bd=0,
            padx=12,
            pady=10,
            cursor="hand2",
        )

    def _show_page(self, key: str) -> None:
        self._page = key
        titles = {
            "dashboard": ("DASHBOARD", "Real-time overview of CHECK SYSTEM across all MT4 accounts."),
            "trades": ("LIVE TRADES", "Open positions from every connected account."),
            "logs": ("ACTIVITY", "Engine + cycle audit stream."),
        }
        title, sub = titles[key]
        self.page_title.configure(text=title)
        self.page_sub.configure(text=sub)
        for _name, frame in self.pages.items():
            frame.pack_forget()
        self.pages[key].pack(fill=tk.BOTH, expand=True)
        for name, btn in self._nav_btns.items():
            btn.configure(bg=C["panel2"] if name == key else C["panel"], fg=C["blue"] if name == key else C["ink"])

    # ── data / draw ─────────────────────────────────────────────────────────
    def _selected_bridge(self):
        health = self._health
        if health is None or not health.bridges:
            return None
        if self._selected_account:
            for b in health.bridges:
                if b.account_id == self._selected_account:
                    return b
        return health.bridges[0]

    def _render_accounts(self) -> None:
        for child in self.account_list.winfo_children():
            child.destroy()
        health = self._health
        if health is None or not health.bridges:
            tk.Label(
                self.account_list, text="No MT4 bridge", bg=C["panel"], fg=C["red"], font=self.f_ui, anchor="w"
            ).pack(fill=tk.X, padx=6)
            return
        if self._selected_account is None:
            self._selected_account = health.bridges[0].account_id
        for bridge in health.bridges:
            active = bridge.account_id == self._selected_account
            row = tk.Frame(self.account_list, bg=C["panel2"] if active else C["panel"], padx=8, pady=8)
            row.pack(fill=tk.X, pady=3)
            age = format_age(bridge.market_age_s)
            live = "LIVE" if "STALE" not in age and age != "missing" else "STALE"
            color = C["green"] if live == "LIVE" else C["amber"]
            tk.Label(row, text=bridge.account_id, bg=row["bg"], fg=C["ink"], font=self.f_mono_b, anchor="w").pack(
                fill=tk.X
            )
            sub = tk.Frame(row, bg=row["bg"])
            sub.pack(fill=tk.X)
            tk.Label(sub, text=live, bg=row["bg"], fg=color, font=self.f_ui_b).pack(side=tk.LEFT)
            tk.Label(sub, text=f" · {bridge.symbol}", bg=row["bg"], fg=C["muted"], font=self.f_ui).pack(side=tk.LEFT)
            row.bind("<Button-1>", lambda _e, a=bridge.account_id: self._select_account(a))
            for child in row.winfo_children():
                child.bind("<Button-1>", lambda _e, a=bridge.account_id: self._select_account(a))

    def _select_account(self, account_id: str) -> None:
        self._selected_account = account_id
        self.refresh()

    def _draw_equity(self) -> None:
        canvas = self.equity_canvas
        canvas.delete("all")
        w = max(canvas.winfo_width(), 100)
        h = max(canvas.winfo_height(), 100)
        series = load_equity_series(self._selected_account, limit=100)
        pad = 16
        canvas.create_rectangle(0, 0, w, h, fill=C["panel"], outline="")
        if len(series) < 2:
            canvas.create_text(
                w // 2,
                h // 2,
                text="Collecting equity samples…\nKeep dashboard open while engine runs.",
                fill=C["muted"],
                font=self.f_ui,
                justify=tk.CENTER,
            )
            return
        values = [v for _, v in series]
        lo, hi = min(values), max(values)
        span = max(hi - lo, 1e-6)
        pts = []
        for i, (_, val) in enumerate(series):
            x = pad + (w - 2 * pad) * (i / (len(series) - 1))
            y = h - pad - (h - 2 * pad) * ((val - lo) / span)
            pts.extend([x, y])
        canvas.create_line(*pts, fill=C["blue"], width=2, smooth=True)
        canvas.create_oval(pts[-2] - 3, pts[-1] - 3, pts[-2] + 3, pts[-1] + 3, fill=C["cyan"], outline="")
        canvas.create_text(pad, 12, anchor="w", text=_money(values[-1]), fill=C["ink"], font=self.f_ui_b)

    def _draw_health_ring(self, pct: float, color: str) -> None:
        canvas = self.health_canvas
        canvas.delete("all")
        x0, y0, x1, y1 = 8, 8, 88, 88
        canvas.create_oval(x0, y0, x1, y1, outline=C["line"], width=8)
        extent = max(0.0, min(100.0, pct)) / 100.0 * 360.0
        if extent > 0:
            canvas.create_arc(x0, y0, x1, y1, start=90, extent=-extent, style=tk.ARC, outline=color, width=8)
        canvas.create_text(48, 48, text=f"{pct:.0f}%", fill=C["ink"], font=self.f_ui_b)

    def _set_text(self, widget: tk.Text, content: str) -> None:
        widget.configure(state=tk.NORMAL)
        widget.delete("1.0", tk.END)
        widget.insert(tk.END, content)
        widget.configure(state=tk.DISABLED)

    def _append_activity(self, line: str) -> None:
        tag = "dim"
        u = line.upper()
        if line.startswith("CYCLE"):
            tag = "cycle"
        elif "ERROR" in u or "FAIL" in u:
            tag = "err"
        elif "CTRL" in u or "OK" in u:
            tag = "ok"
        self.activity.configure(state=tk.NORMAL)
        self.activity.insert(tk.END, line.rstrip() + "\n", tag)
        total = int(float(self.activity.index("end-1c").split(".")[0]))
        if total > 2500:
            self.activity.delete("1.0", f"{total - 2500}.0")
        self.activity.see(tk.END)
        self.activity.configure(state=tk.DISABLED)

    # ── engine wiring ───────────────────────────────────────────────────────
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
                self._append_activity(f"AUDIT  {raw[:220]}")
                continue
            if isinstance(entry, dict):
                self._append_activity("CYCLE  " + format_audit_line(entry))

    def _start_reader(self) -> None:
        if self.engine.proc is None or self.engine.proc.stdout is None:
            return

        def _feed() -> None:
            assert self.engine.proc is not None and self.engine.proc.stdout is not None
            for line in self.engine.proc.stdout:
                self.log_queue.put(line.rstrip("\n"))
            self.log_queue.put(f"[engine exited code={self.engine.proc.poll()}]")

        threading.Thread(target=_feed, daemon=True).start()

    def _drain_logs(self) -> None:
        while True:
            try:
                line = self.log_queue.get_nowait()
            except queue.Empty:
                break
            self._append_activity("ENGINE " + line)

    def refresh(self) -> None:
        try:
            self.config_path = resolve_config(self.config_path)
            health = collect_health(self.config_path)
            self._health = health
            cfg = load_config_json(self.config_path)
            stats = audit_day_stats(audit_file(cfg))
            recent = audit_activity(audit_file(cfg), limit=25)
        except Exception as exc:  # noqa: BLE001
            self.footer_var.set(f"ERROR: {exc}")
            return

        self._render_accounts()
        bridge = self._selected_bridge()
        currency = bridge.currency if bridge else ""
        if bridge:
            self.m_balance[1].set(_money(bridge.balance, currency))
            self.m_balance[2].set(f"account {bridge.account_id}")
            self.m_balance[3].configure(fg=C["muted"])

            self.m_equity[1].set(_money(bridge.equity, currency))
            delta = bridge.equity - bridge.balance
            self.m_equity[2].set(f"vs balance {delta:+.2f}")
            self.m_equity[3].configure(fg=C["green"] if delta >= 0 else C["red"])

            self.m_float[1].set(_money(bridge.floating_pl, currency))
            self.m_float[2].set(f"{len(bridge.positions)} open positions")
            self.m_float[3].configure(fg=C["green"] if bridge.floating_pl >= 0 else C["red"])

            self.state_vars["symbol"].set(f"{bridge.symbol}  bid={bridge.bid} ask={bridge.ask}")
            self.state_vars["spread"].set("—" if bridge.spread is None else str(bridge.spread))
            age = bridge.market_age_s
            if age is None:
                pct, color = 0.0, C["red"]
                detail = "market export missing"
            elif age <= 5:
                pct, color = 100.0, C["green"]
                detail = format_age(age)
            elif age <= 30:
                pct, color = max(35.0, 100.0 - age * 2), C["cyan"]
                detail = format_age(age)
            else:
                pct, color = max(5.0, 40.0 - min(age, 120) / 4), C["amber"]
                detail = format_age(age)
            self._draw_health_ring(pct, color)
            self.health_label.set(f"{pct:.0f}%")
            self.health_detail.set(detail)
        else:
            for card in (self.m_balance, self.m_equity, self.m_float):
                card[1].set("—")
                card[2].set("")
                card[3].configure(fg=C["muted"])
            self.state_vars["symbol"].set("—")
            self.state_vars["spread"].set("—")
            self._draw_health_ring(0, C["red"])
            self.health_label.set("—")
            self.health_detail.set("No bridge")

        self.m_trades[1].set(str(stats["acted"]))
        self.m_trades[2].set(f"open {stats['opens']} · close {stats['closes']} · block {stats['blocks']}")
        self.m_trades[3].configure(fg=C["cyan"] if stats["acted"] else C["muted"])

        audit = health.last_audit or {}
        if bridge and bridge.account_id:
            # prefer selected account audit if present in recent
            for row in recent:
                if str(row.get("account_number") or "") == bridge.account_id:
                    audit = row
                    break
        self.state_vars["accounts"].set(f"{len(health.bridges)} connected")
        self.state_vars["regime"].set(str(audit.get("market_regime") or "—"))
        self.state_vars["strategy"].set(str(audit.get("selected_strategy") or "—"))
        self.state_vars["decision"].set(str(audit.get("decision") or "—"))
        self.state_vars["reason"].set(str(audit.get("reason_code") or audit.get("human_readable_reason") or "—"))

        # recent cycles text
        lines = []
        for row in recent[:12]:
            lines.append(format_audit_line(row))
        self._set_text(self.recent_box, "\n".join(lines) if lines else "No audit cycles yet.")

        # positions
        pos_lines = []
        trade_lines = []
        for b in health.bridges:
            if not b.positions:
                continue
            for p in b.positions:
                line = (
                    f"{b.account_id}  {p.symbol}  {p.side}  {p.lot:.2f}  "
                    f"@{p.open_price}  SL={p.stop_loss}  TP={p.take_profit}  "
                    f"P/L={p.profit:+.2f}"
                )
                pos_lines.append(line)
                trade_lines.append(line)
        self._set_text(self.pos_box, "\n".join(pos_lines) if pos_lines else "No open positions.")
        self._set_text(self.trades_box, "\n".join(trade_lines) if trade_lines else "No open positions.")

        running = self.engine.running
        mode = self.engine.mode or health.mode
        ages = [b.market_age_s for b in health.bridges if b.market_age_s is not None]
        fresh_n = sum(1 for a in ages if a <= 30)
        if running:
            self._set_badge(self.badge_system, "RUNNING", C["green"])
            self._set_badge(self.badge_engine, mode.upper(), C["cyan"] if mode == "live" else C["blue"])
        else:
            self._set_badge(self.badge_system, "STOPPED", C["red"])
            self._set_badge(self.badge_engine, "IDLE", C["amber"])
        self._set_badge(
            self.badge_bridge,
            f"{fresh_n}/{len(health.bridges)} FRESH" if health.bridges else "NONE",
            C["green"] if health.bridges and fresh_n == len(health.bridges) else C["amber"],
        )

        parts = []
        for b in health.bridges:
            parts.append(f"{b.account_id}:{format_age(b.market_age_s)}")
        self.footer_var.set(
            "  ·  ".join(
                [
                    f"mode={health.mode}",
                    f"trading={'on' if health.trading_enabled else 'off'}",
                    f"pid={self.engine.pid or '-'}",
                    " | ".join(parts) if parts else "no bridges",
                ]
            )
        )

        self._draw_equity()
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
                "Set config/system.json:\n  mode=live\n  trading_enabled=true\n\n" + detail,
            )
            self._append_activity(f"ERROR  {detail}")
            return
        if not messagebox.askyesno("Confirm LIVE", "Start LIVE on all discovered MT4 accounts?"):
            return
        self._start_mode("live")

    def _start_mode(self, mode: str) -> None:
        try:
            cfg = load_config_json(self.config_path)
            cleared = clear_stop(runtime_dir(cfg))
            self.engine.start(mode=mode, config_path=self.config_path)
            self._start_reader()
            msg = f"Started {mode}"
            if cleared:
                msg += " (cleared STOP_TRADING)"
            self._append_activity("CTRL   " + msg)
            self._show_page("logs")
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Start failed", str(exc))
            self._append_activity(f"ERROR  {exc}")
        self.refresh()

    def stop_engine(self) -> None:
        try:
            cfg = load_config_json(self.config_path)
            path = write_stop(runtime_dir(cfg))
            self._append_activity(f"CTRL   wrote {path.name}")
            if self.engine.running:
                self._stopping = True

                def _kill() -> None:
                    deadline = time.time() + 10
                    while time.time() < deadline and self.engine.running:
                        time.sleep(0.2)
                    if self.engine.running:
                        self.engine.stop_hard()
                        self.log_queue.put("[hard-stopped]")
                    self._stopping = False

                threading.Thread(target=_kill, daemon=True).start()
            self._append_activity("CTRL   stop requested")
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Stop failed", str(exc))
        self.refresh()

    def deploy_mt4(self) -> None:
        self._append_activity("CTRL   deploying MT4…")
        code, out = run_deploy_mt4()
        for line in out.splitlines() or [f"exit={code}"]:
            self._append_activity("DEPLOY " + line)
        if code != 0:
            messagebox.showerror("Deploy failed", out[-800:] or f"exit {code}")
        else:
            messagebox.showinfo("Deploy", "Done. Open EA from Data Folder and press F7.")
        self.refresh()

    def _tick(self) -> None:
        self._drain_logs()
        self._poll_audit()
        if (
            self.engine.proc is not None
            and not self.engine.running
            and not self._stopping
            and self.engine.poll_exit() is not None
        ):
            self.engine.proc = None
        self.refresh()
        self.root.after(1000, self._tick)

    def _pulse_tick(self) -> None:
        self._pulse = not self._pulse
        if self.engine.running:
            color = C["green"] if self._pulse else C["cyan"]
            self._set_badge(self.badge_system, "RUNNING", color)
        self.root.after(700, self._pulse_tick)

    def _on_close(self) -> None:
        if self.engine.running:
            if not messagebox.askyesno("Engine running", "Stop engine and exit?"):
                return
            with contextlib.suppress(Exception):
                write_stop(runtime_dir(load_config_json(self.config_path)))
            self.engine.stop_hard(timeout_s=5)
        self.root.destroy()


def main() -> int:
    try:
        cfg = resolve_config()
    except FileNotFoundError as exc:
        print(exc, file=sys.stderr)
        return 1
    if sync_system_json is not None and cfg.name == "system.json":
        with contextlib.suppress(Exception):
            sync_system_json(cfg)
    root = tk.Tk()
    DashboardApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
