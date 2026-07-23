"""CHECK COMMAND — professional multi-account trading control desk (Tkinter).

Dense summary KPIs + always-visible tables (accounts, positions, system, day).
Entry point for START_DASHBOARD.bat and frozen CHECK_SYSTEM.exe.
"""

from __future__ import annotations

import contextlib
import math
import queue
import sys
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
from pathlib import Path
from tkinter import messagebox, ttk

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

from dashboard_core import (  # noqa: E402
    EngineProcess,
    arm_live_runtime,
    audit_activity,
    audit_file,
    build_floor_report,
    clear_account_lot_override,
    clear_stop,
    collect_health,
    default_fixed_lot,
    format_age,
    format_audit_line,
    list_known_accounts,
    load_config_json,
    load_equity_series,
    lot_bounds,
    read_account_lot_override,
    record_equity_samples,
    resolve_config,
    run_deploy_mt4,
    runtime_dir,
    set_trading_enabled,
    validate_live_config,
    write_account_lot_override,
    write_stop,
)
import platform_store  # noqa: E402

try:
    from checktrader.config.migrate import sync_system_json
except Exception:  # noqa: BLE001
    sync_system_json = None  # type: ignore[assignment]

# Command-desk palette: graphite + brass + signal green (not purple / cream).
C = {
    "bg": "#0C1110",
    "panel": "#141C1A",
    "panel2": "#1A2622",
    "line": "#2A3B34",
    "ink": "#ECF3EF",
    "mute": "#80948A",
    "brass": "#D4A84B",
    "signal": "#3DDC97",
    "sky": "#5BB8C8",
    "warn": "#E0A045",
    "stop": "#E85D4C",
    "ok": "#5EE0A0",
    "dim": "#4A5E55",
}


def _font(cands: list[str], size: int, weight: str = "normal") -> tuple:
    fam = set(tkfont.families())
    for name in cands:
        if name in fam:
            return (name, size, weight) if weight != "normal" else (name, size)
    return ("TkDefaultFont", size, weight) if weight != "normal" else ("TkDefaultFont", size)


class EquityChart:
    """Mini equity polyline — always draws frame + empty state."""

    def __init__(self, canvas: tk.Canvas) -> None:
        self.canvas = canvas
        self.points: list[float] = []
        canvas.bind("<Configure>", lambda _e: self.draw())

    def set_points(self, values: list[float]) -> None:
        self.points = values[-120:]
        self.draw()

    def draw(self) -> None:
        c = self.canvas
        c.delete("all")
        w = max(c.winfo_width(), 40)
        h = max(c.winfo_height(), 40)
        c.create_rectangle(0, 0, w, h, fill=C["panel2"], outline=C["line"])
        c.create_text(10, 12, text="EQUITY", anchor="w", fill=C["brass"], font=_font(["Bahnschrift", "Segoe UI"], 9, "bold"))
        if len(self.points) < 2:
            c.create_text(w // 2, h // 2, text="waiting for samples…", fill=C["mute"], font=_font(["Cascadia Mono", "Consolas"], 9))
            return
        lo, hi = min(self.points), max(self.points)
        span = max(hi - lo, 1e-9)
        pad_x, pad_y = 8, 22
        coords: list[float] = []
        n = len(self.points)
        for i, v in enumerate(self.points):
            x = pad_x + (w - 2 * pad_x) * (i / (n - 1))
            y = h - pad_y - (h - pad_y - 10) * ((v - lo) / span)
            coords.extend([x, y])
        c.create_line(*coords, fill=C["signal"], width=2, smooth=True)
        c.create_text(w - 8, 12, text=f"{self.points[-1]:.2f}", anchor="e", fill=C["ink"], font=_font(["Cascadia Mono", "Consolas"], 9))


class DashboardApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("CHECK COMMAND · trading platform")
        self.root.geometry("1560x960")
        self.root.minsize(1280, 800)
        self.root.configure(bg=C["bg"])

        self.f_brand = _font(["Bahnschrift", "Segoe UI Variable Display", "Arial Black"], 26, "bold")
        self.f_h1 = _font(["Bahnschrift", "Segoe UI"], 12, "bold")
        self.f_kpi = _font(["Bahnschrift", "Segoe UI"], 16, "bold")
        self.f_ui = _font(["Bahnschrift", "Segoe UI"], 10)
        self.f_ui_b = _font(["Bahnschrift SemiBold", "Segoe UI"], 10, "bold")
        self.f_mono = _font(["Cascadia Mono", "Consolas", "Courier New"], 9)
        self.f_mono_b = _font(["Cascadia Mono", "Consolas"], 9, "bold")

        self.config_path = resolve_config()
        # Seed platform + push into system.json so EXE owns trading params.
        if not (ROOT / "config" / "platform.json").exists():
            platform_store.save_platform(platform_store.load_platform())
        platform_store.apply_platform_to_system_json(self.config_path)
        (ROOT / "clients").mkdir(parents=True, exist_ok=True)

        self.engine = EngineProcess()
        self.log_queue: queue.Queue[str] = queue.Queue()
        self._page = "floor"
        self._nav_btns: dict[str, tk.Button] = {}
        self._health = None
        self._report = None
        self._lot_vars: dict[str, tk.StringVar] = {}
        self._lot_dirty: dict[str, bool] = {}
        self._lot_meta: dict[str, dict] = {}
        self._accounts_built: tuple[str, ...] = ()
        self._suppress_lot_trace = False
        self._started_wall = time.time()
        self._focus_account: str | None = None
        self._pulse = 0.0
        self.foot_vars: dict[str, tk.StringVar] = {}
        self.kpi: dict[str, tk.StringVar] = {}
        self._setting_vars: dict[str, tk.StringVar] = {}
        self._clients_built: tuple[str, ...] = ()

        self._style_trees()
        self._build()
        self.refresh()
        self.root.after(70, self._motion_tick)
        self.root.after(700, self._tick)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _style_trees(self) -> None:
        style = ttk.Style()
        with contextlib.suppress(tk.TclError):
            style.theme_use("clam")
        style.configure(
            "Cmd.Treeview",
            background=C["panel2"],
            foreground=C["ink"],
            fieldbackground=C["panel2"],
            borderwidth=0,
            rowheight=26,
            font=self.f_mono,
        )
        style.configure(
            "Cmd.Treeview.Heading",
            background=C["panel"],
            foreground=C["brass"],
            relief="flat",
            font=self.f_ui_b,
        )
        style.map("Cmd.Treeview", background=[("selected", C["line"])], foreground=[("selected", C["ink"])])

    def _btn(self, parent: tk.Misc, text: str, color: str, command, *, padx: int = 12) -> tk.Button:
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=C["panel2"],
            fg=color,
            activebackground=C["line"],
            activeforeground=color,
            relief=tk.FLAT,
            bd=0,
            highlightthickness=1,
            highlightbackground=color,
            font=self.f_ui_b,
            padx=padx,
            pady=7,
            cursor="hand2",
        )

    def _build(self) -> None:
        shell = tk.Frame(self.root, bg=C["bg"])
        shell.pack(fill=tk.BOTH, expand=True)

        # ── Brand + master controls ───────────────────────────────────────
        top = tk.Frame(shell, bg=C["bg"])
        top.pack(fill=tk.X, padx=16, pady=(12, 0))
        left = tk.Frame(top, bg=C["bg"])
        left.pack(side=tk.LEFT)
        tk.Label(left, text="CHECK", bg=C["bg"], fg=C["brass"], font=self.f_brand).pack(side=tk.LEFT)
        tk.Label(left, text=" COMMAND", bg=C["bg"], fg=C["ink"], font=self.f_brand).pack(side=tk.LEFT)
        self.online_lbl = tk.Label(left, text="  ·  OFFLINE", bg=C["bg"], fg=C["stop"], font=self.f_h1)
        self.online_lbl.pack(side=tk.LEFT, padx=(8, 0), pady=(8, 0))
        self.subtitle = tk.Label(
            left,
            text="M1 platform · trend + breakout · EXE control plane",
            bg=C["bg"],
            fg=C["mute"],
            font=self.f_ui,
        )
        self.subtitle.pack(side=tk.LEFT, padx=14, pady=(10, 0))

        right = tk.Frame(top, bg=C["bg"])
        right.pack(side=tk.RIGHT)
        self._btn(right, "START LIVE", C["signal"], self._start_live).pack(side=tk.LEFT, padx=3)
        self._btn(right, "PAPER", C["sky"], self._start_paper).pack(side=tk.LEFT, padx=3)
        self._btn(right, "STOP", C["stop"], self._confirm_stop).pack(side=tk.LEFT, padx=3)
        self._btn(right, "DEPLOY", C["brass"], self._deploy).pack(side=tk.LEFT, padx=3)

        # ── Nav ───────────────────────────────────────────────────────────
        nav = tk.Frame(shell, bg=C["panel"], height=48)
        nav.pack(fill=tk.X, padx=0, pady=(10, 0))
        nav.pack_propagate(False)
        nav_in = tk.Frame(nav, bg=C["panel"])
        nav_in.pack(side=tk.LEFT, padx=12, pady=6)
        for key, label, accent in (
            ("floor", "FLOOR", C["brass"]),
            ("accounts", "ACCOUNTS", C["sky"]),
            ("tape", "TAPE", C["warn"]),
            ("settings", "SETTINGS", C["mute"]),
        ):
            btn = self._btn(nav_in, label, accent, lambda k=key: self._show_page(k))
            btn.pack(side=tk.LEFT, padx=3)
            self._nav_btns[key] = btn
        self.hint = tk.Label(nav, text="", bg=C["panel"], fg=C["mute"], font=self.f_mono)
        self.hint.pack(side=tk.RIGHT, padx=16)

        # ── KPI summary strip (always visible) ────────────────────────────
        kpi_wrap = tk.Frame(shell, bg=C["bg"])
        kpi_wrap.pack(fill=tk.X, padx=14, pady=(10, 0))
        self.kpi_frame = kpi_wrap
        for key, title, color in (
            ("equity", "EQUITY", C["signal"]),
            ("balance", "BALANCE", C["sky"]),
            ("float", "FLOAT P/L", C["brass"]),
            ("pos", "POSITIONS", C["ink"]),
            ("bridges", "BRIDGES", C["ok"]),
            ("day", "DAY OPEN/CLOSE", C["warn"]),
            ("stop", "STOP", C["stop"]),
            ("lot", "DEFAULT LOT", C["mute"]),
        ):
            self.kpi[key] = tk.StringVar(value="—")
            cell = tk.Frame(kpi_wrap, bg=C["panel"], highlightthickness=1, highlightbackground=C["line"])
            cell.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=3)
            tk.Label(cell, text=title, bg=C["panel"], fg=C["mute"], font=self.f_ui).pack(anchor="w", padx=10, pady=(6, 0))
            tk.Label(cell, textvariable=self.kpi[key], bg=C["panel"], fg=color, font=self.f_kpi).pack(anchor="w", padx=10, pady=(0, 8))

        # ── Pages ─────────────────────────────────────────────────────────
        mid = tk.Frame(shell, bg=C["bg"])
        mid.pack(fill=tk.BOTH, expand=True, padx=12, pady=8)
        self.pages: dict[str, tk.Frame] = {}
        self.pages["floor"] = self._page_floor(mid)
        self.pages["accounts"] = self._page_accounts(mid)
        self.pages["tape"] = self._page_tape(mid)
        self.pages["settings"] = self._page_settings(mid)

        self._build_footer(shell)
        self._show_page("floor")

    def _section(self, parent: tk.Misc, title: str, color: str) -> tk.Frame:
        box = tk.Frame(parent, bg=C["panel"], highlightthickness=1, highlightbackground=C["line"])
        head = tk.Frame(box, bg=C["panel"])
        head.pack(fill=tk.X)
        tk.Label(head, text=title, bg=C["panel"], fg=color, font=self.f_h1).pack(side=tk.LEFT, padx=10, pady=6)
        return box

    def _tree(self, parent: tk.Misc, columns: tuple[str, ...], headings: dict[str, str], widths: dict[str, int], *, height: int = 8) -> ttk.Treeview:
        wrap = tk.Frame(parent, bg=C["line"])
        wrap.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        tree = ttk.Treeview(
            wrap,
            columns=columns,
            show="headings",
            style="Cmd.Treeview",
            selectmode="browse",
            height=height,
        )
        vsb = ttk.Scrollbar(wrap, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        for col in columns:
            tree.heading(col, text=headings[col], anchor="w")
            tree.column(col, width=widths.get(col, 90), anchor="w", stretch=True, minwidth=50)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        tree.tag_configure("ok", foreground=C["ok"])
        tree.tag_configure("warn", foreground=C["warn"])
        tree.tag_configure("err", foreground=C["stop"])
        tree.tag_configure("mute", foreground=C["mute"])
        return tree

    def _page_floor(self, parent: tk.Misc) -> tk.Frame:
        frame = tk.Frame(parent, bg=C["bg"])

        # Row 1: system + day + equity
        row1 = tk.Frame(frame, bg=C["bg"])
        row1.pack(fill=tk.X, pady=(0, 8))

        sys_box = self._section(row1, "SYSTEM STATUS", C["brass"])
        sys_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 4))
        self.sys_tree = self._tree(
            sys_box,
            ("item", "value"),
            {"item": "ITEM", "value": "VALUE"},
            {"item": 140, "value": 220},
            height=7,
        )

        day_box = self._section(row1, "TODAY (UTC AUDIT)", C["warn"])
        day_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4)
        self.day_tree = self._tree(
            day_box,
            ("metric", "count"),
            {"metric": "METRIC", "count": "COUNT"},
            {"metric": 140, "count": 80},
            height=7,
        )

        eq_box = self._section(row1, "EQUITY CURVE", C["signal"])
        eq_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(4, 0))
        self.eq_canvas = tk.Canvas(eq_box, bg=C["panel2"], highlightthickness=0, height=190)
        self.eq_canvas.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        self.equity_chart = EquityChart(self.eq_canvas)

        # Row 2: accounts table (main)
        acc_box = self._section(frame, "ACCOUNTS / BRIDGES", C["sky"])
        acc_box.pack(fill=tk.BOTH, expand=True, pady=(0, 8))
        self.floor_tree = self._tree(
            acc_box,
            ("account", "equity", "balance", "float", "symbol", "bid", "ask", "market", "conn", "trade", "pos", "cmds", "lot"),
            {
                "account": "ACCOUNT",
                "equity": "EQUITY",
                "balance": "BALANCE",
                "float": "FLOAT",
                "symbol": "SYMBOL",
                "bid": "BID",
                "ask": "ASK",
                "market": "MARKET",
                "conn": "CONN",
                "trade": "TRADE",
                "pos": "POS",
                "cmds": "CMDS",
                "lot": "LOT",
            },
            {
                "account": 80,
                "equity": 85,
                "balance": 85,
                "float": 75,
                "symbol": 100,
                "bid": 85,
                "ask": 85,
                "market": 70,
                "conn": 55,
                "trade": 55,
                "pos": 45,
                "cmds": 50,
                "lot": 55,
            },
            height=8,
        )
        self.floor_tree.bind("<<TreeviewSelect>>", self._on_floor_select)

        # Row 3: positions
        pos_box = self._section(frame, "OPEN POSITIONS", C["signal"])
        pos_box.pack(fill=tk.BOTH, expand=True)
        self.pos_tree = self._tree(
            pos_box,
            ("account", "ticket", "symbol", "side", "lot", "entry", "price", "sl", "tp", "pl"),
            {
                "account": "ACCOUNT",
                "ticket": "TICKET",
                "symbol": "SYMBOL",
                "side": "SIDE",
                "lot": "LOT",
                "entry": "ENTRY",
                "price": "PRICE",
                "sl": "SL",
                "tp": "TP",
                "pl": "P/L",
            },
            {
                "account": 80,
                "ticket": 90,
                "symbol": 100,
                "side": 55,
                "lot": 55,
                "entry": 95,
                "price": 95,
                "sl": 95,
                "tp": 85,
                "pl": 80,
            },
            height=7,
        )
        return frame

    def _page_accounts(self, parent: tk.Misc) -> tk.Frame:
        frame = tk.Frame(parent, bg=C["bg"])
        head = tk.Frame(frame, bg=C["bg"])
        head.pack(fill=tk.X, pady=(0, 8))
        tk.Label(head, text="CLIENT ACCOUNTS", bg=C["bg"], fg=C["sky"], font=self.f_h1).pack(side=tk.LEFT)
        tk.Label(
            head,
            text="Add = login+password+server → clients/<id>/ + MT4 launch · Delete removes folder",
            bg=C["bg"],
            fg=C["mute"],
            font=self.f_ui,
        ).pack(side=tk.LEFT, padx=12)
        self._btn(head, "+ ADD ACCOUNT", C["signal"], self._dialog_add_client).pack(side=tk.RIGHT)

        clients_box = self._section(frame, "REGISTERED CLIENTS", C["sky"])
        clients_box.pack(fill=tk.BOTH, expand=True, pady=(0, 8))
        self.clients_host = tk.Frame(clients_box, bg=C["panel"])
        self.clients_host.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        self.clients_empty = tk.Label(
            self.clients_host,
            text="No clients yet — press + ADD ACCOUNT (login / password / server).",
            bg=C["panel"],
            fg=C["mute"],
            font=self.f_ui,
        )
        self.clients_empty.pack(pady=20)

        lot_box = self._section(frame, "LIVE BRIDGE LOT OVERRIDES", C["brass"])
        lot_box.pack(fill=tk.BOTH, expand=True)
        self.accounts_host = tk.Frame(lot_box, bg=C["panel"])
        self.accounts_host.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        self.accounts_empty = tk.Label(
            self.accounts_host,
            text="Bridge lots appear when MT4 exports status (or after you add a client).",
            bg=C["panel"],
            fg=C["mute"],
            font=self.f_ui,
        )
        self.accounts_empty.pack(pady=16)
        return frame

    def _page_tape(self, parent: tk.Misc) -> tk.Frame:
        frame = tk.Frame(parent, bg=C["bg"])
        split = tk.Frame(frame, bg=C["bg"])
        split.pack(fill=tk.BOTH, expand=True)
        left = self._section(split, "AUDIT TAPE", C["warn"])
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 4))
        right = self._section(split, "ENGINE LOG", C["sky"])
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(4, 0))
        self.tape = tk.Text(left, bg=C["panel2"], fg=C["ink"], relief=tk.FLAT, font=self.f_mono, wrap=tk.NONE)
        self.tape.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        self.tape.configure(state=tk.DISABLED)
        self.engine_log = tk.Text(right, bg=C["panel2"], fg=C["mute"], relief=tk.FLAT, font=self.f_mono, wrap=tk.NONE)
        self.engine_log.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        self.engine_log.configure(state=tk.DISABLED)
        return frame

    def _page_settings(self, parent: tk.Misc) -> tk.Frame:
        frame = tk.Frame(parent, bg=C["bg"])
        box = self._section(frame, "PLATFORM SETTINGS (EXE → engine)", C["brass"])
        box.pack(fill=tk.BOTH, expand=True)
        form = tk.Frame(box, bg=C["panel"])
        form.pack(fill=tk.BOTH, expand=True, padx=12, pady=8)

        fields = (
            ("fixed_lot", "LOT SIZE", "0.02"),
            ("force_stop_atr", "SL SIZE (ATR ×)", "1.0"),
            ("min_stop_atr", "MIN SL (ATR ×)", "0.6"),
            ("breakeven_trigger_atr", "BE START (ATR ×)", "0.75"),
            ("breakeven_offset_atr", "BE OFFSET (ATR ×)", "0.05"),
            ("trailing_start_atr", "TRAIL START (ATR ×)", "0.50"),
            ("trailing_lock_atr", "TRAIL LOCK (ATR ×)", "0.75"),
            ("symbol", "SYMBOL", "AUTO"),
            ("mt4_terminal_exe", "MT4 terminal.exe PATH", ""),
            ("cycle_interval_seconds", "CYCLE SEC", "5"),
        )
        plat = platform_store.load_platform()
        grid = tk.Frame(form, bg=C["panel"])
        grid.pack(fill=tk.X)
        for i, (key, label, default) in enumerate(fields):
            row = i // 2
            col = (i % 2) * 2
            tk.Label(grid, text=label, bg=C["panel"], fg=C["mute"], font=self.f_ui).grid(
                row=row, column=col, sticky="w", padx=(0, 8), pady=6
            )
            var = tk.StringVar(value=str(plat.get(key, default)))
            self._setting_vars[key] = var
            tk.Entry(
                grid,
                textvariable=var,
                bg=C["bg"],
                fg=C["ink"],
                insertbackground=C["brass"],
                relief=tk.FLAT,
                width=36 if key == "mt4_terminal_exe" else 14,
                font=self.f_mono,
                highlightthickness=1,
                highlightbackground=C["line"],
                highlightcolor=C["brass"],
            ).grid(row=row, column=col + 1, sticky="w", padx=(0, 24), pady=6)

        toggles = tk.Frame(form, bg=C["panel"])
        toggles.pack(fill=tk.X, pady=(8, 0))
        self._trend_var = tk.BooleanVar(value=bool(plat.get("trend_enabled", True)))
        self._breakout_var = tk.BooleanVar(value=bool(plat.get("breakout_enabled", True)))
        self._force_idle_var = tk.BooleanVar(value=bool(plat.get("force_entry_when_idle", True)))
        tk.Checkbutton(
            toggles, text="TREND UP/DOWN", variable=self._trend_var, bg=C["panel"], fg=C["ink"],
            selectcolor=C["bg"], activebackground=C["panel"], font=self.f_ui_b,
        ).pack(side=tk.LEFT, padx=(0, 16))
        tk.Checkbutton(
            toggles, text="BREAKOUT", variable=self._breakout_var, bg=C["panel"], fg=C["ink"],
            selectcolor=C["bg"], activebackground=C["panel"], font=self.f_ui_b,
        ).pack(side=tk.LEFT, padx=(0, 16))
        tk.Checkbutton(
            toggles, text="FORCE ENTRY WHEN IDLE", variable=self._force_idle_var, bg=C["panel"], fg=C["ink"],
            selectcolor=C["bg"], activebackground=C["panel"], font=self.f_ui_b,
        ).pack(side=tk.LEFT)

        row = tk.Frame(form, bg=C["panel"])
        row.pack(anchor="w", pady=16)
        self._btn(row, "SAVE SETTINGS", C["signal"], self._save_platform_settings).pack(side=tk.LEFT, padx=4)
        self._btn(row, "ENABLE TRADING", C["ok"], lambda: self._set_trading(True)).pack(side=tk.LEFT, padx=4)
        self._btn(row, "DISABLE TRADING", C["warn"], lambda: self._set_trading(False)).pack(side=tk.LEFT, padx=4)
        self._btn(row, "CLEAR STOP", C["sky"], self._clear_stop).pack(side=tk.LEFT, padx=4)
        self._btn(row, "DEPLOY MT4 EA", C["brass"], self._deploy).pack(side=tk.LEFT, padx=4)

        self.settings_info = tk.Label(form, text="", bg=C["panel"], fg=C["mute"], font=self.f_mono, justify=tk.LEFT, anchor="nw")
        self.settings_info.pack(fill=tk.X, pady=(8, 0))
        return frame

    def _save_platform_settings(self) -> None:
        try:
            payload = platform_store.load_platform()
            for key, var in self._setting_vars.items():
                raw = var.get().strip()
                if key in {
                    "fixed_lot",
                    "force_stop_atr",
                    "min_stop_atr",
                    "breakeven_trigger_atr",
                    "breakeven_offset_atr",
                    "trailing_start_atr",
                    "trailing_lock_atr",
                    "cycle_interval_seconds",
                    "min_lot",
                    "max_lot",
                }:
                    payload[key] = float(raw.replace(",", "."))
                else:
                    payload[key] = raw
            payload["trend_enabled"] = bool(self._trend_var.get())
            payload["breakout_enabled"] = bool(self._breakout_var.get())
            payload["force_entry_when_idle"] = bool(self._force_idle_var.get())
            platform_store.save_platform(payload)
            platform_store.apply_platform_to_system_json(self.config_path)
            messagebox.showinfo("Settings", "Saved. Engine uses these on next cycle / restart.")
            self.refresh()
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Settings", str(exc))

    def _dialog_add_client(self) -> None:
        win = tk.Toplevel(self.root)
        win.title("Add MT4 account")
        win.configure(bg=C["panel"])
        win.geometry("460x320")
        win.transient(self.root)
        win.grab_set()
        fields = {}
        for i, (key, label) in enumerate(
            (
                ("label", "Label"),
                ("login", "Login (account number)"),
                ("password", "Password"),
                ("server", "Server"),
                ("lot", "Lot (optional)"),
            )
        ):
            tk.Label(win, text=label, bg=C["panel"], fg=C["mute"], font=self.f_ui).pack(anchor="w", padx=16, pady=(10 if i == 0 else 4, 0))
            show = "*" if key == "password" else ""
            var = tk.StringVar()
            fields[key] = var
            tk.Entry(
                win,
                textvariable=var,
                show=show,
                bg=C["bg"],
                fg=C["ink"],
                insertbackground=C["brass"],
                relief=tk.FLAT,
                font=self.f_mono,
                highlightthickness=1,
                highlightbackground=C["line"],
            ).pack(fill=tk.X, padx=16)

        def save() -> None:
            try:
                lot_raw = fields["lot"].get().strip()
                lot = float(lot_raw.replace(",", ".")) if lot_raw else None
                client = platform_store.add_client(
                    login=fields["login"].get(),
                    password=fields["password"].get(),
                    server=fields["server"].get(),
                    label=fields["label"].get(),
                    lot=lot,
                    mt4_terminal_exe=platform_store.load_platform().get("mt4_terminal_exe"),
                )
                win.destroy()
                self._clients_built = ()
                messagebox.showinfo(
                    "Client",
                    f"Created clients/{client['id']}/\n"
                    f"Bridge: {client['bridge_dir']}\n"
                    f"Launch: clients/{client['id']}/launch_mt4.bat\n"
                    f"Set EA BridgeRootPath to that bridge parent (see BRIDGE_PATH.txt).",
                )
                self._show_page("accounts")
            except Exception as exc:  # noqa: BLE001
                messagebox.showerror("Add account", str(exc))

        self._btn(win, "CREATE + LAUNCH FOLDER", C["signal"], save).pack(pady=16)

    def _delete_client(self, client_id: str) -> None:
        if not messagebox.askyesno("Delete", f"Delete client {client_id} and its MT4 workspace folder?"):
            return
        try:
            platform_store.delete_client(client_id)
            self._clients_built = ()
            self.refresh()
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Delete", str(exc))

    def _launch_client(self, client_id: str) -> None:
        ok, msg = platform_store.launch_client_mt4(client_id)
        if ok:
            messagebox.showinfo("MT4", msg)
        else:
            messagebox.showwarning("MT4", msg)

    def _rebuild_client_rows(self) -> None:
        clients = platform_store.list_clients()
        sig = tuple(str(c.get("id")) for c in clients)
        if sig == self._clients_built and self.clients_host.winfo_children():
            # still rebuild labels lightly — force full rebuild when page shown
            pass
        for child in list(self.clients_host.winfo_children()):
            if child is self.clients_empty:
                continue
            child.destroy()
        self._clients_built = sig
        if not clients:
            self.clients_empty.pack(pady=20)
            return
        self.clients_empty.pack_forget()
        header = tk.Frame(self.clients_host, bg=C["panel2"])
        header.pack(fill=tk.X, pady=(0, 4))
        for text in ("ID", "LOGIN", "SERVER", "LABEL", "ACTIONS"):
            tk.Label(header, text=text, bg=C["panel2"], fg=C["brass"], font=self.f_ui_b, width=14, anchor="w").pack(
                side=tk.LEFT, padx=4, pady=4
            )
        for row in clients:
            cid = str(row.get("id"))
            full = platform_store.read_client(cid) or row
            line = tk.Frame(self.clients_host, bg=C["panel2"])
            line.pack(fill=tk.X, pady=2)
            for text, w in (
                (cid, 14),
                (str(full.get("login") or ""), 14),
                (str(full.get("server") or ""), 14),
                (str(full.get("label") or ""), 14),
            ):
                tk.Label(line, text=text, bg=C["panel2"], fg=C["ink"], font=self.f_mono, width=w, anchor="w").pack(
                    side=tk.LEFT, padx=4, pady=6
                )
            self._btn(line, "LAUNCH MT4", C["signal"], lambda c=cid: self._launch_client(c), padx=8).pack(side=tk.LEFT, padx=2)
            self._btn(line, "DELETE", C["stop"], lambda c=cid: self._delete_client(c), padx=8).pack(side=tk.LEFT, padx=2)

    def _build_footer(self, parent: tk.Misc) -> None:
        foot = tk.Frame(parent, bg=C["panel"], height=42)
        foot.pack(fill=tk.X, side=tk.BOTTOM)
        foot.pack_propagate(False)
        inner = tk.Frame(foot, bg=C["panel"])
        inner.pack(fill=tk.BOTH, expand=True, padx=14)
        self.foot_vars = {
            "uptime": tk.StringVar(value="0m 0s"),
            "engine": tk.StringVar(value="DOWN"),
            "conn": tk.StringVar(value="NONE"),
            "reason": tk.StringVar(value="—"),
            "time": tk.StringVar(value="—"),
        }
        for label, key, color in (
            ("UPTIME", "uptime", C["ok"]),
            ("ENGINE", "engine", C["sky"]),
            ("CONN", "conn", C["signal"]),
            ("LAST REASON", "reason", C["warn"]),
            ("LOCAL", "time", C["mute"]),
        ):
            cell = tk.Frame(inner, bg=C["panel"])
            cell.pack(side=tk.LEFT, expand=True, fill=tk.X)
            tk.Label(cell, text=label, bg=C["panel"], fg=C["mute"], font=self.f_ui).pack(anchor="w", pady=(4, 0))
            tk.Label(cell, textvariable=self.foot_vars[key], bg=C["panel"], fg=color, font=self.f_ui_b).pack(anchor="w")

    def _show_page(self, key: str) -> None:
        self._page = key
        for name, frame in self.pages.items():
            if name == key:
                frame.pack(fill=tk.BOTH, expand=True)
            else:
                frame.pack_forget()
        for name, btn in self._nav_btns.items():
            accent = {"floor": C["brass"], "accounts": C["sky"], "tape": C["warn"], "settings": C["mute"]}.get(name, C["mute"])
            if name == key:
                btn.configure(bg=C["line"], fg=C["ink"], highlightbackground=C["ink"])
            else:
                btn.configure(bg=C["panel2"], fg=accent, highlightbackground=accent)
        if key in {"floor", "accounts", "settings"}:
            self.refresh()

    def _on_floor_select(self, _event=None) -> None:
        sel = self.floor_tree.selection()
        if not sel:
            return
        vals = self.floor_tree.item(sel[0], "values")
        if not vals:
            return
        acct = str(vals[0])
        if acct and acct not in {"—", "(no bridges)"}:
            self._focus_account = acct
            self._show_page("accounts")

    # ── engine / config ────────────────────────────────────────────────────
    def _cfg_data(self) -> dict:
        return load_config_json(self.config_path)

    def _rt(self) -> Path:
        return runtime_dir(self._cfg_data())

    def _start_live(self) -> None:
        if self.engine.running:
            messagebox.showinfo("Engine", "Engine already running")
            return
        if sync_system_json is not None:
            with contextlib.suppress(Exception):
                sync_system_json(self.config_path, ROOT / "config" / "system.example.json")
        arm_live_runtime(self.config_path)
        ok, detail = validate_live_config(self.config_path)
        if not ok:
            messagebox.showerror("Live validation", detail)
            return
        clear_stop(self._rt())
        try:
            self.engine.start(mode="live", config_path=self.config_path)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Engine", str(exc))
            return
        self._pump_engine_logs()
        self.refresh()

    def _start_paper(self) -> None:
        if self.engine.running:
            messagebox.showinfo("Engine", "Engine already running")
            return
        if sync_system_json is not None:
            with contextlib.suppress(Exception):
                sync_system_json(self.config_path, ROOT / "config" / "system.example.json")
        clear_stop(self._rt())
        try:
            self.engine.start(mode="paper", config_path=self.config_path)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Engine", str(exc))
            return
        self._pump_engine_logs()
        self.refresh()

    def _pump_engine_logs(self) -> None:
        proc = getattr(self.engine, "proc", None)
        if proc is None or proc.stdout is None:
            return

        def reader() -> None:
            for line in proc.stdout:
                self.log_queue.put(line.rstrip("\n"))

        threading.Thread(target=reader, daemon=True).start()

    def _confirm_stop(self) -> None:
        if not messagebox.askyesno("STOP", "Write STOP_TRADING and stop the engine?"):
            return
        write_stop(self._rt())
        self.engine.stop_hard()
        self.refresh()

    def _clear_stop(self) -> None:
        clear_stop(self._rt())
        self.refresh()

    def _set_trading(self, enabled: bool) -> None:
        set_trading_enabled(self.config_path, enabled)
        self.refresh()

    def _deploy(self) -> None:
        code, out = run_deploy_mt4()
        messagebox.showinfo("Deploy MT4", out if out else f"exit={code}")

    def _save_lot(self, account_id: str) -> None:
        var = self._lot_vars.get(account_id)
        if var is None:
            return
        try:
            lot = float(var.get().replace(",", "."))
        except ValueError:
            messagebox.showerror("Lot", f"Invalid lot for {account_id}")
            return
        mn, mx, _ = lot_bounds(self._cfg_data())
        if lot < mn or lot > mx:
            messagebox.showerror("Lot", f"Lot must be {mn}…{mx}")
            return
        write_account_lot_override(self._rt(), account_id, lot)
        self._set_lot_var(account_id, f"{lot:.2f}")
        self._lot_dirty[account_id] = False
        messagebox.showinfo("Lot", f"{account_id} → fixed_lot={lot:.2f}")
        if account_id in self._lot_meta:
            self._lot_meta[account_id]["source"].configure(text="override", fg=C["brass"])

    def _reset_lot(self, account_id: str) -> None:
        clear_account_lot_override(self._rt(), account_id)
        default_lot = default_fixed_lot(self._cfg_data())
        self._set_lot_var(account_id, f"{default_lot:.2f}")
        self._lot_dirty[account_id] = False
        if account_id in self._lot_meta:
            self._lot_meta[account_id]["source"].configure(text="config", fg=C["mute"])

    def _mark_lot_dirty(self, account_id: str, *_args) -> None:
        if self._suppress_lot_trace:
            return
        self._lot_dirty[account_id] = True

    def _set_lot_var(self, account_id: str, value: str) -> None:
        var = self._lot_vars.get(account_id)
        if var is None:
            return
        self._suppress_lot_trace = True
        try:
            var.set(value)
        finally:
            self._suppress_lot_trace = False

    def _entry_focused(self, account_id: str) -> bool:
        meta = self._lot_meta.get(account_id)
        if not meta:
            return False
        entry = meta.get("entry")
        return bool(entry and entry.focus_get() is entry)

    def _sync_account_rows(self, health) -> None:
        cfg = self._cfg_data()
        rt = self._rt()
        default_lot = default_fixed_lot(cfg)
        accounts = tuple(list_known_accounts(health, rt))
        if accounts != self._accounts_built:
            self._rebuild_account_rows(health, accounts, default_lot, rt)
            return
        bridge_by = {b.account_id: b for b in health.bridges}
        for acct in accounts:
            meta = self._lot_meta.get(acct)
            if not meta:
                continue
            b = bridge_by.get(acct)
            eq = f"{b.equity:.2f}" if b else "—"
            sym = (b.symbol if b and b.symbol else health.symbol) or "—"
            override = read_account_lot_override(rt, acct)
            src = "override" if override is not None else "config"
            src_c = C["brass"] if override is not None else C["mute"]
            focused = self._focus_account == acct
            meta["row"].configure(bg=C["line"] if focused else C["panel2"])
            meta["account"].configure(text=acct, bg=meta["row"]["bg"])
            meta["balance"].configure(text=eq, bg=meta["row"]["bg"])
            meta["symbol"].configure(text=str(sym), bg=meta["row"]["bg"])
            meta["source"].configure(text=src, fg=src_c, bg=meta["row"]["bg"])
            if self._lot_dirty.get(acct) or self._entry_focused(acct):
                continue
            effective = override if override is not None else default_lot
            target = f"{effective:.2f}"
            if self._lot_vars[acct].get().strip() != target:
                self._set_lot_var(acct, target)

    def _rebuild_account_rows(
        self,
        health,
        accounts: tuple[str, ...] | None = None,
        default_lot: float | None = None,
        rt: Path | None = None,
    ) -> None:
        cfg = self._cfg_data()
        rt = self._rt() if rt is None else rt
        default_lot = default_fixed_lot(cfg) if default_lot is None else default_lot
        accounts = accounts if accounts is not None else tuple(list_known_accounts(health, rt))
        for child in list(self.accounts_host.winfo_children()):
            if child is self.accounts_empty:
                continue
            child.destroy()
        self._lot_vars.clear()
        self._lot_meta.clear()
        self._lot_dirty = {k: v for k, v in self._lot_dirty.items() if k in accounts}
        self._accounts_built = accounts
        if not accounts:
            self.accounts_empty.pack(pady=40)
            return
        self.accounts_empty.pack_forget()
        bridge_by = {b.account_id: b for b in health.bridges}
        header = tk.Frame(self.accounts_host, bg=C["panel"])
        header.pack(fill=tk.X, pady=(0, 4))
        for text in ("ACCOUNT", "EQUITY", "SYMBOL", "LOT", "SOURCE", "ACTIONS"):
            tk.Label(header, text=text, bg=C["panel"], fg=C["brass"], font=self.f_ui_b, width=12, anchor="w").pack(
                side=tk.LEFT, padx=6, pady=6
            )
        for acct in accounts:
            focused = self._focus_account == acct
            row = tk.Frame(self.accounts_host, bg=C["line"] if focused else C["panel2"])
            row.pack(fill=tk.X, pady=2)
            b = bridge_by.get(acct)
            eq = f"{b.equity:.2f}" if b else "—"
            sym = (b.symbol if b and b.symbol else health.symbol) or "—"
            override = read_account_lot_override(rt, acct)
            effective = override if override is not None else default_lot
            src = "override" if override is not None else "config"
            var = tk.StringVar(value=f"{effective:.2f}")
            self._lot_vars[acct] = var
            var.trace_add("write", lambda *_a, a=acct: self._mark_lot_dirty(a))
            lbl_acct = tk.Label(row, text=acct, bg=row["bg"], fg=C["ink"], font=self.f_mono_b, width=12, anchor="w")
            lbl_acct.pack(side=tk.LEFT, padx=6, pady=8)
            lbl_bal = tk.Label(row, text=eq, bg=row["bg"], fg=C["signal"], font=self.f_mono, width=12, anchor="w")
            lbl_bal.pack(side=tk.LEFT, padx=6)
            lbl_sym = tk.Label(row, text=str(sym), bg=row["bg"], fg=C["mute"], font=self.f_mono, width=12, anchor="w")
            lbl_sym.pack(side=tk.LEFT, padx=6)
            entry = tk.Entry(
                row,
                textvariable=var,
                bg=C["bg"],
                fg=C["ink"],
                insertbackground=C["brass"],
                relief=tk.FLAT,
                width=8,
                font=self.f_mono,
                highlightthickness=1,
                highlightbackground=C["line"],
                highlightcolor=C["brass"],
            )
            entry.pack(side=tk.LEFT, padx=6)
            lbl_src = tk.Label(
                row,
                text=src,
                bg=row["bg"],
                fg=C["brass"] if override is not None else C["mute"],
                font=self.f_ui,
                width=10,
                anchor="w",
            )
            lbl_src.pack(side=tk.LEFT, padx=6)
            self._btn(row, "SAVE", C["signal"], lambda a=acct: self._save_lot(a), padx=10).pack(side=tk.LEFT, padx=4)
            self._btn(row, "RESET", C["mute"], lambda a=acct: self._reset_lot(a), padx=10).pack(side=tk.LEFT, padx=2)
            self._lot_meta[acct] = {
                "row": row,
                "account": lbl_acct,
                "balance": lbl_bal,
                "symbol": lbl_sym,
                "source": lbl_src,
                "entry": entry,
            }
            self._lot_dirty.setdefault(acct, False)

    def _fill_tree(self, tree: ttk.Treeview, rows: list[tuple]) -> None:
        tree.delete(*tree.get_children())
        for values, tag in rows:
            tree.insert("", tk.END, values=values, tags=(tag,))

    def refresh(self) -> None:
        health = collect_health(self.config_path)
        self._health = health
        cfg = self._cfg_data()
        rt = self._rt()
        with contextlib.suppress(Exception):
            record_equity_samples(health.bridges, rt)
        report = build_floor_report(health, audit_path=audit_file(cfg))
        self._report = report

        online = self.engine.running or report.connected > 0
        self.online_lbl.configure(
            text=f"  ·  {'ONLINE' if online else 'OFFLINE'}",
            fg=C["signal"] if online else C["stop"],
        )
        self.hint.configure(
            text=f"{report.symbol}  |  mode={report.mode}  |  trade={'ON' if report.trading_enabled else 'OFF'}  |  "
            f"{report.last_decision}/{report.last_reason}"
        )

        # KPI strip — always numbers, never blank
        self.kpi["equity"].set(f"{report.equity_total:.2f}" if report.bridge_count else "0.00")
        self.kpi["balance"].set(f"{report.balance_total:.2f}" if report.bridge_count else "0.00")
        self.kpi["float"].set(f"{report.floating_pl:+.2f}")
        self.kpi["pos"].set(str(report.positions))
        self.kpi["bridges"].set(f"{report.connected}/{report.bridge_count}" if report.bridge_count else "0/0")
        self.kpi["day"].set(f"{report.day_opens}/{report.day_closes}")
        self.kpi["stop"].set("ARMED" if report.stop_present else "clear")
        self.kpi["lot"].set(f"{default_fixed_lot(cfg):.2f}")

        # System status table
        eng = "UP" if self.engine.running else "DOWN"
        eng_mode = (self.engine.mode or "off").upper()
        self._fill_tree(
            self.sys_tree,
            [
                (("Engine", f"{eng} · {eng_mode} · pid={self.engine.pid or '—'}"), "ok" if self.engine.running else "err"),
                (("Mode", report.mode), "ok"),
                (("Trading", "ENABLED" if report.trading_enabled else "DISABLED"), "ok" if report.trading_enabled else "warn"),
                (("STOP file", "ARMED" if report.stop_present else "clear"), "err" if report.stop_present else "ok"),
                (("Symbol", report.symbol), "mute"),
                (("Commands backlog", str(report.commands)), "warn" if report.commands else "ok"),
                (("Stale bridges", str(report.stale)), "err" if report.stale else "ok"),
            ],
        )

        # Day table
        self._fill_tree(
            self.day_tree,
            [
                (("OPEN", str(report.day_opens)), "ok"),
                (("CLOSE", str(report.day_closes)), "warn"),
                (("MODIFY", str(report.day_modifies)), "mute"),
                (("BLOCK", str(report.day_blocks)), "err" if report.day_blocks else "mute"),
                (("HOLD", str(report.day_holds)), "mute"),
                (("Last decision", report.last_decision), "ok"),
                (("Last reason", report.last_reason[:28]), "warn"),
            ],
        )

        # Equity chart
        series = load_equity_series(limit=120, rt=rt)
        self.equity_chart.set_points([v for _ts, v in series])

        # Accounts table
        default_lot = default_fixed_lot(cfg)
        floor_rows: list[tuple] = []
        for b in health.bridges:
            override = read_account_lot_override(rt, b.account_id)
            lot = override if override is not None else default_lot
            fl = b.floating_pl if b.floating_pl else sum(p.profit for p in b.positions)
            tag = "ok" if b.connected and (b.market_age_s is not None and b.market_age_s <= 30) else (
                "warn" if b.connected else "err"
            )
            floor_rows.append(
                (
                    (
                        b.account_id,
                        f"{b.equity:.2f}",
                        f"{b.balance:.2f}",
                        f"{fl:+.2f}",
                        b.symbol or report.symbol,
                        f"{b.bid:.5f}" if b.bid else "—",
                        f"{b.ask:.5f}" if b.ask else "—",
                        format_age(b.market_age_s),
                        "YES" if b.connected else "NO",
                        "YES" if b.trading_allowed else "NO",
                        str(len(b.positions)),
                        str(b.commands),
                        f"{lot:.2f}",
                    ),
                    tag,
                )
            )
        known = set(list_known_accounts(health, rt))
        seen = {b.account_id for b in health.bridges}
        for acct in sorted(known - seen):
            override = read_account_lot_override(rt, acct)
            lot = override if override is not None else default_lot
            floor_rows.append(
                (
                    (acct, "—", "—", "—", report.symbol, "—", "—", "—", "—", "—", "0", "0", f"{lot:.2f}"),
                    "mute",
                )
            )
        if not floor_rows:
            floor_rows = [
                (
                    ("(no bridges)", "0.00", "0.00", "+0.00", report.symbol, "—", "—", "—", "NO", "NO", "0", "0", f"{default_lot:.2f}"),
                    "mute",
                )
            ]
        self._fill_tree(self.floor_tree, floor_rows)

        # Positions
        pos_rows: list[tuple] = []
        for b in health.bridges:
            for p in b.positions:
                tag = "ok" if p.profit >= 0 else "err"
                cur = p.current_price
                pos_rows.append(
                    (
                        (
                            b.account_id,
                            str(p.ticket),
                            p.symbol,
                            p.side,
                            f"{p.lot:.2f}",
                            f"{p.open_price:.5f}" if p.open_price else "—",
                            f"{cur:.5f}" if cur else "—",
                            f"{p.stop_loss:.5f}" if p.stop_loss else "—",
                            f"{p.take_profit:.5f}" if p.take_profit else "—",
                            f"{p.profit:+.2f}",
                        ),
                        tag,
                    )
                )
        if not pos_rows:
            pos_rows = [(("(flat)", "—", "—", "—", "—", "—", "—", "—", "—", "—"), "mute")]
        self._fill_tree(self.pos_tree, pos_rows)

        # Tape
        lines = [format_audit_line(e) for e in audit_activity(audit_file(cfg), limit=80)]
        self._set_text(self.tape, "\n".join(lines) if lines else "(audit empty — start engine to fill tape)")

        drained: list[str] = []
        while True:
            try:
                drained.append(self.log_queue.get_nowait())
            except queue.Empty:
                break
        if drained:
            self.engine_log.configure(state=tk.NORMAL)
            self.engine_log.insert(tk.END, "\n".join(drained) + "\n")
            self.engine_log.see(tk.END)
            self.engine_log.configure(state=tk.DISABLED)

        pos_cfg = cfg.get("position_sizing") or cfg.get("position") or {}
        self.settings_info.configure(
            text=(
                f"config: {self.config_path}\n"
                f"runtime: {rt}\n"
                f"mode: {report.mode}   trading_enabled: {report.trading_enabled}   stop: {report.stop_present}\n"
                f"symbol: {report.symbol}\n"
                f"default lot: {pos_cfg.get('fixed_lot') or pos_cfg.get('default_lot')}   "
                f"min/max: {pos_cfg.get('min_lot')}/{pos_cfg.get('max_lot')}\n"
                f"engine: {eng}  pid={self.engine.pid}  mode={self.engine.mode}\n"
                f"bridges: {report.bridge_count} connected={report.connected} stale={report.stale}\n"
                f"day: open={report.day_opens} close={report.day_closes} modify={report.day_modifies} "
                f"block={report.day_blocks} hold={report.day_holds}"
            )
        )

        if self._page == "accounts":
            self._rebuild_client_rows()
            self._sync_account_rows(health)
        if self._page == "settings":
            # keep form values; only refresh info strip
            pass

        if self.foot_vars:
            uptime = int(time.time() - self._started_wall)
            self.foot_vars["uptime"].set(f"{uptime // 60}m {uptime % 60}s")
            self.foot_vars["engine"].set(f"{eng_mode} · {eng}")
            self.foot_vars["conn"].set(
                "STABLE" if report.connected else ("DEGRADED" if report.bridge_count else "NONE")
            )
            self.foot_vars["reason"].set(f"{report.last_decision} / {report.last_reason}"[:42])
            self.foot_vars["time"].set(time.strftime("%H:%M:%S"))

    def _set_text(self, widget: tk.Text, text: str) -> None:
        widget.configure(state=tk.NORMAL)
        widget.delete("1.0", tk.END)
        widget.insert("1.0", text)
        widget.configure(state=tk.DISABLED)

    def _motion_tick(self) -> None:
        self._pulse = (self._pulse + 0.09) % math.tau
        if self._report and self._report.stop_present:
            self.kpi["stop"].set("ARMED" if math.sin(self._pulse * 3) > 0 else "ARMED ·")
        self.root.after(70, self._motion_tick)

    def _tick(self) -> None:
        with contextlib.suppress(Exception):
            self.refresh()
        self.root.after(700, self._tick)

    def _on_close(self) -> None:
        if self.engine.running:
            if messagebox.askyesno("Quit", "Engine is running. Stop and quit?"):
                with contextlib.suppress(Exception):
                    write_stop(self._rt())
                with contextlib.suppress(Exception):
                    self.engine.stop_hard()
            else:
                return
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    try:
        root.state("zoomed")
    except tk.TclError:
        with contextlib.suppress(tk.TclError):
            root.attributes("-zoomed", True)
    DashboardApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
