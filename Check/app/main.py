"""CHECK — full Nexus-style command center (1:1 layout)."""

from __future__ import annotations

import contextlib
import os
import sys
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any

from app import paths

ROOT = paths.app_root()
os.chdir(ROOT)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import alerts, analytics, automation, bridge, clients, copier, settings as settings_mod  # noqa: E402
from app.engine import Engine  # noqa: E402
from app.risk import ACCOUNT_RISK_DEFAULTS, as_bool  # noqa: E402
from app.ui.chart import CandleChart  # noqa: E402
from app.ui.theme import C, Toggle, font, pill_btn  # noqa: E402

NAV = (
    ("dashboard", "Dashboard"),
    ("accounts", "Accounts"),
    ("strategies", "Strategies"),
    ("copier", "Trade Copier"),
    ("market", "Market Analysis"),
    ("automation", "Automation"),
    ("risk", "Risk Manager"),
    ("reports", "Reports"),
    ("alerts", "Alerts"),
    ("journal", "Journal"),
    ("settings", "Settings"),
)


class App:
    def __init__(self, root: tk.Tk) -> None:
        paths.ensure_layout()
        if not (ROOT / "config" / "settings.json").exists():
            settings_mod.save(settings_mod.load())

        self.root = root
        self.root.title("CHECK")
        self.root.geometry("1540x960")
        self.root.minsize(1280, 820)
        self.root.configure(bg=C["bg"])

        self.f_brand = font(["Bahnschrift SemiBold", "Bahnschrift", "Segoe UI"], 20, "bold")
        self.f_h = font(["Bahnschrift", "Segoe UI"], 11, "bold")
        self.f_ui = font(["Segoe UI", "Bahnschrift"], 9)
        self.f_mono = font(["Cascadia Mono", "Consolas"], 9)
        self.f_kpi = font(["Bahnschrift", "Segoe UI"], 15, "bold")

        self.engine = Engine(on_log=self._push_log, on_alert=self._push_alert)
        self._log_lines: list[str] = []
        self._alert_lines: list[str] = []
        self._page = "dashboard"
        self.selected_cid: str | None = None
        self.kpi: dict[str, tk.StringVar] = {}
        self.live_var = tk.BooleanVar(value=False)
        self._nav: dict[str, tk.Label] = {}
        self._toggles: dict[str, tk.BooleanVar] = {}
        self._nums: dict[str, tk.StringVar] = {}
        self._g_toggles: dict[str, tk.BooleanVar] = {}
        self._g_nums: dict[str, tk.StringVar] = {}
        self._strat: dict[str, tk.BooleanVar] = {}
        self._auto_t: dict[str, tk.BooleanVar] = {}
        self._auto_n: dict[str, tk.StringVar] = {}
        self._alert_t: dict[str, tk.BooleanVar] = {}
        self._alert_n: dict[str, tk.StringVar] = {}
        self._copier_t: dict[str, tk.BooleanVar] = {}
        self._copier_n: dict[str, tk.StringVar] = {}
        self._hours: dict[str, dict[str, Any]] = {}
        self.ticker_vars: dict[str, tk.StringVar] = {}

        self._style()
        self._build()
        self.refresh()
        self.root.after(800, self._tick)
        self.root.protocol("WM_DELETE_WINDOW", self._close)

    def _style(self) -> None:
        st = ttk.Style()
        with contextlib.suppress(tk.TclError):
            st.theme_use("clam")
        st.configure("N.Treeview", background=C["panel"], foreground=C["ink"], fieldbackground=C["panel"], rowheight=26, font=self.f_mono)
        st.configure("N.Treeview.Heading", background=C["panel2"], foreground=C["violet2"], font=self.f_ui)
        st.map("N.Treeview", background=[("selected", C["line"])])

    def _card(self, parent, title: str) -> tk.Frame:
        wrap = tk.Frame(parent, bg=C["panel"], highlightthickness=1, highlightbackground=C["line"])
        tk.Label(wrap, text=title, bg=C["panel"], fg=C["violet2"], font=self.f_h).pack(anchor="w", padx=10, pady=(8, 2))
        return wrap

    def _build(self) -> None:
        shell = tk.Frame(self.root, bg=C["bg"])
        shell.pack(fill=tk.BOTH, expand=True)

        side = tk.Frame(shell, bg=C["sidebar"], width=188)
        side.pack(side=tk.LEFT, fill=tk.Y)
        side.pack_propagate(False)
        tk.Label(side, text="CHECK", bg=C["sidebar"], fg=C["violet2"], font=self.f_brand).pack(anchor="w", padx=16, pady=(18, 0))
        tk.Label(side, text="NEXUS DESK", bg=C["sidebar"], fg=C["mute"], font=self.f_ui).pack(anchor="w", padx=16, pady=(0, 14))
        for key, label in NAV:
            lab = tk.Label(side, text=f"  {label}", bg=C["sidebar"], fg=C["mute"], font=self.f_ui, anchor="w", cursor="hand2", pady=9)
            lab.pack(fill=tk.X, padx=6)
            lab.bind("<Button-1>", lambda _e, k=key: self._show(k))
            self._nav[key] = lab

        main = tk.Frame(shell, bg=C["bg"])
        main.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        head = tk.Frame(main, bg=C["panel"], height=72)
        head.pack(fill=tk.X, padx=12, pady=(12, 6))
        head.pack_propagate(False)
        kpi_row = tk.Frame(head, bg=C["panel"])
        kpi_row.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=6, pady=6)
        for key, title, col in (
            ("equity", "Total Equity", C["ink"]),
            ("daily", "Daily P/L", C["ok"]),
            ("pos", "Open Positions", C["violet2"]),
            ("win", "Win Rate", C["ice"]),
            ("pf", "Profit Factor", C["warn"]),
        ):
            self.kpi[key] = tk.StringVar(value="—")
            cell = tk.Frame(kpi_row, bg=C["panel"])
            cell.pack(side=tk.LEFT, padx=10)
            tk.Label(cell, text=title, bg=C["panel"], fg=C["mute"], font=self.f_ui).pack(anchor="w")
            tk.Label(cell, textvariable=self.kpi[key], bg=C["panel"], fg=col, font=self.f_kpi).pack(anchor="w")
        live = tk.Frame(head, bg=C["panel"])
        live.pack(side=tk.RIGHT, padx=14)
        tk.Label(live, text="Live Trading", bg=C["panel"], fg=C["mute"], font=self.f_ui).pack(anchor="e")
        Toggle(live, self.live_var, on_change=self._toggle_live).pack(anchor="e", pady=2)
        paper = tk.Frame(head, bg=C["panel"])
        paper.pack(side=tk.RIGHT, padx=8)
        pill_btn(paper, "PAPER", C["ice"], lambda: self._start_mode("paper")).pack()

        # ticker strip
        tick = tk.Frame(main, bg=C["panel2"], height=36)
        tick.pack(fill=tk.X, padx=12, pady=(0, 6))
        tick.pack_propagate(False)
        self.ticker_host = tk.Frame(tick, bg=C["panel2"])
        self.ticker_host.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        self.body = tk.Frame(main, bg=C["bg"])
        self.body.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 6))
        self.pages = {k: getattr(self, f"_page_{k}")(self.body) for k, _ in NAV}

        foot = tk.Frame(main, bg=C["panel"])
        foot.pack(fill=tk.X, side=tk.BOTTOM, padx=12, pady=(0, 8))
        self.foot = tk.Label(foot, text="", bg=C["panel"], fg=C["mute"], font=self.f_mono, anchor="w")
        self.foot.pack(fill=tk.X, padx=8, pady=5)
        self._show("dashboard")

    # ----- pages -----
    def _page_dashboard(self, parent) -> tk.Frame:
        f = tk.Frame(parent, bg=C["bg"])
        top = tk.Frame(f, bg=C["bg"])
        top.pack(fill=tk.BOTH, expand=True)

        left = self._card(top, "ACCOUNTS OVERVIEW")
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))
        left.configure(width=220)
        left.pack_propagate(False)
        self.acc_cards = tk.Frame(left, bg=C["panel"])
        self.acc_cards.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        mid = self._card(top, "MARKET CHART  ·  M1")
        mid.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))
        self.chart = CandleChart(mid, height=280)
        self.chart.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        self.chart_meta = tk.StringVar(value="—")
        tk.Label(mid, textvariable=self.chart_meta, bg=C["panel"], fg=C["mute"], font=self.f_mono).pack(anchor="w", padx=10, pady=(0, 6))

        right = self._card(top, "STRATEGY MODES")
        right.pack(side=tk.LEFT, fill=tk.Y)
        right.configure(width=240)
        right.pack_propagate(False)
        cfg = settings_mod.load()
        box = tk.Frame(right, bg=C["panel"])
        box.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        for key, label in (("trend", "TREND"), ("range", "RANGE"), ("breakout", "BREAKOUT"), ("scalping", "SCALPING")):
            var = tk.BooleanVar(value=bool(cfg.get(key, key in {"trend", "breakout"})))
            self._strat[key] = var
            Toggle(box, var, label, on_change=self._save_strategies_quiet).pack(anchor="w", pady=6)
        tk.Label(box, text="Hard SL/BE/Trail → Risk Manager\n(per account points / $)", bg=C["panel"], fg=C["mute"], font=self.f_ui, justify="left").pack(anchor="w", pady=10)

        bot = tk.Frame(f, bg=C["bg"])
        bot.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
        pos_card = self._card(bot, "OPEN POSITIONS")
        pos_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))
        self.pos = ttk.Treeview(pos_card, columns=("symbol", "account", "type", "size", "sl", "price", "pl", "strategy", "time"), show="headings", style="N.Treeview", height=8)
        for c, t, w in (("symbol", "Symbol", 80), ("account", "Account", 80), ("type", "Type", 50), ("size", "Size", 50), ("sl", "SL", 80), ("price", "Price", 80), ("pl", "P/L", 70), ("strategy", "Strategy", 90), ("time", "Time", 70)):
            self.pos.heading(c, text=t)
            self.pos.column(c, width=w, anchor="w")
        self.pos.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        log_card = self._card(bot, "ENGINE LOG")
        log_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.log = tk.Text(log_card, bg=C["panel2"], fg=C["ink"], height=8, relief=tk.FLAT, font=self.f_mono)
        self.log.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        self.log.configure(state=tk.DISABLED)
        return f

    def _page_accounts(self, parent) -> tk.Frame:
        f = tk.Frame(parent, bg=C["bg"])
        head = tk.Frame(f, bg=C["bg"])
        head.pack(fill=tk.X)
        tk.Label(head, text="MULTI-ACCOUNT MANAGEMENT", bg=C["bg"], fg=C["violet2"], font=self.f_h).pack(side=tk.LEFT)
        pill_btn(head, "+ ADD ACCOUNT", C["ok"], self._add_account).pack(side=tk.RIGHT)
        self.acc_table = ttk.Treeview(f, columns=("id", "login", "server", "lot", "sl", "equity", "status", "pl"), show="headings", style="N.Treeview", height=16)
        for c, t, w in (("id", "ID", 90), ("login", "Login", 90), ("server", "Server", 120), ("lot", "Lot", 50), ("sl", "SL pts", 60), ("equity", "Equity", 90), ("status", "Status", 80), ("pl", "P/L today", 80)):
            self.acc_table.heading(c, text=t)
            self.acc_table.column(c, width=w, anchor="w")
        self.acc_table.pack(fill=tk.BOTH, expand=True, pady=8)
        self.acc_table.bind("<<TreeviewSelect>>", self._on_acc_select)
        row = tk.Frame(f, bg=C["bg"])
        row.pack(fill=tk.X)
        for text, cmd, col in (("LAUNCH MT4", self._launch_selected, C["ice"]), ("EDIT RISK", lambda: self._show("risk"), C["warn"]), ("DELETE", self._delete_selected, C["bad"])):
            pill_btn(row, text, col, cmd).pack(side=tk.LEFT, padx=4)
        return f

    def _page_strategies(self, parent) -> tk.Frame:
        f = tk.Frame(parent, bg=C["bg"])
        tk.Label(f, text="STRATEGIES  ·  M1", bg=C["bg"], fg=C["violet2"], font=self.f_h).pack(anchor="w")
        modes = self._card(f, "MODES")
        modes.pack(fill=tk.X, pady=8)
        row = tk.Frame(modes, bg=C["panel"])
        row.pack(anchor="w", padx=10, pady=10)
        cfg = settings_mod.load()
        for key, label in (("trend", "TREND"), ("range", "RANGE"), ("breakout", "BREAKOUT"), ("scalping", "SCALPING")):
            if key not in self._strat:
                self._strat[key] = tk.BooleanVar(value=bool(cfg.get(key, key in {"trend", "breakout"})))
            Toggle(row, self._strat[key], label).pack(side=tk.LEFT, padx=12)
        filt = self._card(f, "FILTERS (informational)")
        filt.pack(fill=tk.X, pady=8)
        for txt in ("EMA Trend (20 / 50)", "Breakout box 20 bars", "Range fade box 30 bars", "Scalp body 8–40 points"):
            tk.Label(filt, text="• " + txt, bg=C["panel"], fg=C["ink"], font=self.f_ui).pack(anchor="w", padx=12, pady=3)
        pill_btn(f, "SAVE STRATEGIES", C["violet2"], self._save_strategies).pack(anchor="w", pady=8)
        return f

    def _page_copier(self, parent) -> tk.Frame:
        f = tk.Frame(parent, bg=C["bg"])
        tk.Label(f, text="TRADE COPIER", bg=C["bg"], fg=C["violet2"], font=self.f_h).pack(anchor="w")
        cfg = copier.load()
        card = self._card(f, "MASTER → FOLLOWERS  (hard lot per follower)")
        card.pack(fill=tk.BOTH, expand=True, pady=8)
        self._copier_t["enabled"] = tk.BooleanVar(value=bool(cfg.get("enabled")))
        Toggle(card, self._copier_t["enabled"], "Copier enabled").pack(anchor="w", padx=10, pady=6)
        self._copier_n["master_id"] = tk.StringVar(value=str(cfg.get("master_id") or ""))
        r = tk.Frame(card, bg=C["panel"])
        r.pack(fill=tk.X, padx=10, pady=4)
        tk.Label(r, text="Master account id", bg=C["panel"], fg=C["mute"], width=22, anchor="w").pack(side=tk.LEFT)
        tk.Entry(r, textvariable=self._copier_n["master_id"], bg=C["panel2"], fg=C["ink"], relief=tk.FLAT, width=18).pack(side=tk.LEFT)
        for key, label, default in (("copy_sl", "Copy SL", True), ("copy_pending", "Copy pending", False), ("reverse", "Reverse copy", False)):
            self._copier_t[key] = tk.BooleanVar(value=bool(cfg.get(key, default)))
            Toggle(card, self._copier_t[key], label).pack(anchor="w", padx=10, pady=4)
        tk.Label(card, text="Followers (id:lot  one per line)  e.g.  boss2:0.02", bg=C["panel"], fg=C["mute"]).pack(anchor="w", padx=10, pady=(10, 2))
        self.copier_followers = tk.Text(card, bg=C["panel2"], fg=C["ink"], height=8, relief=tk.FLAT, font=self.f_mono)
        self.copier_followers.pack(fill=tk.X, padx=10, pady=6)
        lines = []
        for fol in cfg.get("followers") or []:
            if isinstance(fol, dict):
                en = "1" if fol.get("enabled", True) else "0"
                lines.append(f"{fol.get('id')}:{fol.get('lot', 0.02)}:{en}")
        self.copier_followers.insert("1.0", "\n".join(lines))
        pill_btn(f, "SAVE COPIER", C["violet2"], self._save_copier).pack(anchor="w")
        return f

    def _page_market(self, parent) -> tk.Frame:
        f = tk.Frame(parent, bg=C["bg"])
        tk.Label(f, text="MARKET ANALYSIS", bg=C["bg"], fg=C["violet2"], font=self.f_h).pack(anchor="w")
        self.market_chart = CandleChart(f, height=360)
        self.market_chart.pack(fill=tk.BOTH, expand=True, pady=8)
        self.market_info = tk.StringVar(value="—")
        tk.Label(f, textvariable=self.market_info, bg=C["bg"], fg=C["mute"], font=self.f_mono).pack(anchor="w")
        return f

    def _page_automation(self, parent) -> tk.Frame:
        f = tk.Frame(parent, bg=C["bg"])
        tk.Label(f, text="AUTOMATION", bg=C["bg"], fg=C["violet2"], font=self.f_h).pack(anchor="w")
        cfg = automation.load()
        card = self._card(f, "RULES  ·  hard $ / lot / hours")
        card.pack(fill=tk.BOTH, expand=True, pady=8)
        specs = (
            ("close_all_profit_enabled", "Close all at profit", "close_all_profit", "Profit $"),
            ("close_all_loss_enabled", "Close all at loss", "close_all_loss", "Loss $"),
            ("reduce_lot_after_loss_enabled", "Reduce lot after loss", "reduce_lot_to", "Lot after loss"),
            ("news_filter_enabled", "News filter (blocks new entries when ON)", None, None),
            ("trading_hours_enabled", "Trading hours filter", None, None),
        )
        for tkey, tlabel, nkey, nlabel in specs:
            self._auto_t[tkey] = tk.BooleanVar(value=bool(cfg.get(tkey)))
            Toggle(card, self._auto_t[tkey], tlabel).pack(anchor="w", padx=10, pady=4)
            if nkey:
                self._auto_n[nkey] = tk.StringVar(value=str(cfg.get(nkey, "")))
                r = tk.Frame(card, bg=C["panel"])
                r.pack(fill=tk.X, padx=28, pady=2)
                tk.Label(r, text=nlabel, bg=C["panel"], fg=C["mute"], width=18, anchor="w").pack(side=tk.LEFT)
                tk.Entry(r, textvariable=self._auto_n[nkey], bg=C["panel2"], fg=C["ink"], relief=tk.FLAT, width=12).pack(side=tk.LEFT)

        hours = self._card(f, "TRADING HOURS  (0–23 hard hours, Mon=0)")
        hours.pack(fill=tk.X, pady=8)
        days = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
        grid = tk.Frame(hours, bg=C["panel"])
        grid.pack(fill=tk.X, padx=8, pady=8)
        hcfg = cfg.get("hours") or {}
        for i, name in enumerate(days):
            day = hcfg.get(str(i), {"on": i < 5, "start": 0, "end": 23})
            on = tk.BooleanVar(value=bool(day.get("on", True)))
            st = tk.StringVar(value=str(day.get("start", 0)))
            en = tk.StringVar(value=str(day.get("end", 23)))
            self._hours[str(i)] = {"on": on, "start": st, "end": en}
            row = tk.Frame(grid, bg=C["panel"])
            row.pack(fill=tk.X, pady=2)
            tk.Label(row, text=name, bg=C["panel"], fg=C["ink"], width=5, anchor="w").pack(side=tk.LEFT)
            Toggle(row, on, "").pack(side=tk.LEFT)
            tk.Label(row, text="start", bg=C["panel"], fg=C["mute"]).pack(side=tk.LEFT, padx=(8, 2))
            tk.Entry(row, textvariable=st, width=4, bg=C["panel2"], fg=C["ink"], relief=tk.FLAT).pack(side=tk.LEFT)
            tk.Label(row, text="end", bg=C["panel"], fg=C["mute"]).pack(side=tk.LEFT, padx=(8, 2))
            tk.Entry(row, textvariable=en, width=4, bg=C["panel2"], fg=C["ink"], relief=tk.FLAT).pack(side=tk.LEFT)
        pill_btn(f, "SAVE AUTOMATION", C["violet2"], self._save_automation).pack(anchor="w", pady=8)
        return f

    def _num_row(self, parent, key: str, label: str, store: dict, default: str = "0") -> None:
        row = tk.Frame(parent, bg=C["panel"])
        row.pack(fill=tk.X, padx=10, pady=3)
        tk.Label(row, text=label, bg=C["panel"], fg=C["mute"], font=self.f_ui, width=26, anchor="w").pack(side=tk.LEFT)
        var = tk.StringVar(value=default)
        store[key] = var
        tk.Entry(row, textvariable=var, bg=C["panel2"], fg=C["ink"], insertbackground=C["violet"], relief=tk.FLAT, width=12, font=self.f_mono).pack(side=tk.LEFT)

    def _toggle_row(self, parent, key: str, label: str, store: dict, default: bool = False) -> None:
        row = tk.Frame(parent, bg=C["panel"])
        row.pack(fill=tk.X, padx=10, pady=3)
        var = tk.BooleanVar(value=default)
        store[key] = var
        Toggle(row, var, label).pack(side=tk.LEFT)

    def _page_risk(self, parent) -> tk.Frame:
        f = tk.Frame(parent, bg=C["bg"])
        top = tk.Frame(f, bg=C["bg"])
        top.pack(fill=tk.X)
        tk.Label(top, text="RISK MANAGER", bg=C["bg"], fg=C["violet2"], font=self.f_h).pack(side=tk.LEFT)
        self.risk_title = tk.StringVar(value="(select account in Accounts)")
        tk.Label(top, textvariable=self.risk_title, bg=C["bg"], fg=C["mute"], font=self.f_ui).pack(side=tk.LEFT, padx=10)
        grid = tk.Frame(f, bg=C["bg"])
        grid.pack(fill=tk.BOTH, expand=True, pady=8)

        left = self._card(grid, "ACCOUNT POINTS")
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))
        self._num_row(left, "lot", "Lot", self._nums, "0.02")
        self._num_row(left, "sl_points", "SL (points)", self._nums, "150")
        self._toggle_row(left, "be_enabled", "Breakeven", self._toggles, True)
        self._num_row(left, "be_start_points", "BE start (points)", self._nums, "50")
        self._num_row(left, "be_offset_points", "BE offset (points)", self._nums, "5")
        self._toggle_row(left, "trail_enabled", "Trailing", self._toggles, True)
        self._num_row(left, "trail_start_points", "Trail start (points)", self._nums, "80")
        self._num_row(left, "trail_lock_points", "Trail lock (points)", self._nums, "40")

        mid = self._card(grid, "PROTECTION ON/OFF + HARD $")
        mid.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))
        self._toggle_row(mid, "equity_protection_enabled", "Equity Protection", self._toggles, False)
        self._num_row(mid, "equity_floor", "Equity floor ($)", self._nums, "0")
        self._toggle_row(mid, "daily_loss_limit_enabled", "Daily Loss Limit", self._toggles, False)
        self._num_row(mid, "daily_loss_limit", "Daily loss max ($)", self._nums, "200")
        self._toggle_row(mid, "profit_lock_enabled", "Profit Lock", self._toggles, False)
        self._num_row(mid, "profit_lock", "Profit lock ($)", self._nums, "300")
        self._toggle_row(mid, "auto_stop_enabled", "Auto Stop after losses", self._toggles, False)
        self._num_row(mid, "auto_stop_after_losses", "Losses count", self._nums, "3")
        self._toggle_row(mid, "spread_filter_enabled", "Spread Filter", self._toggles, True)
        self._num_row(mid, "max_spread_points", "Max spread (points)", self._nums, "40")
        self._toggle_row(mid, "max_open_trades_enabled", "Max Open Trades", self._toggles, True)
        self._num_row(mid, "max_open_trades", "Max open (count)", self._nums, "1")

        right = self._card(grid, "PORTFOLIO HARD CAPS")
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        cfg = settings_mod.load()
        self._toggle_row(right, "max_total_open_enabled", "Max total open", self._g_toggles, bool(cfg.get("max_total_open_enabled")))
        self._num_row(right, "max_total_open", "Max total open", self._g_nums, str(cfg.get("max_total_open", 10)))
        self._toggle_row(right, "global_daily_loss_enabled", "Global daily loss", self._g_toggles, bool(cfg.get("global_daily_loss_enabled")))
        self._num_row(right, "global_daily_loss", "Global daily loss ($)", self._g_nums, str(cfg.get("global_daily_loss", 1000)))
        self._toggle_row(right, "global_equity_floor_enabled", "Global equity floor", self._g_toggles, bool(cfg.get("global_equity_floor_enabled")))
        self._num_row(right, "global_equity_floor", "Global equity floor ($)", self._g_nums, str(cfg.get("global_equity_floor", 0)))

        tk.Label(f, text="No percentages — only points / $ / count. OFF = function disabled.", bg=C["bg"], fg=C["mute"], font=self.f_ui).pack(anchor="w")
        pill_btn(f, "SAVE RISK", C["violet2"], self._save_risk).pack(anchor="w", pady=8)
        return f

    def _page_reports(self, parent) -> tk.Frame:
        f = tk.Frame(parent, bg=C["bg"])
        tk.Label(f, text="REPORTS / ANALYTICS", bg=C["bg"], fg=C["violet2"], font=self.f_h).pack(anchor="w")
        self.report_text = tk.Text(f, bg=C["panel"], fg=C["ink"], relief=tk.FLAT, font=self.f_mono, height=28)
        self.report_text.pack(fill=tk.BOTH, expand=True, pady=8)
        return f

    def _page_alerts(self, parent) -> tk.Frame:
        f = tk.Frame(parent, bg=C["bg"])
        tk.Label(f, text="ALERTS", bg=C["bg"], fg=C["violet2"], font=self.f_h).pack(anchor="w")
        cfg = alerts.load()
        card = self._card(f, "NOTIFICATION RULES  ·  hard $ thresholds")
        card.pack(fill=tk.X, pady=8)
        for tkey, label, nkey, nlabel in (
            ("equity_drawdown_enabled", "Equity drawdown", "equity_drawdown", "Drawdown $"),
            ("daily_profit_target_enabled", "Daily profit target", "daily_profit_target", "Target $"),
            ("trade_opened_enabled", "Trade opened", None, None),
            ("trade_closed_enabled", "Trade closed", None, None),
            ("email_enabled", "Email (flag only)", None, None),
            ("push_enabled", "Push (flag only)", None, None),
        ):
            self._alert_t[tkey] = tk.BooleanVar(value=bool(cfg.get(tkey)))
            Toggle(card, self._alert_t[tkey], label).pack(anchor="w", padx=10, pady=4)
            if nkey:
                self._alert_n[nkey] = tk.StringVar(value=str(cfg.get(nkey, "")))
                r = tk.Frame(card, bg=C["panel"])
                r.pack(fill=tk.X, padx=28, pady=2)
                tk.Label(r, text=nlabel, bg=C["panel"], fg=C["mute"], width=14, anchor="w").pack(side=tk.LEFT)
                tk.Entry(r, textvariable=self._alert_n[nkey], bg=C["panel2"], fg=C["ink"], relief=tk.FLAT, width=12).pack(side=tk.LEFT)
        live = self._card(f, "LIVE ALERT FEED")
        live.pack(fill=tk.BOTH, expand=True, pady=8)
        self.alert_feed = tk.Text(live, bg=C["panel2"], fg=C["ink"], height=12, relief=tk.FLAT, font=self.f_mono)
        self.alert_feed.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        self.alert_feed.configure(state=tk.DISABLED)
        pill_btn(f, "SAVE ALERTS", C["violet2"], self._save_alerts).pack(anchor="w")
        return f

    def _page_journal(self, parent) -> tk.Frame:
        f = tk.Frame(parent, bg=C["bg"])
        tk.Label(f, text="JOURNAL", bg=C["bg"], fg=C["violet2"], font=self.f_h).pack(anchor="w")
        self.journal = ttk.Treeview(f, columns=("ts", "type", "account", "symbol", "side", "pl", "reason"), show="headings", style="N.Treeview", height=22)
        for c, t, w in (("ts", "Time", 160), ("type", "Type", 70), ("account", "Account", 80), ("symbol", "Symbol", 80), ("side", "Side", 50), ("pl", "P/L", 70), ("reason", "Reason", 120)):
            self.journal.heading(c, text=t)
            self.journal.column(c, width=w, anchor="w")
        self.journal.pack(fill=tk.BOTH, expand=True, pady=8)
        return f

    def _page_settings(self, parent) -> tk.Frame:
        f = tk.Frame(parent, bg=C["bg"])
        tk.Label(f, text="SETTINGS", bg=C["bg"], fg=C["violet2"], font=self.f_h).pack(anchor="w")
        cfg = settings_mod.load()
        card = self._card(f, "GLOBAL")
        card.pack(fill=tk.X, pady=8)
        self._g_misc: dict[str, tk.StringVar] = {}
        for key, label, default in (("symbol", "Symbol", str(cfg.get("symbol", "AUTO"))), ("cycle_sec", "Cycle sec", str(cfg.get("cycle_sec", 3))), ("magic", "Magic", str(cfg.get("magic", 50001)))):
            self._num_row(card, key, label, self._g_misc, default)
        st = clients.setup_status()
        tip = f"Template MT4: {'OK' if st['template_ok'] else 'MISSING — put MT4 in template\\\\ then SETUP.bat'}"
        if st.get("master"):
            tip += f"\n{st['master']}"
        tk.Label(f, text=tip, bg=C["bg"], fg=C["mute"], font=self.f_mono, justify="left").pack(anchor="w", pady=8)
        pill_btn(f, "SAVE SETTINGS", C["violet2"], self._save_settings).pack(anchor="w")
        return f

    # ----- navigation / actions -----
    def _show(self, key: str) -> None:
        self._page = key
        for name, fr in self.pages.items():
            if name == key:
                fr.pack(fill=tk.BOTH, expand=True)
            else:
                fr.pack_forget()
        for k, lab in self._nav.items():
            lab.configure(fg=C["violet2"] if k == key else C["mute"], bg=C["panel2"] if k == key else C["sidebar"])
        if key == "accounts":
            self._render_accounts_table()
        if key == "risk" and self.selected_cid:
            self._load_risk(self.selected_cid)
        if key in {"dashboard", "market", "reports", "journal", "alerts"}:
            self.refresh()

    def _push_log(self, line: str) -> None:
        self._log_lines.append(line)
        self._log_lines = self._log_lines[-250:]

    def _push_alert(self, line: str) -> None:
        self._alert_lines.append(f"{line}")
        self._alert_lines = self._alert_lines[-100:]

    def _toggle_live(self) -> None:
        if self.live_var.get():
            st = clients.setup_status()
            if not st["template_ok"]:
                self.live_var.set(False)
                messagebox.showwarning("SETUP", "Put MT4 in template\\ then run SETUP.bat")
                return
            self.engine.start("live")
        else:
            self.engine.stop()
        self.refresh()

    def _start_mode(self, mode: str) -> None:
        self.engine.start(mode)
        self.live_var.set(mode == "live")
        self.refresh()

    def _save_strategies(self) -> None:
        data = settings_mod.load()
        for k, var in self._strat.items():
            data[k] = bool(var.get())
        settings_mod.save(data)
        messagebox.showinfo("Strategies", "Saved.")

    def _save_strategies_quiet(self) -> None:
        data = settings_mod.load()
        for k, var in self._strat.items():
            data[k] = bool(var.get())
        settings_mod.save(data)

    def _save_settings(self) -> None:
        data = settings_mod.load()
        data["symbol"] = self._g_misc["symbol"].get().strip() or "AUTO"
        data["cycle_sec"] = float(self._g_misc["cycle_sec"].get().replace(",", ".") or 3)
        data["magic"] = int(float(self._g_misc["magic"].get() or 50001))
        settings_mod.save(data)
        messagebox.showinfo("Settings", "Saved.")

    def _save_copier(self) -> None:
        followers = []
        for line in self.copier_followers.get("1.0", tk.END).splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(":")
            if len(parts) < 2:
                continue
            followers.append({"id": parts[0].strip(), "lot": float(parts[1].replace(",", ".")), "enabled": parts[2].strip() != "0" if len(parts) > 2 else True})
        copier.save({
            "enabled": bool(self._copier_t["enabled"].get()),
            "master_id": self._copier_n["master_id"].get().strip(),
            "copy_sl": bool(self._copier_t["copy_sl"].get()),
            "copy_pending": bool(self._copier_t["copy_pending"].get()),
            "reverse": bool(self._copier_t["reverse"].get()),
            "followers": followers,
        })
        messagebox.showinfo("Copier", "Saved.")

    def _save_automation(self) -> None:
        data = automation.load()
        for k, var in self._auto_t.items():
            data[k] = bool(var.get())
        for k, var in self._auto_n.items():
            raw = var.get().replace(",", ".").strip()
            data[k] = float(raw or 0)
        hours = {}
        for i, meta in self._hours.items():
            hours[i] = {"on": bool(meta["on"].get()), "start": int(float(meta["start"].get() or 0)), "end": int(float(meta["end"].get() or 23))}
        data["hours"] = hours
        automation.save(data)
        messagebox.showinfo("Automation", "Saved.")

    def _save_alerts(self) -> None:
        data = alerts.load()
        for k, var in self._alert_t.items():
            data[k] = bool(var.get())
        for k, var in self._alert_n.items():
            data[k] = float(var.get().replace(",", ".") or 0)
        alerts.save(data)
        messagebox.showinfo("Alerts", "Saved.")

    def _add_account(self) -> None:
        win = tk.Toplevel(self.root)
        win.title("Add account")
        win.configure(bg=C["panel"])
        win.geometry("420x340")
        fields: dict[str, tk.StringVar] = {}
        for key, label in (("label", "Label"), ("login", "Login"), ("password", "Password"), ("server", "Server")):
            tk.Label(win, text=label, bg=C["panel"], fg=C["mute"]).pack(anchor="w", padx=14, pady=(8, 0))
            var = tk.StringVar()
            fields[key] = var
            tk.Entry(win, textvariable=var, show="*" if key == "password" else "", bg=C["panel2"], fg=C["ink"], relief=tk.FLAT).pack(fill=tk.X, padx=14)

        def go() -> None:
            try:
                c = clients.add(login=fields["login"].get(), password=fields["password"].get(), server=fields["server"].get(), label=fields["label"].get())
                win.destroy()
                self.selected_cid = c["id"]
                messagebox.showinfo("Account", f"Created {c['id']}\nSet Risk Manager → LAUNCH MT4")
                self._show("accounts")
                self._load_risk(c["id"])
            except Exception as exc:  # noqa: BLE001
                messagebox.showerror("Add", str(exc))

        pill_btn(win, "CREATE + CLONE MT4", C["ok"], go).pack(pady=16)

    def _render_accounts_table(self) -> None:
        for i in self.acc_table.get_children():
            self.acc_table.delete(i)
        snap_by_login: dict[str, dict] = {}
        for b in clients.all_bridges():
            st = bridge.load_status(b) or {}
            login = str(st.get("account") or "")
            if login:
                snap_by_login[login] = st
        for row in clients.list_clients():
            cid = str(row.get("id"))
            full = clients.read(cid) or row
            st = snap_by_login.get(str(full.get("login")), {})
            eq = float(st.get("equity") or 0)
            bal = float(st.get("balance") or eq)
            self.acc_table.insert("", tk.END, iid=cid, values=(cid, full.get("login"), full.get("server"), full.get("lot"), full.get("sl_points"), f"{eq:.2f}" if eq else "—", "active" if st else "idle", f"{eq-bal:+.2f}" if eq else "—"))

    def _render_acc_cards(self) -> None:
        for w in self.acc_cards.winfo_children():
            w.destroy()
        rows = clients.list_clients()
        if not rows:
            tk.Label(self.acc_cards, text="No accounts", bg=C["panel"], fg=C["mute"]).pack(pady=12)
            return
        for row in rows[:8]:
            cid = str(row.get("id"))
            full = clients.read(cid) or row
            card = tk.Frame(self.acc_cards, bg=C["panel2"])
            card.pack(fill=tk.X, pady=3)
            tk.Label(card, text=cid, bg=C["panel2"], fg=C["ink"], font=self.f_h).pack(anchor="w", padx=8, pady=(6, 0))
            tk.Label(card, text=f"SL {full.get('sl_points')} pts · lot {full.get('lot')}", bg=C["panel2"], fg=C["mute"], font=self.f_mono).pack(anchor="w", padx=8, pady=(0, 6))

    def _on_acc_select(self, _e=None) -> None:
        sel = self.acc_table.selection()
        if sel:
            self.selected_cid = sel[0]
            self._load_risk(self.selected_cid)

    def _load_risk(self, cid: str) -> None:
        self.selected_cid = cid
        full = clients.read(cid)
        if not full:
            return
        self.risk_title.set(f"account: {cid}")
        for k, var in self._nums.items():
            if k in full:
                var.set(str(full.get(k)))
        for k, var in self._toggles.items():
            if k in full:
                var.set(as_bool(full.get(k), bool(ACCOUNT_RISK_DEFAULTS.get(k, False))))

    def _save_risk(self) -> None:
        try:
            g = settings_mod.load()
            for k, var in self._g_toggles.items():
                g[k] = bool(var.get())
            for k, var in self._g_nums.items():
                raw = var.get().replace(",", ".").strip()
                g[k] = float(raw) if "." in raw else int(float(raw or 0))
            settings_mod.save(g)
            if not self.selected_cid:
                messagebox.showinfo("Risk", "Portfolio caps saved. Select account for account risk.")
                return
            fields: dict[str, Any] = {}
            for k, var in self._toggles.items():
                fields[k] = bool(var.get())
            for k, var in self._nums.items():
                raw = var.get().replace(",", ".").strip()
                fields[k] = int(float(raw or 0)) if k in {"max_open_trades", "auto_stop_after_losses"} else float(raw or 0)
            clients.update_risk(self.selected_cid, **fields)
            messagebox.showinfo("Risk", f"Saved for {self.selected_cid}")
            self._render_accounts_table()
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Risk", str(exc))

    def _launch_selected(self) -> None:
        if not self.selected_cid:
            messagebox.showwarning("MT4", "Select an account")
            return
        ok, msg = clients.launch(self.selected_cid)
        (messagebox.showinfo if ok else messagebox.showwarning)("MT4", msg)

    def _delete_selected(self) -> None:
        if not self.selected_cid:
            return
        if messagebox.askyesno("Delete", f"Delete {self.selected_cid}?"):
            clients.delete(self.selected_cid)
            self.selected_cid = None
            self._render_accounts_table()

    def refresh(self) -> None:
        if not getattr(self, "foot", None):
            return
        self.live_var.set(self.engine.running and self.engine.mode == "live")
        snap = analytics.snapshot()
        self.kpi["equity"].set(f"{snap['equity']:,.2f}" if snap["equity"] else "—")
        self.kpi["daily"].set(f"{snap['daily_pl']:+,.2f}")
        self.kpi["pos"].set(str(snap["open_positions"]))
        self.kpi["win"].set(f"{snap['win_rate']:.1f}%")
        self.kpi["pf"].set(f"{snap['profit_factor']:.2f}")

        # tickers
        for w in self.ticker_host.winfo_children():
            w.destroy()
        bridges = clients.all_bridges()
        if not bridges:
            tk.Label(self.ticker_host, text="No live bridges", bg=C["panel2"], fg=C["mute"], font=self.f_ui).pack(side=tk.LEFT)
        for b in bridges[:8]:
            mk = bridge.load_market(b) or {}
            sym = str(mk.get("symbol") or "?")
            bid = mk.get("bid")
            age = bridge.age_s(b / "market" / "latest.json")
            txt = f"{sym}  {bid}  ({age:.0f}s)" if bid is not None and age is not None else sym
            tk.Label(self.ticker_host, text=txt, bg=C["panel2"], fg=C["ice"], font=self.f_mono, padx=10).pack(side=tk.LEFT)

        # chart from first bridge
        if bridges and hasattr(self, "chart"):
            mk = bridge.load_market(bridges[0]) or {}
            bars = mk.get("bars_m1") or []
            sigs = []
            if self.engine.last_signal:
                side = "BUY" if "UP" in self.engine.last_signal or self.engine.last_signal.endswith("_UP") else "SELL"
                if "SELL" in self.engine.last_signal or "DOWN" in self.engine.last_signal:
                    side = "SELL"
                if "BUY" in self.engine.last_signal or "UP" in self.engine.last_signal:
                    side = "BUY"
                sigs = [(side, -1)]
            self.chart.set_data(bars, sigs)
            self.chart_meta.set(f"{mk.get('symbol','—')}  bid={mk.get('bid')} ask={mk.get('ask')}  last={self.engine.last_reason}")
            if hasattr(self, "market_chart"):
                self.market_chart.set_data(bars, sigs)
                self.market_info.set(self.chart_meta.get())

        if hasattr(self, "pos"):
            for i in self.pos.get_children():
                self.pos.delete(i)
            for b in bridges:
                st = bridge.load_status(b) or {}
                mk = bridge.load_market(b) or {}
                acc = str(st.get("account") or mk.get("account") or "—")
                for p in st.get("positions") or []:
                    if not isinstance(p, dict):
                        continue
                    self.pos.insert("", tk.END, values=(p.get("symbol") or mk.get("symbol"), acc, p.get("side"), p.get("lot"), p.get("sl"), p.get("price"), p.get("profit"), self.engine.last_signal or "—", "live"))

        if hasattr(self, "acc_cards") and self._page == "dashboard":
            self._render_acc_cards()

        if hasattr(self, "log") and self._log_lines:
            self.log.configure(state=tk.NORMAL)
            self.log.delete("1.0", tk.END)
            self.log.insert(tk.END, "\n".join(self._log_lines[-80:]))
            self.log.configure(state=tk.DISABLED)

        if hasattr(self, "alert_feed"):
            self.alert_feed.configure(state=tk.NORMAL)
            self.alert_feed.delete("1.0", tk.END)
            self.alert_feed.insert(tk.END, "\n".join(self._alert_lines[-60:] or ["No alerts yet"]))
            self.alert_feed.configure(state=tk.DISABLED)

        if hasattr(self, "report_text") and self._page == "reports":
            by = snap.get("by_symbol") or {}
            lines = [
                f"Equity: {snap['equity']:.2f}",
                f"Daily P/L: {snap['daily_pl']:+.2f}",
                f"Open: {snap['open_positions']}",
                f"Win rate: {snap['win_rate']:.1f}%  ({snap['wins']}W / {snap['losses']}L)",
                f"Profit factor: {snap['profit_factor']:.2f}",
                "",
                "P/L by symbol (closed journal):",
            ]
            for sym, pl in sorted(by.items(), key=lambda x: -abs(x[1])):
                lines.append(f"  {sym}: {pl:+.2f}")
            if not by:
                lines.append("  (no closed trades in journal yet)")
            self.report_text.delete("1.0", tk.END)
            self.report_text.insert("1.0", "\n".join(lines))

        if hasattr(self, "journal") and self._page == "journal":
            for i in self.journal.get_children():
                self.journal.delete(i)
            for row in reversed(analytics.read_journal(200)):
                self.journal.insert("", tk.END, values=(row.get("ts"), row.get("type"), row.get("account"), row.get("symbol"), row.get("side"), row.get("pl"), row.get("reason") or row.get("mode") or ""))

        st = clients.setup_status()
        self.foot.configure(text=f"CHECK NEXUS  |  template={'OK' if st['template_ok'] else 'MISSING'}  |  accounts={st['clients']}  |  mode={self.engine.mode}  |  reason={self.engine.last_reason}")

    def _tick(self) -> None:
        with contextlib.suppress(Exception):
            self.refresh()
        self.root.after(800, self._tick)

    def _close(self) -> None:
        if self.engine.running:
            if not messagebox.askyesno("Quit", "Stop and quit?"):
                return
            self.engine.stop()
        self.root.destroy()


def main() -> None:
    paths.ensure_layout()
    root = tk.Tk()
    with contextlib.suppress(tk.TclError):
        root.state("zoomed")
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
