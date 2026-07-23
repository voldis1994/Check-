"""CHECK LEDGER — multi-account trading floor console (Tkinter).

Table-first ops desk: accounts, bridges, positions, audit tape.
No brain / neural HUD — real rows you can read and edit.
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
    clear_account_lot_override,
    clear_stop,
    collect_health,
    default_fixed_lot,
    format_age,
    format_audit_line,
    list_known_accounts,
    load_config_json,
    lot_bounds,
    read_account_lot_override,
    resolve_config,
    run_deploy_mt4,
    runtime_dir,
    set_trading_enabled,
    validate_live_config,
    write_account_lot_override,
    write_stop,
)

try:
    from checktrader.config.migrate import sync_system_json
except Exception:  # noqa: BLE001
    sync_system_json = None  # type: ignore[assignment]

# Ledger desk palette — forest ink + brass (not purple / not cream-serif).
C = {
    "void": "#0A1210",
    "panel": "#12201C",
    "panel2": "#183028",
    "line": "#254038",
    "ink": "#E8F0EC",
    "mute": "#7A9188",
    "brass": "#D4A84B",
    "signal": "#3DDC97",
    "sky": "#4DB6C6",
    "warn": "#E0A045",
    "stop": "#E85D4C",
    "ok": "#5EE0A0",
}


def _font(cands: list[str], size: int, weight: str = "normal") -> tuple:
    fam = set(tkfont.families())
    for name in cands:
        if name in fam:
            return (name, size, weight) if weight != "normal" else (name, size)
    return ("TkDefaultFont", size, weight) if weight != "normal" else ("TkDefaultFont", size)


class BrandBar:
    """Full-bleed brand strip with a slow ledger scan line."""

    def __init__(self, canvas: tk.Canvas) -> None:
        self.canvas = canvas
        self.phase = 0.0
        self._online = False
        self._mode = "—"
        canvas.bind("<Configure>", lambda _e: self.draw())

    def set_status(self, *, online: bool, mode: str) -> None:
        self._online = online
        self._mode = mode

    def tick(self) -> None:
        self.phase = (self.phase + 0.045) % 1.0
        self.draw()

    def draw(self) -> None:
        c = self.canvas
        c.delete("all")
        w = max(c.winfo_width(), 100)
        h = max(c.winfo_height(), 40)
        c.create_rectangle(0, 0, w, h, fill=C["void"], outline="")
        # Blueprint hatch
        for i in range(0, w + 40, 28):
            x = (i + self.phase * 28) % (w + 40) - 20
            c.create_line(x, 0, x + 18, h, fill="#0F1C18", width=1)
        # Brand
        c.create_text(22, h * 0.42, text="CHECK", anchor="w", fill=C["brass"], font=_font(["Bahnschrift", "Segoe UI"], 32, "bold"))
        c.create_text(168, h * 0.48, text="LEDGER", anchor="w", fill=C["ink"], font=_font(["Bahnschrift", "Segoe UI"], 22, "bold"))
        c.create_text(290, h * 0.52, text="multi-account floor · tables only", anchor="w", fill=C["mute"], font=_font(["Cascadia Mono", "Consolas"], 9))
        # Status pill text (not a floating badge overlay — part of brand row)
        st = "ONLINE" if self._online else "OFFLINE"
        st_c = C["signal"] if self._online else C["stop"]
        c.create_text(w - 24, h * 0.35, text=st, anchor="e", fill=st_c, font=_font(["Bahnschrift", "Segoe UI"], 14, "bold"))
        c.create_text(w - 24, h * 0.68, text=f"mode {self._mode}", anchor="e", fill=C["mute"], font=_font(["Cascadia Mono", "Consolas"], 9))
        # Scan line
        y = 4 + (h - 8) * self.phase
        c.create_line(0, y, w, y, fill=C["signal"], width=1)


class DashboardApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("CHECK LEDGER · trading floor")
        self.root.geometry("1480x900")
        self.root.minsize(1180, 720)
        self.root.configure(bg=C["void"])

        self.f_h1 = _font(["Bahnschrift", "Segoe UI"], 13, "bold")
        self.f_ui = _font(["Bahnschrift", "Segoe UI"], 10)
        self.f_ui_b = _font(["Bahnschrift SemiBold", "Segoe UI"], 10, "bold")
        self.f_mono = _font(["Cascadia Mono", "Consolas", "Courier New"], 9)
        self.f_mono_b = _font(["Cascadia Mono", "Consolas"], 9, "bold")

        self.config_path = resolve_config()
        self.engine = EngineProcess()
        self.log_queue: queue.Queue[str] = queue.Queue()
        self._page = "floor"
        self._nav_btns: dict[str, tk.Button] = {}
        self._health = None
        self._lot_vars: dict[str, tk.StringVar] = {}
        self._lot_dirty: dict[str, bool] = {}
        self._lot_meta: dict[str, dict] = {}
        self._accounts_built: tuple[str, ...] = ()
        self._suppress_lot_trace = False
        self._started_wall = time.time()
        self._focus_account: str | None = None
        self._pulse = 0.0

        self._style_trees()
        self._build()
        self.refresh()
        self.root.after(80, self._motion_tick)
        self.root.after(800, self._tick)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _style_trees(self) -> None:
        style = ttk.Style()
        with contextlib.suppress(tk.TclError):
            style.theme_use("clam")
        style.configure(
            "Ledger.Treeview",
            background=C["panel2"],
            foreground=C["ink"],
            fieldbackground=C["panel2"],
            borderwidth=0,
            rowheight=28,
            font=self.f_mono,
        )
        style.configure(
            "Ledger.Treeview.Heading",
            background=C["panel"],
            foreground=C["brass"],
            relief="flat",
            font=self.f_ui_b,
        )
        style.map(
            "Ledger.Treeview",
            background=[("selected", C["line"])],
            foreground=[("selected", C["ink"])],
        )

    def _build(self) -> None:
        shell = tk.Frame(self.root, bg=C["void"])
        shell.pack(fill=tk.BOTH, expand=True)

        self.brand_canvas = tk.Canvas(shell, height=72, bg=C["void"], highlightthickness=0)
        self.brand_canvas.pack(fill=tk.X)
        self.brand = BrandBar(self.brand_canvas)

        self._build_controls(shell)

        # Metric strip — plain labels, not cards
        metrics = tk.Frame(shell, bg=C["void"])
        metrics.pack(fill=tk.X, padx=18, pady=(10, 0))
        self.metric_vars = {
            "equity": tk.StringVar(value="—"),
            "bridges": tk.StringVar(value="—"),
            "positions": tk.StringVar(value="—"),
            "stop": tk.StringVar(value="—"),
            "lot": tk.StringVar(value="—"),
        }
        for title, key, color in (
            ("EQUITY", "equity", C["signal"]),
            ("BRIDGES", "bridges", C["sky"]),
            ("POSITIONS", "positions", C["brass"]),
            ("STOP", "stop", C["stop"]),
            ("DEFAULT LOT", "lot", C["ok"]),
        ):
            cell = tk.Frame(metrics, bg=C["void"])
            cell.pack(side=tk.LEFT, padx=(0, 28))
            tk.Label(cell, text=title, bg=C["void"], fg=C["mute"], font=self.f_ui).pack(anchor="w")
            tk.Label(cell, textvariable=self.metric_vars[key], bg=C["void"], fg=color, font=self.f_h1).pack(anchor="w")

        mid = tk.Frame(shell, bg=C["void"])
        mid.pack(fill=tk.BOTH, expand=True, padx=16, pady=10)
        self.pages: dict[str, tk.Frame] = {}
        self.pages["floor"] = self._page_floor(mid)
        self.pages["accounts"] = self._page_accounts(mid)
        self.pages["positions"] = self._page_positions(mid)
        self.pages["tape"] = self._page_tape(mid)
        self.pages["settings"] = self._page_settings(mid)
        # Footer before first page show — refresh() needs foot_vars.
        self._build_footer(shell)
        self._show_page("floor")

    def _btn(self, parent: tk.Misc, text: str, color: str, command, *, padx: int = 14) -> tk.Button:
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
            pady=8,
            cursor="hand2",
        )

    def _build_controls(self, parent: tk.Misc) -> None:
        bar = tk.Frame(parent, bg=C["panel"], height=56)
        bar.pack(fill=tk.X)
        bar.pack_propagate(False)
        left = tk.Frame(bar, bg=C["panel"])
        left.pack(side=tk.LEFT, padx=14, pady=8)
        for key, label, accent in (
            ("floor", "FLOOR", C["brass"]),
            ("accounts", "ACCOUNTS", C["sky"]),
            ("positions", "POSITIONS", C["signal"]),
            ("tape", "TAPE", C["warn"]),
            ("settings", "SETTINGS", C["mute"]),
        ):
            btn = self._btn(left, label, accent, lambda k=key: self._show_page(k))
            btn.pack(side=tk.LEFT, padx=3)
            self._nav_btns[key] = btn
        right = tk.Frame(bar, bg=C["panel"])
        right.pack(side=tk.RIGHT, padx=14, pady=8)
        self._btn(right, "START LIVE", C["signal"], self._start_live).pack(side=tk.LEFT, padx=3)
        self._btn(right, "PAPER", C["sky"], self._start_paper).pack(side=tk.LEFT, padx=3)
        self._btn(right, "STOP", C["stop"], self._confirm_stop).pack(side=tk.LEFT, padx=3)

    def _show_page(self, key: str) -> None:
        self._page = key
        for name, frame in self.pages.items():
            if name == key:
                frame.pack(fill=tk.BOTH, expand=True)
            else:
                frame.pack_forget()
        for name, btn in self._nav_btns.items():
            accent = {
                "floor": C["brass"],
                "accounts": C["sky"],
                "positions": C["signal"],
                "tape": C["warn"],
                "settings": C["mute"],
            }.get(name, C["mute"])
            if name == key:
                btn.configure(bg=C["line"], fg=C["ink"], highlightbackground=C["ink"])
            else:
                btn.configure(bg=C["panel2"], fg=accent, highlightbackground=accent)
        if key in {"accounts", "floor", "positions"}:
            self.refresh()

    def _tree(self, parent: tk.Misc, columns: tuple[str, ...], headings: dict[str, str], widths: dict[str, int]) -> ttk.Treeview:
        wrap = tk.Frame(parent, bg=C["line"])
        wrap.pack(fill=tk.BOTH, expand=True)
        tree = ttk.Treeview(wrap, columns=columns, show="headings", style="Ledger.Treeview", selectmode="browse")
        vsb = ttk.Scrollbar(wrap, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        for col in columns:
            tree.heading(col, text=headings[col], anchor="w")
            tree.column(col, width=widths.get(col, 100), anchor="w", stretch=True)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=1, pady=1)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        tree.tag_configure("ok", foreground=C["ok"])
        tree.tag_configure("warn", foreground=C["warn"])
        tree.tag_configure("err", foreground=C["stop"])
        tree.tag_configure("mute", foreground=C["mute"])
        return tree

    def _page_floor(self, parent: tk.Misc) -> tk.Frame:
        frame = tk.Frame(parent, bg=C["void"])
        tk.Label(frame, text="ACCOUNTS / BRIDGES", bg=C["void"], fg=C["brass"], font=self.f_h1).pack(anchor="w", pady=(0, 6))
        self.floor_tree = self._tree(
            frame,
            ("account", "equity", "balance", "symbol", "market", "status", "conn", "trade", "pos", "lot"),
            {
                "account": "ACCOUNT",
                "equity": "EQUITY",
                "balance": "BALANCE",
                "symbol": "SYMBOL",
                "market": "MARKET",
                "status": "STATUS",
                "conn": "CONN",
                "trade": "TRADE",
                "pos": "POS",
                "lot": "LOT",
            },
            {
                "account": 90,
                "equity": 90,
                "balance": 90,
                "symbol": 110,
                "market": 80,
                "status": 80,
                "conn": 70,
                "trade": 70,
                "pos": 50,
                "lot": 70,
            },
        )
        self.floor_tree.bind("<<TreeviewSelect>>", self._on_floor_select)

        tk.Label(frame, text="OPEN POSITIONS", bg=C["void"], fg=C["signal"], font=self.f_h1).pack(anchor="w", pady=(14, 6))
        self.floor_pos_tree = self._tree(
            frame,
            ("account", "ticket", "symbol", "side", "lot", "entry", "sl", "tp", "pl"),
            {
                "account": "ACCOUNT",
                "ticket": "TICKET",
                "symbol": "SYMBOL",
                "side": "SIDE",
                "lot": "LOT",
                "entry": "ENTRY",
                "sl": "SL",
                "tp": "TP",
                "pl": "P/L",
            },
            {
                "account": 80,
                "ticket": 90,
                "symbol": 100,
                "side": 60,
                "lot": 60,
                "entry": 100,
                "sl": 100,
                "tp": 90,
                "pl": 90,
            },
        )
        return frame

    def _page_accounts(self, parent: tk.Misc) -> tk.Frame:
        frame = tk.Frame(parent, bg=C["void"])
        head = tk.Frame(frame, bg=C["void"])
        head.pack(fill=tk.X, pady=(0, 8))
        tk.Label(head, text="PER-ACCOUNT LOT", bg=C["void"], fg=C["sky"], font=self.f_h1).pack(side=tk.LEFT)
        tk.Label(
            head,
            text="Edit lot → SAVE. Override writes runtime/accounts/<id>/lot.json",
            bg=C["void"],
            fg=C["mute"],
            font=self.f_ui,
        ).pack(side=tk.LEFT, padx=12)
        self.accounts_host = tk.Frame(frame, bg=C["void"])
        self.accounts_host.pack(fill=tk.BOTH, expand=True)
        self.accounts_empty = tk.Label(
            self.accounts_host,
            text="No accounts yet — start LIVE with MT4 bridges connected.",
            bg=C["void"],
            fg=C["mute"],
            font=self.f_ui,
        )
        self.accounts_empty.pack(pady=40)
        return frame

    def _page_positions(self, parent: tk.Misc) -> tk.Frame:
        frame = tk.Frame(parent, bg=C["void"])
        tk.Label(frame, text="POSITION BOOK", bg=C["void"], fg=C["signal"], font=self.f_h1).pack(anchor="w", pady=(0, 6))
        self.pos_tree = self._tree(
            frame,
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
                "side": 60,
                "lot": 60,
                "entry": 100,
                "price": 100,
                "sl": 100,
                "tp": 90,
                "pl": 90,
            },
        )
        return frame

    def _page_tape(self, parent: tk.Misc) -> tk.Frame:
        frame = tk.Frame(parent, bg=C["void"])
        split = tk.Frame(frame, bg=C["void"])
        split.pack(fill=tk.BOTH, expand=True)
        left = tk.Frame(split, bg=C["void"])
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))
        right = tk.Frame(split, bg=C["void"])
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(6, 0))
        tk.Label(left, text="AUDIT TAPE", bg=C["void"], fg=C["warn"], font=self.f_h1).pack(anchor="w", pady=(0, 6))
        self.tape = tk.Text(left, bg=C["panel2"], fg=C["ink"], relief=tk.FLAT, font=self.f_mono, wrap=tk.NONE)
        self.tape.pack(fill=tk.BOTH, expand=True)
        self.tape.configure(state=tk.DISABLED)
        tk.Label(right, text="ENGINE LOG", bg=C["void"], fg=C["sky"], font=self.f_h1).pack(anchor="w", pady=(0, 6))
        self.engine_log = tk.Text(right, bg=C["panel2"], fg=C["mute"], relief=tk.FLAT, font=self.f_mono, wrap=tk.NONE)
        self.engine_log.pack(fill=tk.BOTH, expand=True)
        self.engine_log.configure(state=tk.DISABLED)
        return frame

    def _page_settings(self, parent: tk.Misc) -> tk.Frame:
        frame = tk.Frame(parent, bg=C["void"])
        tk.Label(frame, text="SETTINGS", bg=C["void"], fg=C["brass"], font=self.f_h1).pack(anchor="w", pady=(0, 10))
        self.settings_info = tk.Label(frame, text="", bg=C["void"], fg=C["ink"], font=self.f_mono, justify=tk.LEFT)
        self.settings_info.pack(anchor="w")
        row = tk.Frame(frame, bg=C["void"])
        row.pack(anchor="w", pady=16)
        for text, color, cmd in (
            ("ENABLE TRADING", C["signal"], lambda: self._set_trading(True)),
            ("DISABLE TRADING", C["warn"], lambda: self._set_trading(False)),
            ("CLEAR STOP", C["sky"], self._clear_stop),
            ("DEPLOY MT4", C["brass"], self._deploy),
        ):
            self._btn(row, text, color, cmd).pack(side=tk.LEFT, padx=4)
        return frame

    def _build_footer(self, parent: tk.Misc) -> None:
        foot = tk.Frame(parent, bg=C["panel"], height=44)
        foot.pack(fill=tk.X, side=tk.BOTTOM)
        foot.pack_propagate(False)
        inner = tk.Frame(foot, bg=C["panel"])
        inner.pack(fill=tk.BOTH, expand=True, padx=16)
        self.foot_vars = {
            "uptime": tk.StringVar(value="—"),
            "engine": tk.StringVar(value="—"),
            "conn": tk.StringVar(value="—"),
            "time": tk.StringVar(value="—"),
            "system": tk.StringVar(value="OFFLINE"),
        }
        for label, key, color in (
            ("UPTIME", "uptime", C["ok"]),
            ("ENGINE", "engine", C["sky"]),
            ("CONNECTIONS", "conn", C["signal"]),
            ("LOCAL", "time", C["mute"]),
            ("SYSTEM", "system", C["brass"]),
        ):
            cell = tk.Frame(inner, bg=C["panel"])
            cell.pack(side=tk.LEFT, expand=True, fill=tk.X)
            tk.Label(cell, text=label, bg=C["panel"], fg=C["mute"], font=self.f_ui).pack(anchor="w", pady=(6, 0))
            tk.Label(cell, textvariable=self.foot_vars[key], bg=C["panel"], fg=color, font=self.f_ui_b).pack(anchor="w")

    def _on_floor_select(self, _event=None) -> None:
        sel = self.floor_tree.selection()
        if not sel:
            return
        acct = self.floor_tree.item(sel[0], "values")[0]
        if acct and acct != "—":
            self._focus_account = str(acct)
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
            meta["account"].configure(text=acct)
            meta["balance"].configure(text=eq)
            meta["symbol"].configure(text=str(sym))
            meta["source"].configure(text=src, fg=src_c)
            if self._lot_dirty.get(acct) or self._entry_focused(acct):
                continue
            effective = override if override is not None else default_lot
            current = self._lot_vars[acct].get().strip()
            target = f"{effective:.2f}"
            if current != target:
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
        for text, w in (("ACCOUNT", 120), ("EQUITY", 100), ("SYMBOL", 110), ("LOT", 90), ("SOURCE", 90), ("", 200)):
            tk.Label(header, text=text, bg=C["panel"], fg=C["brass"], font=self.f_ui_b, width=max(w // 8, 8), anchor="w").pack(
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
            lbl_acct = tk.Label(row, text=acct, bg=row["bg"], fg=C["ink"], font=self.f_mono_b, width=14, anchor="w")
            lbl_acct.pack(side=tk.LEFT, padx=6, pady=8)
            lbl_bal = tk.Label(row, text=eq, bg=row["bg"], fg=C["signal"], font=self.f_mono, width=12, anchor="w")
            lbl_bal.pack(side=tk.LEFT, padx=6)
            lbl_sym = tk.Label(row, text=str(sym), bg=row["bg"], fg=C["mute"], font=self.f_mono, width=12, anchor="w")
            lbl_sym.pack(side=tk.LEFT, padx=6)
            entry = tk.Entry(
                row,
                textvariable=var,
                bg=C["void"],
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
        for row in rows:
            values, tag = row[0], row[1]
            tree.insert("", tk.END, values=values, tags=(tag,))

    def refresh(self) -> None:
        health = collect_health(self.config_path)
        self._health = health
        cfg = self._cfg_data()
        online = self.engine.running or any(b.connected for b in health.bridges)
        mode = self.engine.mode or health.mode or "—"
        self.brand.set_status(online=online, mode=str(mode))

        equity = sum(b.equity for b in health.bridges) if health.bridges else 0.0
        n_pos = sum(len(b.positions) for b in health.bridges)
        self.metric_vars["equity"].set(f"{equity:.2f}" if health.bridges else "—")
        self.metric_vars["bridges"].set(str(len(health.bridges)))
        self.metric_vars["positions"].set(str(n_pos))
        self.metric_vars["stop"].set("ARMED" if health.stop_present else "clear")
        self.metric_vars["lot"].set(f"{default_fixed_lot(cfg):.2f}")

        # Floor tables
        default_lot = default_fixed_lot(cfg)
        rt = self._rt()
        floor_rows: list[tuple] = []
        for b in health.bridges:
            override = read_account_lot_override(rt, b.account_id)
            lot = override if override is not None else default_lot
            tag = "ok" if b.connected and (b.market_age_s is not None and b.market_age_s <= 30) else (
                "warn" if b.connected else "err"
            )
            floor_rows.append(
                (
                    (
                        b.account_id,
                        f"{b.equity:.2f}",
                        f"{b.balance:.2f}",
                        b.symbol or health.symbol or "—",
                        format_age(b.market_age_s),
                        format_age(b.status_age_s),
                        "YES" if b.connected else "NO",
                        "YES" if b.trading_allowed else "NO",
                        str(len(b.positions)),
                        f"{lot:.2f}",
                    ),
                    tag,
                )
            )
        # Also show accounts that only have lot overrides / folders
        known = set(list_known_accounts(health, rt))
        seen = {b.account_id for b in health.bridges}
        for acct in sorted(known - seen):
            override = read_account_lot_override(rt, acct)
            lot = override if override is not None else default_lot
            floor_rows.append(
                ((acct, "—", "—", health.symbol or "—", "—", "—", "—", "—", "0", f"{lot:.2f}"), "mute")
            )
        self._fill_tree(self.floor_tree, floor_rows)

        pos_rows: list[tuple] = []
        for b in health.bridges:
            for p in b.positions:
                tag = "ok" if p.profit >= 0 else "err"
                pos_rows.append(
                    (
                        (
                            b.account_id,
                            str(p.ticket),
                            p.symbol,
                            p.side,
                            f"{p.lot:.2f}",
                            f"{p.open_price:.5f}" if p.open_price else "—",
                            f"{p.stop_loss:.5f}" if p.stop_loss else "—",
                            f"{p.take_profit:.5f}" if p.take_profit else "—",
                            f"{p.profit:.2f}",
                        ),
                        tag,
                    )
                )
        self._fill_tree(self.floor_pos_tree, pos_rows)

        book_rows: list[tuple] = []
        for b in health.bridges:
            for p in b.positions:
                tag = "ok" if p.profit >= 0 else "err"
                cur = p.current_price
                book_rows.append(
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
                            f"{p.profit:.2f}",
                        ),
                        tag,
                    )
                )
        self._fill_tree(self.pos_tree, book_rows)

        # Tape
        lines = [format_audit_line(e) for e in audit_activity(audit_file(cfg), limit=60)]
        self._set_text(self.tape, "\n".join(lines) if lines else "(no audit yet)")

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
                f"mode: {health.mode}   trading_enabled: {health.trading_enabled}   stop: {health.stop_present}\n"
                f"symbol: {health.symbol}\n"
                f"default lot: {pos_cfg.get('fixed_lot') or pos_cfg.get('default_lot')}   "
                f"min/max: {pos_cfg.get('min_lot')}/{pos_cfg.get('max_lot')}\n"
                f"engine: {'UP' if self.engine.running else 'DOWN'}  pid={self.engine.pid}  mode={self.engine.mode}"
            )
        )

        if self._page == "accounts":
            self._sync_account_rows(health)

        if getattr(self, "foot_vars", None):
            uptime = int(time.time() - self._started_wall)
            self.foot_vars["uptime"].set(f"{uptime // 60}m {uptime % 60}s")
            self.foot_vars["engine"].set(
                f"{'LIVE' if self.engine.mode == 'live' else (self.engine.mode or 'off').upper()} · "
                f"{'UP' if self.engine.running else 'DOWN'}"
            )
            self.foot_vars["conn"].set(
                "STABLE" if any(b.connected for b in health.bridges) else ("DEGRADED" if health.bridges else "NONE")
            )
            self.foot_vars["time"].set(time.strftime("%H:%M:%S"))
            self.foot_vars["system"].set("ONLINE" if online else "OFFLINE")

    def _set_text(self, widget: tk.Text, text: str) -> None:
        widget.configure(state=tk.NORMAL)
        widget.delete("1.0", tk.END)
        widget.insert("1.0", text)
        widget.configure(state=tk.DISABLED)

    def _motion_tick(self) -> None:
        self._pulse = (self._pulse + 0.08) % math.tau
        self.brand.tick()
        # Soft pulse on ONLINE metric via brand already; nudge stop color when armed
        if self._health and self._health.stop_present:
            t = 0.5 + 0.5 * math.sin(self._pulse * 2)
            # mild brightness pulse on stop label via text swap
            self.metric_vars["stop"].set("ARMED" if t > 0.2 else "ARMED ·")
        self.root.after(80, self._motion_tick)

    def _tick(self) -> None:
        with contextlib.suppress(Exception):
            self.refresh()
        self.root.after(800, self._tick)

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
    DashboardApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
