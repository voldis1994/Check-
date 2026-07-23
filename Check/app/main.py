"""CHECK desk — Nexus-style command center. Hard numbers + risk toggles."""

from __future__ import annotations

import contextlib
import os
import sys
import tkinter as tk
import tkinter.font as tkfont
from tkinter import messagebox, ttk
from typing import Any, Callable

from app import paths

ROOT = paths.app_root()
os.chdir(ROOT)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import bridge, clients, settings as settings_mod  # noqa: E402
from app.engine import Engine  # noqa: E402
from app.risk import ACCOUNT_RISK_DEFAULTS, as_bool  # noqa: E402

# Reference look: dark navy / violet command center
C = {
    "bg": "#0B0E17",
    "sidebar": "#0F1320",
    "panel": "#151B2E",
    "panel2": "#1A2238",
    "line": "#2A3555",
    "ink": "#E8ECF8",
    "mute": "#8B95B2",
    "violet": "#7C6CFF",
    "violet2": "#9B8CFF",
    "ok": "#22C55E",
    "bad": "#EF4444",
    "warn": "#F59E0B",
    "ice": "#38BDF8",
}


def _font(names: list[str], size: int, weight: str = "normal") -> tuple:
    fam = set(tkfont.families())
    for n in names:
        if n in fam:
            return (n, size, weight) if weight != "normal" else (n, size)
    return ("TkDefaultFont", size, weight) if weight != "normal" else ("TkDefaultFont", size)


class Toggle(tk.Frame):
    """On/Off pill for risk functions."""

    def __init__(self, parent, var: tk.BooleanVar, text: str = "", on_change: Callable | None = None):
        super().__init__(parent, bg=parent.cget("bg") if parent.cget("bg") else C["panel"])
        self.var = var
        self.on_change = on_change
        self.btn = tk.Label(
            self,
            text="ON" if var.get() else "OFF",
            bg=C["ok"] if var.get() else C["line"],
            fg=C["ink"],
            font=("Segoe UI", 9, "bold"),
            width=5,
            cursor="hand2",
            padx=6,
            pady=3,
        )
        self.btn.pack(side=tk.LEFT)
        self.btn.bind("<Button-1>", self._flip)
        if text:
            tk.Label(self, text=text, bg=self.cget("bg"), fg=C["ink"], font=("Segoe UI", 10)).pack(
                side=tk.LEFT, padx=8
            )
        var.trace_add("write", lambda *_: self._sync())

    def _flip(self, _e=None) -> None:
        self.var.set(not self.var.get())
        if self.on_change:
            self.on_change()

    def _sync(self) -> None:
        on = bool(self.var.get())
        self.btn.configure(text="ON" if on else "OFF", bg=C["ok"] if on else C["line"])


class App:
    def __init__(self, root: tk.Tk) -> None:
        paths.ensure_layout()
        if not (ROOT / "config" / "settings.json").exists():
            settings_mod.save(settings_mod.load())

        self.root = root
        self.root.title("CHECK")
        self.root.geometry("1440x920")
        self.root.minsize(1200, 780)
        self.root.configure(bg=C["bg"])

        self.f_brand = _font(["Bahnschrift SemiBold", "Bahnschrift", "Segoe UI"], 22, "bold")
        self.f_h = _font(["Bahnschrift", "Segoe UI"], 12, "bold")
        self.f_ui = _font(["Segoe UI", "Bahnschrift"], 10)
        self.f_mono = _font(["Cascadia Mono", "Consolas"], 9)
        self.f_kpi = _font(["Bahnschrift", "Segoe UI"], 16, "bold")

        self.engine = Engine(on_log=self._push_log)
        self._log_lines: list[str] = []
        self._page = "dashboard"
        self.selected_cid: str | None = None
        self.kpi: dict[str, tk.StringVar] = {}
        self.live_var = tk.BooleanVar(value=False)
        self._nav: dict[str, tk.Label] = {}
        self._toggles: dict[str, tk.BooleanVar] = {}
        self._nums: dict[str, tk.StringVar] = {}
        self._g_toggles: dict[str, tk.BooleanVar] = {}
        self._g_nums: dict[str, tk.StringVar] = {}

        self._style()
        self._build()
        self.refresh()
        self.root.after(900, self._tick)
        self.root.protocol("WM_DELETE_WINDOW", self._close)

    def _style(self) -> None:
        st = ttk.Style()
        with contextlib.suppress(tk.TclError):
            st.theme_use("clam")
        st.configure(
            "N.Treeview",
            background=C["panel"],
            foreground=C["ink"],
            fieldbackground=C["panel"],
            rowheight=28,
            font=self.f_mono,
            borderwidth=0,
        )
        st.configure("N.Treeview.Heading", background=C["panel2"], foreground=C["violet2"], font=self.f_ui)
        st.map("N.Treeview", background=[("selected", C["line"])])

    def _build(self) -> None:
        shell = tk.Frame(self.root, bg=C["bg"])
        shell.pack(fill=tk.BOTH, expand=True)

        # --- sidebar ---
        side = tk.Frame(shell, bg=C["sidebar"], width=200)
        side.pack(side=tk.LEFT, fill=tk.Y)
        side.pack_propagate(False)
        tk.Label(side, text="CHECK", bg=C["sidebar"], fg=C["violet2"], font=self.f_brand).pack(
            anchor="w", padx=18, pady=(22, 2)
        )
        tk.Label(side, text="COMMAND CENTER", bg=C["sidebar"], fg=C["mute"], font=self.f_ui).pack(
            anchor="w", padx=18, pady=(0, 18)
        )
        for key, label in (
            ("dashboard", "Dashboard"),
            ("accounts", "Accounts"),
            ("strategies", "Strategies"),
            ("risk", "Risk Manager"),
            ("settings", "Settings"),
        ):
            lab = tk.Label(
                side,
                text=f"  {label}",
                bg=C["sidebar"],
                fg=C["mute"],
                font=self.f_ui,
                anchor="w",
                cursor="hand2",
                pady=10,
            )
            lab.pack(fill=tk.X, padx=8)
            lab.bind("<Button-1>", lambda _e, k=key: self._show(k))
            self._nav[key] = lab

        # --- main column ---
        main = tk.Frame(shell, bg=C["bg"])
        main.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # header KPIs + Live toggle
        head = tk.Frame(main, bg=C["panel"], height=78)
        head.pack(fill=tk.X, padx=14, pady=(14, 8))
        head.pack_propagate(False)
        kpi_row = tk.Frame(head, bg=C["panel"])
        kpi_row.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=8, pady=8)
        for key, title, col in (
            ("equity", "Total Equity", C["ink"]),
            ("daily", "Daily P/L", C["ok"]),
            ("pos", "Open Positions", C["violet2"]),
            ("bridges", "Bridges", C["ice"]),
            ("reason", "Last", C["warn"]),
        ):
            self.kpi[key] = tk.StringVar(value="—")
            cell = tk.Frame(kpi_row, bg=C["panel"])
            cell.pack(side=tk.LEFT, fill=tk.Y, padx=12)
            tk.Label(cell, text=title, bg=C["panel"], fg=C["mute"], font=self.f_ui).pack(anchor="w")
            tk.Label(cell, textvariable=self.kpi[key], bg=C["panel"], fg=col, font=self.f_kpi).pack(anchor="w")

        live_box = tk.Frame(head, bg=C["panel"])
        live_box.pack(side=tk.RIGHT, padx=16)
        tk.Label(live_box, text="Live Trading", bg=C["panel"], fg=C["mute"], font=self.f_ui).pack(anchor="e")
        Toggle(live_box, self.live_var, on_change=self._toggle_live).pack(anchor="e", pady=4)

        self.body = tk.Frame(main, bg=C["bg"])
        self.body.pack(fill=tk.BOTH, expand=True, padx=14, pady=(0, 8))
        self.pages = {
            "dashboard": self._page_dashboard(self.body),
            "accounts": self._page_accounts(self.body),
            "strategies": self._page_strategies(self.body),
            "risk": self._page_risk(self.body),
            "settings": self._page_settings(self.body),
        }

        foot = tk.Frame(main, bg=C["panel"], height=32)
        foot.pack(fill=tk.X, side=tk.BOTTOM, padx=14, pady=(0, 10))
        self.foot = tk.Label(foot, text="", bg=C["panel"], fg=C["mute"], font=self.f_mono, anchor="w")
        self.foot.pack(fill=tk.X, padx=10, pady=6)

        self._show("dashboard")

    def _card(self, parent, title: str) -> tk.Frame:
        wrap = tk.Frame(parent, bg=C["panel"])
        tk.Label(wrap, text=title, bg=C["panel"], fg=C["violet2"], font=self.f_h).pack(anchor="w", padx=12, pady=(10, 4))
        return wrap

    def _page_dashboard(self, parent) -> tk.Frame:
        f = tk.Frame(parent, bg=C["bg"])
        top = tk.Frame(f, bg=C["bg"])
        top.pack(fill=tk.BOTH, expand=True)

        left = self._card(top, "ACCOUNTS")
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))
        self.acc_list = tk.Frame(left, bg=C["panel"])
        self.acc_list.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        right = self._card(top, "OPEN POSITIONS")
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.pos = ttk.Treeview(
            right,
            columns=("account", "ticket", "side", "lot", "sl", "pl"),
            show="headings",
            style="N.Treeview",
            height=12,
        )
        for c, t, w in (
            ("account", "ACCOUNT", 90),
            ("ticket", "TICKET", 80),
            ("side", "SIDE", 50),
            ("lot", "LOT", 50),
            ("sl", "SL", 90),
            ("pl", "P/L", 70),
        ):
            self.pos.heading(c, text=t)
            self.pos.column(c, width=w, anchor="w")
        self.pos.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        bot = self._card(f, "ENGINE LOG")
        bot.pack(fill=tk.X, pady=(8, 0))
        self.log = tk.Text(bot, bg=C["panel2"], fg=C["ink"], height=7, relief=tk.FLAT, font=self.f_mono)
        self.log.pack(fill=tk.X, padx=8, pady=8)
        self.log.configure(state=tk.DISABLED)
        return f

    def _page_accounts(self, parent) -> tk.Frame:
        f = tk.Frame(parent, bg=C["bg"])
        head = tk.Frame(f, bg=C["bg"])
        head.pack(fill=tk.X)
        tk.Label(head, text="MULTI-ACCOUNT", bg=C["bg"], fg=C["violet2"], font=self.f_h).pack(side=tk.LEFT)
        tk.Button(
            head,
            text="+ ADD ACCOUNT",
            command=self._add_account,
            bg=C["violet"],
            fg=C["ink"],
            relief=tk.FLAT,
            font=self.f_ui,
            padx=12,
            pady=6,
            cursor="hand2",
        ).pack(side=tk.RIGHT)

        self.acc_table = ttk.Treeview(
            f,
            columns=("id", "login", "server", "lot", "sl", "status"),
            show="headings",
            style="N.Treeview",
            height=14,
        )
        for c, t, w in (
            ("id", "ID", 100),
            ("login", "LOGIN", 100),
            ("server", "SERVER", 140),
            ("lot", "LOT", 60),
            ("sl", "SL PTS", 70),
            ("status", "STATUS", 100),
        ):
            self.acc_table.heading(c, text=t)
            self.acc_table.column(c, width=w, anchor="w")
        self.acc_table.pack(fill=tk.BOTH, expand=True, pady=10)
        self.acc_table.bind("<<TreeviewSelect>>", self._on_acc_select)

        row = tk.Frame(f, bg=C["bg"])
        row.pack(fill=tk.X)
        for text, cmd, col in (
            ("LAUNCH MT4", self._launch_selected, C["ice"]),
            ("EDIT RISK", lambda: self._show("risk"), C["warn"]),
            ("DELETE", self._delete_selected, C["bad"]),
        ):
            tk.Button(
                row,
                text=text,
                command=cmd,
                bg=C["panel"],
                fg=col,
                relief=tk.FLAT,
                highlightthickness=1,
                highlightbackground=col,
                font=self.f_ui,
                padx=12,
                pady=7,
                cursor="hand2",
            ).pack(side=tk.LEFT, padx=4)
        return f

    def _page_strategies(self, parent) -> tk.Frame:
        f = tk.Frame(parent, bg=C["bg"])
        tk.Label(f, text="STRATEGIES  (M1 only)", bg=C["bg"], fg=C["violet2"], font=self.f_h).pack(anchor="w")
        cfg = settings_mod.load()
        card = self._card(f, "MODES")
        card.pack(fill=tk.X, pady=10)
        self.trend_v = tk.BooleanVar(value=bool(cfg.get("trend", True)))
        self.bo_v = tk.BooleanVar(value=bool(cfg.get("breakout", True)))
        row = tk.Frame(card, bg=C["panel"])
        row.pack(anchor="w", padx=12, pady=12)
        Toggle(row, self.trend_v, "TREND").pack(side=tk.LEFT, padx=(0, 24))
        Toggle(row, self.bo_v, "BREAKOUT").pack(side=tk.LEFT)
        tk.Label(
            card,
            text="Range / Scalping nav — tikai Trend + Breakout.",
            bg=C["panel"],
            fg=C["mute"],
            font=self.f_ui,
        ).pack(anchor="w", padx=12, pady=(0, 12))
        tk.Button(
            f,
            text="SAVE STRATEGIES",
            command=self._save_strategies,
            bg=C["violet"],
            fg=C["ink"],
            relief=tk.FLAT,
            font=self.f_ui,
            padx=14,
            pady=8,
        ).pack(anchor="w")
        return f

    def _num_row(self, parent, key: str, label: str, store: dict, default: str = "0") -> None:
        row = tk.Frame(parent, bg=C["panel"])
        row.pack(fill=tk.X, padx=12, pady=4)
        tk.Label(row, text=label, bg=C["panel"], fg=C["mute"], font=self.f_ui, width=28, anchor="w").pack(side=tk.LEFT)
        var = tk.StringVar(value=default)
        store[key] = var
        tk.Entry(
            row,
            textvariable=var,
            bg=C["panel2"],
            fg=C["ink"],
            insertbackground=C["violet"],
            relief=tk.FLAT,
            width=14,
            font=self.f_mono,
        ).pack(side=tk.LEFT)

    def _toggle_row(self, parent, key: str, label: str, store: dict, default: bool = False) -> None:
        row = tk.Frame(parent, bg=C["panel"])
        row.pack(fill=tk.X, padx=12, pady=5)
        var = tk.BooleanVar(value=default)
        store[key] = var
        Toggle(row, var, label).pack(side=tk.LEFT)

    def _page_risk(self, parent) -> tk.Frame:
        f = tk.Frame(parent, bg=C["bg"])
        top = tk.Frame(f, bg=C["bg"])
        top.pack(fill=tk.X)
        tk.Label(top, text="RISK MANAGER", bg=C["bg"], fg=C["violet2"], font=self.f_h).pack(side=tk.LEFT)
        self.risk_title = tk.StringVar(value="(select account)")
        tk.Label(top, textvariable=self.risk_title, bg=C["bg"], fg=C["mute"], font=self.f_ui).pack(side=tk.LEFT, padx=12)

        grid = tk.Frame(f, bg=C["bg"])
        grid.pack(fill=tk.BOTH, expand=True, pady=8)

        left = self._card(grid, "ACCOUNT — hard numbers + toggles")
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))
        self._num_row(left, "lot", "Lot", self._nums, "0.02")
        self._num_row(left, "sl_points", "SL (points)", self._nums, "150")
        self._toggle_row(left, "be_enabled", "Breakeven", self._toggles, True)
        self._num_row(left, "be_start_points", "BE start (points)", self._nums, "50")
        self._num_row(left, "be_offset_points", "BE offset (points)", self._nums, "5")
        self._toggle_row(left, "trail_enabled", "Trailing", self._toggles, True)
        self._num_row(left, "trail_start_points", "Trail start (points)", self._nums, "80")
        self._num_row(left, "trail_lock_points", "Trail lock (points)", self._nums, "40")

        mid = self._card(grid, "PROTECTION — On/Off + hard $ / counts")
        mid.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))
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

        right = self._card(grid, "PORTFOLIO (global hard caps)")
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        cfg = settings_mod.load()
        self._toggle_row(right, "max_total_open_enabled", "Max total open", self._g_toggles, bool(cfg.get("max_total_open_enabled")))
        self._num_row(right, "max_total_open", "Max total open (count)", self._g_nums, str(cfg.get("max_total_open", 10)))
        self._toggle_row(
            right, "global_daily_loss_enabled", "Global daily loss", self._g_toggles, bool(cfg.get("global_daily_loss_enabled"))
        )
        self._num_row(right, "global_daily_loss", "Global daily loss ($)", self._g_nums, str(cfg.get("global_daily_loss", 1000)))
        self._toggle_row(
            right,
            "global_equity_floor_enabled",
            "Global equity floor",
            self._g_toggles,
            bool(cfg.get("global_equity_floor_enabled")),
        )
        self._num_row(right, "global_equity_floor", "Global equity floor ($)", self._g_nums, str(cfg.get("global_equity_floor", 0)))

        tk.Label(
            f,
            text="Nav procentu — tikai cietie skaitli (points / $ / count). OFF = funkcija izslegta.",
            bg=C["bg"],
            fg=C["mute"],
            font=self.f_ui,
        ).pack(anchor="w", pady=(4, 8))

        tk.Button(
            f,
            text="SAVE RISK",
            command=self._save_risk,
            bg=C["violet"],
            fg=C["ink"],
            relief=tk.FLAT,
            font=self.f_ui,
            padx=16,
            pady=8,
            cursor="hand2",
        ).pack(anchor="w")
        return f

    def _page_settings(self, parent) -> tk.Frame:
        f = tk.Frame(parent, bg=C["bg"])
        tk.Label(f, text="SETTINGS", bg=C["bg"], fg=C["violet2"], font=self.f_h).pack(anchor="w")
        cfg = settings_mod.load()
        card = self._card(f, "GLOBAL")
        card.pack(fill=tk.X, pady=10)
        self._g_misc: dict[str, tk.StringVar] = {}
        for key, label, default in (
            ("symbol", "Symbol", str(cfg.get("symbol", "AUTO"))),
            ("cycle_sec", "Cycle sec", str(cfg.get("cycle_sec", 3))),
            ("magic", "Magic", str(cfg.get("magic", 50001))),
        ):
            self._num_row(card, key, label, self._g_misc, default)
        st = clients.setup_status()
        tip = f"Template MT4: {'OK' if st['template_ok'] else 'MISSING — template\\\\ + SETUP.bat'}"
        if st.get("master"):
            tip += f"\n{st['master']}"
        tk.Label(f, text=tip, bg=C["bg"], fg=C["mute"], font=self.f_mono, justify="left").pack(anchor="w", pady=8)
        tk.Button(
            f,
            text="SAVE SETTINGS",
            command=self._save_settings,
            bg=C["violet"],
            fg=C["ink"],
            relief=tk.FLAT,
            font=self.f_ui,
            padx=14,
            pady=8,
        ).pack(anchor="w")
        return f

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
        if key == "dashboard":
            self._render_acc_cards()
        self.refresh()

    def _push_log(self, line: str) -> None:
        self._log_lines.append(line)
        self._log_lines = self._log_lines[-200:]

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

    def _save_strategies(self) -> None:
        data = settings_mod.load()
        data["trend"] = bool(self.trend_v.get())
        data["breakout"] = bool(self.bo_v.get())
        settings_mod.save(data)
        messagebox.showinfo("Strategies", "Saved.")

    def _save_settings(self) -> None:
        data = settings_mod.load()
        data["symbol"] = self._g_misc["symbol"].get().strip() or "AUTO"
        data["cycle_sec"] = float(self._g_misc["cycle_sec"].get().replace(",", ".") or 3)
        data["magic"] = int(float(self._g_misc["magic"].get() or 50001))
        settings_mod.save(data)
        messagebox.showinfo("Settings", "Saved.")

    def _add_account(self) -> None:
        win = tk.Toplevel(self.root)
        win.title("Add account")
        win.configure(bg=C["panel"])
        win.geometry("420x360")
        fields: dict[str, tk.StringVar] = {}
        for key, label in (("label", "Label"), ("login", "Login"), ("password", "Password"), ("server", "Server")):
            tk.Label(win, text=label, bg=C["panel"], fg=C["mute"]).pack(anchor="w", padx=14, pady=(8, 0))
            var = tk.StringVar()
            fields[key] = var
            tk.Entry(
                win,
                textvariable=var,
                show="*" if key == "password" else "",
                bg=C["panel2"],
                fg=C["ink"],
                relief=tk.FLAT,
            ).pack(fill=tk.X, padx=14)

        def go() -> None:
            try:
                c = clients.add(
                    login=fields["login"].get(),
                    password=fields["password"].get(),
                    server=fields["server"].get(),
                    label=fields["label"].get(),
                )
                win.destroy()
                self.selected_cid = c["id"]
                messagebox.showinfo("Account", f"Created {c['id']}\nSet RISK (points / $) then LAUNCH MT4")
                self._show("accounts")
                self._load_risk(c["id"])
            except Exception as exc:  # noqa: BLE001
                messagebox.showerror("Add", str(exc))

        tk.Button(win, text="CREATE", command=go, bg=C["violet"], fg=C["ink"], relief=tk.FLAT, padx=14, pady=8).pack(
            pady=16
        )

    def _render_accounts_table(self) -> None:
        for i in self.acc_table.get_children():
            self.acc_table.delete(i)
        for row in clients.list_clients():
            cid = str(row.get("id"))
            full = clients.read(cid) or row
            self.acc_table.insert(
                "",
                tk.END,
                iid=cid,
                values=(
                    cid,
                    full.get("login"),
                    full.get("server"),
                    full.get("lot"),
                    full.get("sl_points"),
                    "ready",
                ),
            )

    def _render_acc_cards(self) -> None:
        for w in self.acc_list.winfo_children():
            w.destroy()
        rows = clients.list_clients()
        if not rows:
            tk.Label(self.acc_list, text="No accounts yet", bg=C["panel"], fg=C["mute"], font=self.f_ui).pack(pady=20)
            return
        for row in rows:
            cid = str(row.get("id"))
            full = clients.read(cid) or row
            card = tk.Frame(self.acc_list, bg=C["panel2"])
            card.pack(fill=tk.X, pady=4)
            tk.Label(card, text=cid, bg=C["panel2"], fg=C["ink"], font=self.f_h).pack(anchor="w", padx=10, pady=(8, 0))
            tk.Label(
                card,
                text=f"login {full.get('login')}  ·  SL {full.get('sl_points')} pts  ·  lot {full.get('lot')}",
                bg=C["panel2"],
                fg=C["mute"],
                font=self.f_mono,
            ).pack(anchor="w", padx=10, pady=(0, 8))

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
            # always save global portfolio caps
            g = settings_mod.load()
            for k, var in self._g_toggles.items():
                g[k] = bool(var.get())
            for k, var in self._g_nums.items():
                raw = var.get().replace(",", ".").strip()
                g[k] = float(raw) if "." in raw else int(float(raw or 0))
            settings_mod.save(g)

            if not self.selected_cid:
                messagebox.showinfo("Risk", "Global portfolio risk saved.\nSelect an account to save account risk.")
                return

            fields: dict[str, Any] = {}
            for k, var in self._toggles.items():
                fields[k] = bool(var.get())
            for k, var in self._nums.items():
                raw = var.get().replace(",", ".").strip()
                if k in {"max_open_trades", "auto_stop_after_losses"}:
                    fields[k] = int(float(raw or 0))
                else:
                    fields[k] = float(raw or 0)
            clients.update_risk(self.selected_cid, **fields)
            messagebox.showinfo("Risk", f"Saved hard-number risk for {self.selected_cid}")
            self._render_accounts_table()
            self.refresh()
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
            self.refresh()

    def refresh(self) -> None:
        if not getattr(self, "foot", None):
            return
        self.live_var.set(self.engine.running and self.engine.mode == "live")

        for i in self.pos.get_children():
            self.pos.delete(i)

        bridges = clients.all_bridges()
        equity_sum = 0.0
        pos_n = 0
        daily = 0.0
        for b in bridges:
            market = bridge.load_market(b) or {}
            status = bridge.load_status(b) or {}
            account = str(status.get("account") or market.get("account") or "—")
            eq = float(status.get("equity") or 0)
            bal = float(status.get("balance") or eq)
            equity_sum += eq
            daily += eq - bal
            positions = status.get("positions") or []
            if isinstance(positions, list):
                pos_n += len(positions)
                for p in positions:
                    if not isinstance(p, dict):
                        continue
                    self.pos.insert(
                        "",
                        tk.END,
                        values=(account, p.get("ticket"), p.get("side"), p.get("lot"), p.get("sl"), p.get("profit")),
                    )

        self.kpi["equity"].set(f"{equity_sum:,.2f}" if bridges else "—")
        self.kpi["daily"].set(f"{daily:+,.2f}" if bridges else "—")
        self.kpi["pos"].set(str(pos_n))
        self.kpi["bridges"].set(str(len(bridges)))
        self.kpi["reason"].set(self.engine.last_reason)

        if self._log_lines and getattr(self, "log", None):
            self.log.configure(state=tk.NORMAL)
            self.log.delete("1.0", tk.END)
            self.log.insert(tk.END, "\n".join(self._log_lines[-80:]))
            self.log.configure(state=tk.DISABLED)

        st = clients.setup_status()
        self.foot.configure(
            text=f"CHECK  |  template={'OK' if st['template_ok'] else 'MISSING'}  |  accounts={st['clients']}  |  mode={self.engine.mode}"
        )

    def _tick(self) -> None:
        with contextlib.suppress(Exception):
            self.refresh()
        self.root.after(900, self._tick)

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
