"""CHECK SYSTEM ops floor — high-energy desktop console (Tkinter).

Visual language is intentionally unlike the previous navy sidebar deck:
full-bleed brand rail, color slabs, lime/coral/cyan signal accents.
"""

from __future__ import annotations

import contextlib
import json
import math
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
    arm_live_runtime,
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

# Ops-floor palette — loud on purpose, not navy-card console.
C = {
    "void": "#07070A",
    "ink": "#F4F7FA",
    "mute": "#8A93A3",
    "rail": "#101018",
    "slab": "#14141F",
    "slab2": "#1B1B2A",
    "lime": "#C8F542",
    "lime_dim": "#7FA81A",
    "coral": "#FF4D6D",
    "coral_dim": "#B01236",
    "cyan": "#2DE2E6",
    "cyan_dim": "#0E8A8E",
    "violet": "#9B5CFF",
    "amber": "#FFB020",
    "mint": "#3DFFB5",
    "grid": "#24243A",
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
        self.root.title("CHECK · OPS FLOOR")
        self.root.geometry("1500x920")
        self.root.minsize(1280, 800)
        self.root.configure(bg=C["void"])

        self.f_mega = _font(["Bahnschrift", "Segoe UI Variable Display", "Arial Black", "Impact"], 42, "bold")
        self.f_brand = _font(["Bahnschrift", "Segoe UI Variable Display", "Calibri"], 18, "bold")
        self.f_h1 = _font(["Bahnschrift", "Segoe UI"], 16, "bold")
        self.f_h2 = _font(["Bahnschrift SemiBold", "Segoe UI"], 11, "bold")
        self.f_ui = _font(["Bahnschrift", "Segoe UI"], 10)
        self.f_ui_b = _font(["Bahnschrift SemiBold", "Segoe UI"], 10, "bold")
        self.f_metric = _font(["Bahnschrift", "Segoe UI"], 26, "bold")
        self.f_mono = _font(["Cascadia Mono", "Consolas", "Courier New"], 9)
        self.f_mono_b = _font(["Cascadia Mono", "Consolas"], 10, "bold")

        self.config_path = resolve_config()
        self.engine = EngineProcess()
        self.log_queue: queue.Queue[str] = queue.Queue()
        self._audit_offset = 0
        self._stopping = False
        self._selected_account: str | None = None
        self._page = "floor"
        self._pulse = False
        self._health = None
        self._nav_btns: dict[str, tk.Button] = {}
        self._brand_phase = 0.0
        self._flash_until = 0.0

        self._build()
        self._tail_audit_init()
        self.refresh()
        self.root.after(450, self._tick)
        self.root.after(80, self._motion_tick)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── chrome ──────────────────────────────────────────────────────────────
    def _build(self) -> None:
        shell = tk.Frame(self.root, bg=C["void"])
        shell.pack(fill=tk.BOTH, expand=True)

        # Atmosphere canvas (diagonal hash) behind everything
        self.atmosphere = tk.Canvas(shell, bg=C["void"], highlightthickness=0, height=1)
        self.atmosphere.place(x=0, y=0, relwidth=1, relheight=1)
        self.atmosphere.bind("<Configure>", self._paint_atmosphere)

        body = tk.Frame(shell, bg=C["void"])
        body.place(x=0, y=0, relwidth=1, relheight=1)

        self._build_brand_rail(body)
        self._build_account_runway(body)

        mid = tk.Frame(body, bg=C["void"])
        mid.pack(fill=tk.BOTH, expand=True, padx=18, pady=(0, 10))

        self.pages: dict[str, tk.Frame] = {}
        self.pages["floor"] = self._page_floor(mid)
        self.pages["book"] = self._page_book(mid)
        self.pages["tape"] = self._page_tape(mid)
        self._show_page("floor")

        self._build_status_strip(body)

    def _paint_atmosphere(self, _event=None) -> None:
        c = self.atmosphere
        c.delete("all")
        w, h = max(c.winfo_width(), 2), max(c.winfo_height(), 2)
        c.create_rectangle(0, 0, w, h, fill=C["void"], outline="")
        # Soft color washes
        c.create_oval(-120, -80, 420, 280, fill="#12181A", outline="")
        c.create_oval(w - 480, h - 360, w + 80, h + 80, fill="#1A1020", outline="")
        c.create_oval(w // 2 - 200, h // 2 - 40, w // 2 + 420, h // 2 + 320, fill="#0E1520", outline="")
        step = 28
        for i in range(-h, w + h, step):
            c.create_line(i, 0, i + h, h, fill="#12121C", width=1)

    def _build_brand_rail(self, parent: tk.Misc) -> None:
        rail = tk.Frame(parent, bg=C["rail"], height=92)
        rail.pack(fill=tk.X)
        rail.pack_propagate(False)

        # Lime signal bar on top edge
        self.brand_bar = tk.Canvas(rail, height=6, bg=C["rail"], highlightthickness=0)
        self.brand_bar.pack(fill=tk.X)
        self.brand_bar.bind("<Configure>", lambda _e: self._draw_brand_bar())

        row = tk.Frame(rail, bg=C["rail"])
        row.pack(fill=tk.BOTH, expand=True, padx=20, pady=(4, 10))

        left = tk.Frame(row, bg=C["rail"])
        left.pack(side=tk.LEFT, fill=tk.Y)
        tk.Label(left, text="CHECK", bg=C["rail"], fg=C["lime"], font=self.f_mega).pack(side=tk.LEFT, anchor="s")
        sub = tk.Frame(left, bg=C["rail"])
        sub.pack(side=tk.LEFT, padx=(14, 0), anchor="s", pady=(0, 8))
        tk.Label(sub, text="OPS FLOOR", bg=C["rail"], fg=C["ink"], font=self.f_brand, anchor="w").pack(anchor="w")
        tk.Label(sub, text="v3 · live bridge command", bg=C["rail"], fg=C["mute"], font=self.f_ui, anchor="w").pack(
            anchor="w"
        )

        nav = tk.Frame(row, bg=C["rail"])
        nav.pack(side=tk.LEFT, padx=(40, 0), fill=tk.Y)
        for key, label, accent in (
            ("floor", "FLOOR", C["lime"]),
            ("book", "BOOK", C["cyan"]),
            ("tape", "TAPE", C["violet"]),
        ):
            btn = tk.Button(
                nav,
                text=label,
                command=lambda k=key: self._show_page(k),
                bg=C["slab"],
                fg=accent,
                activebackground=C["slab2"],
                activeforeground=accent,
                relief=tk.FLAT,
                bd=0,
                font=self.f_ui_b,
                padx=16,
                pady=12,
                cursor="hand2",
            )
            btn.pack(side=tk.LEFT, padx=4, pady=10)
            self._nav_btns[key] = btn

        right = tk.Frame(row, bg=C["rail"])
        right.pack(side=tk.RIGHT, fill=tk.Y)
        self.pill_sys = self._status_pill(right, "SYSTEM", "OFF", C["coral"])
        self.pill_sys.pack(side=tk.LEFT, padx=5, pady=14)
        self.pill_eng = self._status_pill(right, "ENGINE", "IDLE", C["amber"])
        self.pill_eng.pack(side=tk.LEFT, padx=5, pady=14)
        self.pill_brg = self._status_pill(right, "BRIDGE", "—", C["mute"])
        self.pill_brg.pack(side=tk.LEFT, padx=5, pady=14)

    def _draw_brand_bar(self) -> None:
        c = self.brand_bar
        c.delete("all")
        w = max(c.winfo_width(), 2)
        c.create_rectangle(0, 0, w, 6, fill=C["grid"], outline="")
        # Sweeping lime segment
        seg = 180
        x = int((math.sin(self._brand_phase) * 0.5 + 0.5) * max(w - seg, 1))
        c.create_rectangle(x, 0, x + seg, 6, fill=C["lime"], outline="")
        c.create_rectangle(x + seg - 40, 0, x + seg, 6, fill=C["cyan"], outline="")

    def _status_pill(self, parent: tk.Misc, title: str, value: str, color: str) -> tk.Frame:
        box = tk.Frame(parent, bg=C["slab2"], padx=12, pady=6)
        tk.Label(box, text=title, bg=C["slab2"], fg=C["mute"], font=self.f_ui).pack(anchor="w")
        row = tk.Frame(box, bg=C["slab2"])
        row.pack(anchor="w")
        stripe = tk.Frame(row, bg=color, width=4, height=16)
        stripe.pack(side=tk.LEFT, padx=(0, 8))
        lab = tk.Label(row, text=value, bg=C["slab2"], fg=C["ink"], font=self.f_ui_b)
        lab.pack(side=tk.LEFT)
        box._stripe = stripe  # type: ignore[attr-defined]
        box._lab = lab  # type: ignore[attr-defined]
        return box

    def _set_pill(self, pill: tk.Frame, value: str, color: str) -> None:
        pill._lab.configure(text=value)  # type: ignore[attr-defined]
        pill._stripe.configure(bg=color)  # type: ignore[attr-defined]

    def _build_account_runway(self, parent: tk.Misc) -> None:
        runway = tk.Frame(parent, bg=C["void"], height=64)
        runway.pack(fill=tk.X, padx=18, pady=(12, 8))
        runway.pack_propagate(False)
        left = tk.Frame(runway, bg=C["void"])
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tk.Label(left, text="ACCOUNTS", bg=C["void"], fg=C["mute"], font=self.f_h2, anchor="w").pack(anchor="w")
        self.account_list = tk.Frame(left, bg=C["void"])
        self.account_list.pack(fill=tk.X, pady=(4, 0))

        right = tk.Frame(runway, bg=C["void"])
        right.pack(side=tk.RIGHT, fill=tk.Y)
        self.headline_symbol = tk.StringVar(value="—")
        self.headline_regime = tk.StringVar(value="—")
        tk.Label(right, textvariable=self.headline_symbol, bg=C["void"], fg=C["cyan"], font=self.f_h1, anchor="e").pack(
            anchor="e"
        )
        tk.Label(
            right, textvariable=self.headline_regime, bg=C["void"], fg=C["violet"], font=self.f_ui_b, anchor="e"
        ).pack(anchor="e")

    def _build_status_strip(self, parent: tk.Misc) -> None:
        strip = tk.Frame(parent, bg=C["lime"], height=34)
        strip.pack(fill=tk.X, side=tk.BOTTOM)
        strip.pack_propagate(False)
        self.footer_var = tk.StringVar(value="Waiting for bridge…")
        tk.Label(
            strip,
            textvariable=self.footer_var,
            bg=C["lime"],
            fg="#101010",
            font=self.f_mono_b,
            anchor="w",
            padx=16,
        ).pack(fill=tk.BOTH, expand=True)

    def _slab(self, parent: tk.Misc, bg: str = "") -> tk.Frame:
        return tk.Frame(parent, bg=bg or C["slab"])

    def _color_metric(self, parent: tk.Misc, title: str, accent: str) -> tuple[tk.Frame, tk.StringVar, tk.StringVar]:
        card = tk.Frame(parent, bg=accent)
        tk.Label(card, text=title, bg=accent, fg="#101010", font=self.f_ui_b, anchor="w").pack(
            fill=tk.X, padx=14, pady=(12, 0)
        )
        val = tk.StringVar(value="—")
        sub = tk.StringVar(value="")
        tk.Label(card, textvariable=val, bg=accent, fg="#101010", font=self.f_metric, anchor="w").pack(
            fill=tk.X, padx=14, pady=(2, 0)
        )
        tk.Label(card, textvariable=sub, bg=accent, fg="#203010", font=self.f_ui, anchor="w").pack(
            fill=tk.X, padx=14, pady=(0, 12)
        )
        return card, val, sub

    # ── pages ───────────────────────────────────────────────────────────────
    def _page_floor(self, parent: tk.Misc) -> tk.Frame:
        page = tk.Frame(parent, bg=C["void"])

        grid = tk.Frame(page, bg=C["void"])
        grid.pack(fill=tk.BOTH, expand=True)

        # Left: stacked color metrics
        left = tk.Frame(grid, bg=C["void"], width=280)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        left.pack_propagate(False)
        self.m_balance = self._color_metric(left, "BALANCE", C["lime"])
        self.m_equity = self._color_metric(left, "EQUITY", C["cyan"])
        self.m_float = self._color_metric(left, "FLOATING P/L", C["coral"])
        self.m_trades = self._color_metric(left, "TODAY ACTIONS", C["violet"])
        for card in (self.m_balance, self.m_equity, self.m_float, self.m_trades):
            card[0].pack(fill=tk.X, pady=(0, 8))

        # Center: equity wave + signal board
        center = tk.Frame(grid, bg=C["void"])
        center.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4)

        wave = self._slab(center)
        wave.pack(fill=tk.BOTH, expand=True, pady=(0, 8))
        head = tk.Frame(wave, bg=C["slab"])
        head.pack(fill=tk.X, padx=14, pady=(12, 0))
        tk.Label(head, text="EQUITY WAVE", bg=C["slab"], fg=C["mute"], font=self.f_h2, anchor="w").pack(side=tk.LEFT)
        self.wave_now = tk.StringVar(value="—")
        tk.Label(head, textvariable=self.wave_now, bg=C["slab"], fg=C["lime"], font=self.f_mono_b, anchor="e").pack(
            side=tk.RIGHT
        )
        self.equity_canvas = tk.Canvas(wave, bg=C["slab"], highlightthickness=0, height=240)
        self.equity_canvas.pack(fill=tk.BOTH, expand=True, padx=8, pady=(4, 10))
        self.equity_canvas.bind("<Configure>", lambda _e: self._draw_equity())

        board = self._slab(center)
        board.pack(fill=tk.X)
        tk.Label(board, text="SIGNAL BOARD", bg=C["slab"], fg=C["mute"], font=self.f_h2, anchor="w").pack(
            fill=tk.X, padx=14, pady=(10, 4)
        )
        self.state_vars = {
            "accounts": tk.StringVar(value="—"),
            "symbol": tk.StringVar(value="—"),
            "regime": tk.StringVar(value="—"),
            "strategy": tk.StringVar(value="—"),
            "decision": tk.StringVar(value="—"),
            "reason": tk.StringVar(value="—"),
            "spread": tk.StringVar(value="—"),
        }
        body = tk.Frame(board, bg=C["slab"])
        body.pack(fill=tk.X, padx=14, pady=(0, 12))
        cols = tk.Frame(body, bg=C["slab"])
        cols.pack(fill=tk.X)
        left_col = tk.Frame(cols, bg=C["slab"])
        left_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        right_col = tk.Frame(cols, bg=C["slab"])
        right_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(12, 0))
        for key, label, target in (
            ("accounts", "Accounts", left_col),
            ("symbol", "Symbol", left_col),
            ("regime", "Regime", left_col),
            ("strategy", "Strategy", right_col),
            ("decision", "Decision", right_col),
            ("reason", "Reason", right_col),
            ("spread", "Spread", right_col),
        ):
            row = tk.Frame(target, bg=C["slab2"], padx=8, pady=5)
            row.pack(fill=tk.X, pady=2)
            tk.Label(row, text=label.upper(), width=10, anchor="w", bg=C["slab2"], fg=C["mute"], font=self.f_ui).pack(
                side=tk.LEFT
            )
            tk.Label(
                row,
                textvariable=self.state_vars[key],
                anchor="w",
                bg=C["slab2"],
                fg=C["ink"],
                font=self.f_mono_b,
                wraplength=260,
                justify=tk.LEFT,
            ).pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Right: arm panel + health
        right = tk.Frame(grid, bg=C["void"], width=260)
        right.pack(side=tk.LEFT, fill=tk.Y, padx=(10, 0))
        right.pack_propagate(False)

        arm = tk.Frame(right, bg=C["coral"])
        arm.pack(fill=tk.X, pady=(0, 8))
        tk.Label(arm, text="ARM", bg=C["coral"], fg="#101010", font=self.f_h2, anchor="w").pack(
            fill=tk.X, padx=14, pady=(12, 0)
        )
        tk.Label(arm, text="Fire the engine", bg=C["coral"], fg="#401018", font=self.f_ui, anchor="w").pack(
            fill=tk.X, padx=14, pady=(0, 8)
        )
        actions = tk.Frame(arm, bg=C["coral"])
        actions.pack(fill=tk.X, padx=10, pady=(0, 12))
        self.btn_live = self._big_btn(actions, "START LIVE", "#101010", C["lime"], self.start_live)
        self.btn_live.pack(fill=tk.X, pady=3)
        self.btn_paper = self._big_btn(actions, "START PAPER", "#101010", C["cyan"], self.start_paper)
        self.btn_paper.pack(fill=tk.X, pady=3)
        self.btn_stop = self._big_btn(actions, "STOP", C["ink"], "#5A1020", self.stop_engine)
        self.btn_stop.pack(fill=tk.X, pady=3)

        tools = self._slab(right)
        tools.pack(fill=tk.X, pady=(0, 8))
        tk.Label(tools, text="TOOLS", bg=C["slab"], fg=C["mute"], font=self.f_h2, anchor="w").pack(
            fill=tk.X, padx=12, pady=(10, 4)
        )
        self.btn_deploy = self._ghost(tools, "Deploy MT4", self.deploy_mt4)
        self.btn_deploy.pack(fill=tk.X, padx=10, pady=3)
        self.btn_refresh = self._ghost(tools, "Refresh", self.refresh)
        self.btn_refresh.pack(fill=tk.X, padx=10, pady=(3, 10))

        health = self._slab(right)
        health.pack(fill=tk.BOTH, expand=True)
        tk.Label(health, text="BRIDGE PULSE", bg=C["slab"], fg=C["mute"], font=self.f_h2, anchor="w").pack(
            fill=tk.X, padx=12, pady=(10, 0)
        )
        self.health_canvas = tk.Canvas(health, width=140, height=140, bg=C["slab"], highlightthickness=0)
        self.health_canvas.pack(pady=8)
        self.health_label = tk.StringVar(value="—")
        self.health_detail = tk.StringVar(value="Freshness")
        tk.Label(health, textvariable=self.health_label, bg=C["slab"], fg=C["mint"], font=self.f_metric).pack()
        tk.Label(health, textvariable=self.health_detail, bg=C["slab"], fg=C["mute"], font=self.f_ui).pack(
            pady=(0, 12)
        )

        # Bottom dual tape/book preview
        bottom = tk.Frame(page, bg=C["void"])
        bottom.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        recent = self._slab(bottom)
        recent.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))
        tk.Label(recent, text="RECENT CYCLES", bg=C["slab"], fg=C["mute"], font=self.f_h2, anchor="w").pack(
            fill=tk.X, padx=12, pady=(10, 4)
        )
        self.recent_box = self._mono_box(recent)
        self.recent_box.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        positions = self._slab(bottom)
        positions.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6, 0))
        tk.Label(positions, text="OPEN BOOK", bg=C["slab"], fg=C["mute"], font=self.f_h2, anchor="w").pack(
            fill=tk.X, padx=12, pady=(10, 4)
        )
        self.pos_box = self._mono_box(positions)
        self.pos_box.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        return page

    def _page_book(self, parent: tk.Misc) -> tk.Frame:
        page = tk.Frame(parent, bg=C["void"])
        panel = self._slab(page)
        panel.pack(fill=tk.BOTH, expand=True)
        banner = tk.Frame(panel, bg=C["cyan"], height=48)
        banner.pack(fill=tk.X)
        banner.pack_propagate(False)
        tk.Label(banner, text="LIVE BOOK · EVERY ACCOUNT", bg=C["cyan"], fg="#101010", font=self.f_h1).pack(
            side=tk.LEFT, padx=16, pady=10
        )
        self.trades_box = self._mono_box(panel, height=28)
        self.trades_box.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        return page

    def _page_tape(self, parent: tk.Misc) -> tk.Frame:
        page = tk.Frame(parent, bg=C["void"])
        panel = self._slab(page)
        panel.pack(fill=tk.BOTH, expand=True)
        banner = tk.Frame(panel, bg=C["violet"], height=48)
        banner.pack(fill=tk.X)
        banner.pack_propagate(False)
        tk.Label(banner, text="ACTIVITY TAPE", bg=C["violet"], fg="#101010", font=self.f_h1).pack(
            side=tk.LEFT, padx=16, pady=10
        )
        wrap = tk.Frame(panel, bg=C["slab"])
        wrap.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        self.activity = tk.Text(
            wrap,
            bg="#0B0B12",
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
        self.activity.tag_configure("ok", foreground=C["mint"])
        self.activity.tag_configure("err", foreground=C["coral"])
        self.activity.tag_configure("dim", foreground=C["mute"])
        self.activity.tag_configure("flash", background="#2A1830", foreground=C["lime"])
        return page

    def _mono_box(self, parent: tk.Misc, height: int = 10) -> tk.Text:
        box = tk.Text(
            parent,
            height=height,
            bg="#0B0B12",
            fg=C["ink"],
            font=self.f_mono,
            relief=tk.FLAT,
            highlightthickness=0,
            padx=12,
            pady=8,
        )
        box.configure(state=tk.DISABLED)
        return box

    def _big_btn(self, parent: tk.Misc, text: str, fg: str, bg: str, cmd) -> tk.Button:
        return tk.Button(
            parent,
            text=text,
            command=cmd,
            bg=bg,
            fg=fg,
            activebackground=fg,
            activeforeground=bg,
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
            bg=C["slab2"],
            fg=C["ink"],
            activebackground=C["grid"],
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
        for _name, frame in self.pages.items():
            frame.pack_forget()
        self.pages[key].pack(fill=tk.BOTH, expand=True)
        accents = {"floor": C["lime"], "book": C["cyan"], "tape": C["violet"]}
        for name, btn in self._nav_btns.items():
            on = name == key
            btn.configure(
                bg=accents[name] if on else C["slab"],
                fg="#101010" if on else accents[name],
            )

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
            tk.Label(self.account_list, text="No MT4 bridge", bg=C["void"], fg=C["coral"], font=self.f_ui_b).pack(
                side=tk.LEFT
            )
            return
        if self._selected_account is None:
            self._selected_account = health.bridges[0].account_id
        for bridge in health.bridges:
            active = bridge.account_id == self._selected_account
            age = format_age(bridge.market_age_s)
            live = "LIVE" if "STALE" not in age and age != "missing" else "STALE"
            bg = C["lime"] if active else C["slab2"]
            fg = "#101010" if active else C["ink"]
            chip = tk.Frame(self.account_list, bg=bg, padx=12, pady=6)
            chip.pack(side=tk.LEFT, padx=(0, 8))
            tk.Label(chip, text=bridge.account_id, bg=bg, fg=fg, font=self.f_mono_b).pack(side=tk.LEFT)
            tk.Label(chip, text=f"  {live} · {bridge.symbol}", bg=bg, fg=fg, font=self.f_ui).pack(side=tk.LEFT)
            chip.bind("<Button-1>", lambda _e, a=bridge.account_id: self._select_account(a))
            for child in chip.winfo_children():
                child.bind("<Button-1>", lambda _e, a=bridge.account_id: self._select_account(a))

    def _select_account(self, account_id: str) -> None:
        self._selected_account = account_id
        self.refresh()

    def _draw_equity(self) -> None:
        canvas = self.equity_canvas
        canvas.delete("all")
        w = max(canvas.winfo_width(), 100)
        h = max(canvas.winfo_height(), 100)
        series = load_equity_series(self._selected_account, limit=120)
        pad = 18
        canvas.create_rectangle(0, 0, w, h, fill=C["slab"], outline="")
        # Grid
        for i in range(1, 5):
            y = pad + (h - 2 * pad) * i / 5
            canvas.create_line(pad, y, w - pad, y, fill=C["grid"])
        if len(series) < 2:
            canvas.create_text(
                w // 2,
                h // 2,
                text="Collecting equity samples…\nKeep the floor open while engine runs.",
                fill=C["mute"],
                font=self.f_ui,
                justify=tk.CENTER,
            )
            self.wave_now.set("—")
            return
        values = [v for _, v in series]
        lo, hi = min(values), max(values)
        span = max(hi - lo, 1e-6)
        pts: list[float] = []
        for i, (_, val) in enumerate(series):
            x = pad + (w - 2 * pad) * (i / (len(series) - 1))
            y = h - pad - (h - 2 * pad) * ((val - lo) / span)
            pts.extend([x, y])
        # Filled area under curve
        area = [pad, h - pad, *pts, w - pad, h - pad]
        canvas.create_polygon(*area, fill="#1E2A14", outline="")
        canvas.create_line(*pts, fill=C["lime"], width=3, smooth=True)
        canvas.create_oval(
            pts[-2] - 5,
            pts[-1] - 5,
            pts[-2] + 5,
            pts[-1] + 5,
            fill=C["cyan"],
            outline=C["ink"],
            width=1,
        )
        self.wave_now.set(_money(values[-1]))

    def _draw_health_ring(self, pct: float, color: str) -> None:
        canvas = self.health_canvas
        canvas.delete("all")
        x0, y0, x1, y1 = 12, 12, 128, 128
        canvas.create_oval(x0, y0, x1, y1, outline=C["grid"], width=12)
        extent = max(0.0, min(100.0, pct)) / 100.0 * 360.0
        if extent > 0:
            canvas.create_arc(x0, y0, x1, y1, start=90, extent=-extent, style=tk.ARC, outline=color, width=12)
        canvas.create_text(70, 70, text=f"{pct:.0f}%", fill=C["ink"], font=self.f_h1)

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
        elif "CTRL" in u or "OK" in u or "ARMED" in u:
            tag = "ok"
        self.activity.configure(state=tk.NORMAL)
        self.activity.insert(tk.END, line.rstrip() + "\n", ("flash", tag))
        self._flash_until = time.time() + 0.35
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

            self.m_equity[1].set(_money(bridge.equity, currency))
            delta = bridge.equity - bridge.balance
            self.m_equity[2].set(f"vs balance {delta:+.2f}")

            self.m_float[1].set(_money(bridge.floating_pl, currency))
            self.m_float[2].set(f"{len(bridge.positions)} open positions")
            # Recolor float slab by P/L
            float_bg = C["mint"] if bridge.floating_pl >= 0 else C["coral"]
            self.m_float[0].configure(bg=float_bg)
            for child in self.m_float[0].winfo_children():
                child.configure(bg=float_bg)

            self.state_vars["symbol"].set(f"{bridge.symbol}  bid={bridge.bid} ask={bridge.ask}")
            self.state_vars["spread"].set("—" if bridge.spread is None else str(bridge.spread))
            self.headline_symbol.set(f"{bridge.symbol}  M1")
            age = bridge.market_age_s
            if age is None:
                pct, color = 0.0, C["coral"]
                detail = "market export missing"
            elif age <= 5:
                pct, color = 100.0, C["mint"]
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
            self.state_vars["symbol"].set("—")
            self.state_vars["spread"].set("—")
            self.headline_symbol.set("NO SYMBOL")
            self._draw_health_ring(0, C["coral"])
            self.health_label.set("—")
            self.health_detail.set("No bridge")

        self.m_trades[1].set(str(stats["acted"]))
        self.m_trades[2].set(f"open {stats['opens']} · close {stats['closes']} · block {stats['blocks']}")

        audit = health.last_audit or {}
        if bridge and bridge.account_id:
            for row in recent:
                if str(row.get("account_number") or "") == bridge.account_id:
                    audit = row
                    break
        self.state_vars["accounts"].set(f"{len(health.bridges)} connected")
        self.state_vars["regime"].set(str(audit.get("market_regime") or "—"))
        self.state_vars["strategy"].set(str(audit.get("selected_strategy") or "—"))
        self.state_vars["decision"].set(str(audit.get("decision") or "—"))
        self.state_vars["reason"].set(str(audit.get("reason_code") or audit.get("human_readable_reason") or "—"))
        self.headline_regime.set(str(audit.get("market_regime") or "WAITING"))

        lines = [format_audit_line(row) for row in recent[:14]]
        self._set_text(self.recent_box, "\n".join(lines) if lines else "No audit cycles yet.")

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
        self._set_text(self.pos_box, "\n".join(pos_lines) if pos_lines else "Book flat — no open positions.")
        self._set_text(self.trades_box, "\n".join(trade_lines) if trade_lines else "Book flat — no open positions.")

        running = self.engine.running
        mode = self.engine.mode or health.mode
        ages = [b.market_age_s for b in health.bridges if b.market_age_s is not None]
        fresh_n = sum(1 for a in ages if a <= 30)
        if running:
            self._set_pill(self.pill_sys, "RUNNING", C["mint"] if self._pulse else C["lime"])
            self._set_pill(self.pill_eng, mode.upper(), C["cyan"] if mode == "live" else C["amber"])
        else:
            self._set_pill(self.pill_sys, "STOPPED", C["coral"])
            self._set_pill(self.pill_eng, "IDLE", C["amber"])
        self._set_pill(
            self.pill_brg,
            f"{fresh_n}/{len(health.bridges)} FRESH" if health.bridges else "NONE",
            C["mint"] if health.bridges and fresh_n == len(health.bridges) else C["amber"],
        )

        parts = [f"{b.account_id}:{format_age(b.market_age_s)}" for b in health.bridges]
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
        self._append_activity("WARN   PAPER fills locally — use START LIVE for MT4 orders")
        self._start_mode("paper")

    def start_live(self) -> None:
        try:
            armed = arm_live_runtime(self.config_path)
            if armed:
                self._append_activity("CTRL   armed system.json mode=live trading_enabled=true")
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Live arm failed", str(exc))
            self._append_activity(f"ERROR  {exc}")
            return
        ok, detail = validate_live_config(self.config_path)
        if not ok:
            messagebox.showerror("Live config invalid", detail)
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
            self._show_page("tape")
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

    def _motion_tick(self) -> None:
        self._brand_phase += 0.12
        self._pulse = not self._pulse
        self._draw_brand_bar()
        if self.engine.running:
            self._set_pill(self.pill_sys, "RUNNING", C["mint"] if self._pulse else C["lime"])
        # Clear activity flash highlight after pulse window
        if time.time() > self._flash_until:
            with contextlib.suppress(Exception):
                self.activity.tag_remove("flash", "1.0", tk.END)
        self.root.after(80, self._motion_tick)

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
