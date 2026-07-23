"""ACCOUNT BRAIN — CHECK SYSTEM neural ops console (Tkinter).

Central brain mesh is the main view. Node colors blink when subsystems fail.
ACCOUNTS tab edits per-client lot size via runtime/accounts/<id>/lot.json.
"""

from __future__ import annotations

import contextlib
import math
import queue
import random
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
    audit_file,
    brain_node_states,
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

# Cyber neural palette — dark void + electric signal colors
C = {
    "void": "#05070C",
    "panel": "#0A0E16",
    "panel2": "#0F1520",
    "line": "#1A2740",
    "ink": "#E8F0FF",
    "mute": "#6B7C99",
    "cyan": "#00D4FF",
    "blue": "#2A6BFF",
    "green": "#39FF14",
    "mint": "#00FF88",
    "amber": "#FFBF00",
    "orange": "#FF7A1A",
    "magenta": "#FF2BD6",
    "violet": "#8B5CFF",
    "red": "#FF3355",
    "core": "#C44DFF",
}


def _font(cands: list[str], size: int, weight: str = "normal") -> tuple:
    fam = set(tkfont.families())
    for name in cands:
        if name in fam:
            return (name, size, weight) if weight != "normal" else (name, size)
    return ("TkDefaultFont", size, weight) if weight != "normal" else ("TkDefaultFont", size)


def _lerp_hex(a: str, b: str, t: float) -> str:
    t = max(0.0, min(1.0, t))

    def ch(h: str) -> tuple[int, int, int]:
        h = h.lstrip("#")
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

    ar, ag, ab = ch(a)
    br, bg, bb = ch(b)
    return f"#{int(ar + (br - ar) * t):02x}{int(ag + (bg - ag) * t):02x}{int(ab + (bb - ab) * t):02x}"


LEVEL_BASE = {
    "ok": C["mint"],
    "warn": C["amber"],
    "error": C["red"],
    "idle": C["blue"],
}
LEVEL_HOT = {
    "ok": C["green"],
    "warn": C["orange"],
    "error": C["magenta"],
    "idle": C["cyan"],
}


class BrainMesh:
    """Procedural neural-brain silhouette with status-bound hub nodes."""

    def __init__(self, canvas: tk.Canvas) -> None:
        self.canvas = canvas
        self.phase = 0.0
        self.hubs: dict[str, dict] = {}
        self.satellites: list[dict] = []
        self.edges: list[tuple[int, int]] = []
        self._built_for: tuple[int, int] | None = None
        self._node_ids: list[int] = []
        self._edge_ids: list[int] = []
        self._glow_ids: list[int] = []
        self._label_ids: list[int] = []
        self._states: dict[str, object] = {}

    def ensure_layout(self) -> None:
        w = max(self.canvas.winfo_width(), 100)
        h = max(self.canvas.winfo_height(), 100)
        key = (w, h)
        if self._built_for == key and self.hubs:
            return
        self._built_for = key
        self._layout(w, h)

    def _layout(self, w: int, h: int) -> None:
        cx, cy = w * 0.52, h * 0.48
        rx, ry = w * 0.30, h * 0.34
        rng = random.Random(42)

        # Hub roles placed in brain lobes
        hub_specs = [
            ("core", 0.0, 0.05, 11),
            ("engine", -0.35, -0.25, 8),
            ("bridge", 0.42, -0.18, 8),
            ("connections", 0.55, 0.22, 7),
            ("trading", -0.48, 0.15, 8),
            ("data_flow", 0.15, -0.55, 7),
            ("risk", -0.20, 0.55, 8),
            ("trail", 0.28, 0.48, 7),
            ("accounts", -0.55, -0.05, 7),
        ]
        self.hubs = {}
        points: list[tuple[float, float]] = []
        for key, nx, ny, r in hub_specs:
            x = cx + nx * rx
            y = cy + ny * ry
            self.hubs[key] = {"x": x, "y": y, "r": r, "i": len(points)}
            points.append((x, y))

        # Satellite field — denser center, brain-ish oval clip
        self.satellites = []
        for _ in range(78):
            ang = rng.uniform(0, math.tau)
            # Slight frontal bulge + cerebellum dip
            rr = rng.uniform(0.15, 1.0) ** 0.65
            ox = math.cos(ang) * rr
            oy = math.sin(ang) * rr * (0.85 + 0.15 * math.cos(ang * 2))
            if oy > 0.55 and abs(ox) < 0.25:
                oy += 0.08  # brainstem hint
            x = cx + ox * rx
            y = cy + oy * ry
            self.satellites.append(
                {
                    "x": x,
                    "y": y,
                    "r": rng.uniform(1.6, 3.4),
                    "phase": rng.uniform(0, math.tau),
                    "hub": rng.choice(list(self.hubs)),
                }
            )
            points.append((x, y))

        # Edges: connect each point to a few nearest
        self.edges = []
        for i, (x, y) in enumerate(points):
            dists = []
            for j, (x2, y2) in enumerate(points):
                if i >= j:
                    continue
                d = (x - x2) ** 2 + (y - y2) ** 2
                dists.append((d, j))
            dists.sort()
            for d, j in dists[:3]:
                if d < (rx * 0.55) ** 2:
                    self.edges.append((i, j))

        self._all_points = points

    def set_states(self, states: list) -> None:
        self._states = {s.key: s for s in states}

    def draw(self) -> None:
        self.ensure_layout()
        c = self.canvas
        c.delete("brain")
        w = max(c.winfo_width(), 2)
        h = max(c.winfo_height(), 2)

        # Atmosphere wash
        c.create_oval(
            w * 0.22,
            h * 0.12,
            w * 0.82,
            h * 0.88,
            fill="#080C18",
            outline="",
            tags="brain",
        )
        # Magenta core nebula
        pulse = 0.5 + 0.5 * math.sin(self.phase * 1.4)
        core = self.hubs.get("core")
        if core:
            glow = 40 + 25 * pulse
            c.create_oval(
                core["x"] - glow,
                core["y"] - glow * 0.85,
                core["x"] + glow,
                core["y"] + glow * 0.85,
                fill="",
                outline=C["core"],
                width=1,
                tags="brain",
            )
            c.create_oval(
                core["x"] - glow * 0.55,
                core["y"] - glow * 0.45,
                core["x"] + glow * 0.55,
                core["y"] + glow * 0.45,
                fill="#1A0A28",
                outline="",
                tags="brain",
            )

        points = self._all_points
        # Edges
        for i, j in self.edges:
            x1, y1 = points[i]
            x2, y2 = points[j]
            c.create_line(x1, y1, x2, y2, fill="#14305A", width=1, tags="brain")

        # Satellites inherit hub status
        for sat in self.satellites:
            st = self._states.get(sat["hub"])
            level = getattr(st, "level", "idle") if st else "idle"
            base = LEVEL_BASE.get(level, C["blue"])
            hot = LEVEL_HOT.get(level, C["cyan"])
            blink = level in {"error", "warn"}
            t = 0.5 + 0.5 * math.sin(self.phase * (4.5 if level == "error" else 2.2) + sat["phase"])
            if not blink:
                t = 0.25 + 0.15 * math.sin(self.phase + sat["phase"])
            color = _lerp_hex(base, hot, t if blink else t * 0.5)
            r = sat["r"] * (1.15 + 0.35 * t if blink else 1.0)
            c.create_oval(
                sat["x"] - r,
                sat["y"] - r,
                sat["x"] + r,
                sat["y"] + r,
                fill=color,
                outline="",
                tags="brain",
            )

        # Hubs
        for key, hub in self.hubs.items():
            st = self._states.get(key)
            level = getattr(st, "level", "idle") if st else "idle"
            detail = getattr(st, "detail", "") if st else ""
            label = getattr(st, "label", key.upper()) if st else key.upper()
            base = LEVEL_BASE.get(level, C["blue"])
            hot = LEVEL_HOT.get(level, C["cyan"])
            blink = level in {"error", "warn"}
            t = 0.5 + 0.5 * math.sin(self.phase * (5.0 if level == "error" else 2.5))
            if not blink:
                t = 0.35
            color = _lerp_hex(base, hot, t if blink else 0.2)
            r = hub["r"] * (1.0 + (0.45 * t if blink else 0.0))
            # outer ring
            c.create_oval(
                hub["x"] - r - 4,
                hub["y"] - r - 4,
                hub["x"] + r + 4,
                hub["y"] + r + 4,
                outline=color,
                width=2 if blink else 1,
                tags="brain",
            )
            c.create_oval(
                hub["x"] - r,
                hub["y"] - r,
                hub["x"] + r,
                hub["y"] + r,
                fill=color,
                outline="",
                tags="brain",
            )
            c.create_text(
                hub["x"],
                hub["y"] - r - 12,
                text=label,
                fill=C["ink"] if blink else C["mute"],
                font=("Segoe UI", 8, "bold"),
                tags="brain",
            )
            if blink or key == "core":
                c.create_text(
                    hub["x"],
                    hub["y"] + r + 11,
                    text=detail[:28],
                    fill=color,
                    font=("Segoe UI", 7),
                    tags="brain",
                )


class DashboardApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("ACCOUNT BRAIN · CHECK SYSTEM")
        self.root.geometry("1480x900")
        self.root.minsize(1180, 740)
        self.root.configure(bg=C["void"])

        self.f_mega = _font(["Bahnschrift", "Segoe UI Variable Display", "Arial Black"], 28, "bold")
        self.f_brand = _font(["Bahnschrift", "Segoe UI"], 14, "bold")
        self.f_h1 = _font(["Bahnschrift", "Segoe UI"], 13, "bold")
        self.f_ui = _font(["Bahnschrift", "Segoe UI"], 10)
        self.f_ui_b = _font(["Bahnschrift SemiBold", "Segoe UI"], 10, "bold")
        self.f_mono = _font(["Cascadia Mono", "Consolas", "Courier New"], 9)

        self.config_path = resolve_config()
        self.engine = EngineProcess()
        self.log_queue: queue.Queue[str] = queue.Queue()
        self._page = "main"
        self._nav_btns: dict[str, tk.Button] = {}
        self._health = None
        self._lot_vars: dict[str, tk.StringVar] = {}
        self._lot_rows: dict[str, tk.Frame] = {}
        self._started_wall = time.time()
        self._selected_node = tk.StringVar(value="core · standby")

        self._build()
        self.refresh()
        self.root.after(80, self._motion_tick)
        self.root.after(500, self._tick)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build(self) -> None:
        shell = tk.Frame(self.root, bg=C["void"])
        shell.pack(fill=tk.BOTH, expand=True)

        self._build_nav(shell)

        title_row = tk.Frame(shell, bg=C["void"])
        title_row.pack(fill=tk.X, padx=22, pady=(10, 0))
        self.title_lbl = tk.Label(
            title_row,
            text="ACCOUNT BRAIN — ",
            bg=C["void"],
            fg=C["ink"],
            font=self.f_mega,
            anchor="w",
        )
        self.title_lbl.pack(side=tk.LEFT)
        self.online_lbl = tk.Label(
            title_row,
            text="OFFLINE",
            bg=C["void"],
            fg=C["red"],
            font=self.f_mega,
            anchor="w",
        )
        self.online_lbl.pack(side=tk.LEFT)
        self.node_hint = tk.Label(
            title_row,
            textvariable=self._selected_node,
            bg=C["void"],
            fg=C["mute"],
            font=self.f_ui,
            anchor="e",
        )
        self.node_hint.pack(side=tk.RIGHT)

        mid = tk.Frame(shell, bg=C["void"])
        mid.pack(fill=tk.BOTH, expand=True, padx=16, pady=8)

        self.pages: dict[str, tk.Frame] = {}
        self.pages["main"] = self._page_main(mid)
        self.pages["accounts"] = self._page_accounts(mid)
        self.pages["requests"] = self._page_requests(mid)
        self.pages["settings"] = self._page_settings(mid)
        self._show_page("main")

        self._build_footer(shell)

    def _build_nav(self, parent: tk.Misc) -> None:
        nav = tk.Frame(parent, bg=C["panel"], height=64)
        nav.pack(fill=tk.X)
        nav.pack_propagate(False)
        inner = tk.Frame(nav, bg=C["panel"])
        inner.pack(side=tk.LEFT, padx=16, pady=12)

        for key, label, accent in (
            ("main", "MAIN", C["cyan"]),
            ("accounts", "ACCOUNTS", C["blue"]),
            ("requests", "REQUESTS", C["violet"]),
            ("settings", "SETTINGS", C["amber"]),
            ("stop", "STOP", C["red"]),
        ):
            btn = tk.Button(
                inner,
                text=label,
                command=(self._confirm_stop if key == "stop" else (lambda k=key: self._show_page(k))),
                bg=C["panel2"],
                fg=accent,
                activebackground=C["line"],
                activeforeground=accent,
                relief=tk.FLAT,
                bd=0,
                highlightthickness=1,
                highlightbackground=accent,
                highlightcolor=accent,
                font=self.f_ui_b,
                padx=18,
                pady=10,
                cursor="hand2",
            )
            btn.pack(side=tk.LEFT, padx=5)
            self._nav_btns[key] = btn

        right = tk.Frame(nav, bg=C["panel"])
        right.pack(side=tk.RIGHT, padx=16)
        tk.Button(
            right,
            text="START LIVE",
            command=self._start_live,
            bg=C["panel2"],
            fg=C["green"],
            activebackground=C["line"],
            activeforeground=C["green"],
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=C["green"],
            font=self.f_ui_b,
            padx=14,
            pady=10,
            cursor="hand2",
        ).pack(side=tk.LEFT, padx=4)
        tk.Button(
            right,
            text="PAPER",
            command=self._start_paper,
            bg=C["panel2"],
            fg=C["cyan"],
            activebackground=C["line"],
            activeforeground=C["cyan"],
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=C["cyan"],
            font=self.f_ui_b,
            padx=14,
            pady=10,
            cursor="hand2",
        ).pack(side=tk.LEFT, padx=4)

    def _show_page(self, key: str) -> None:
        self._page = key
        for name, frame in self.pages.items():
            if name == key:
                frame.pack(fill=tk.BOTH, expand=True)
            else:
                frame.pack_forget()
        for name, btn in self._nav_btns.items():
            if name == "stop":
                continue
            accent = {
                "main": C["cyan"],
                "accounts": C["blue"],
                "requests": C["violet"],
                "settings": C["amber"],
            }.get(name, C["mute"])
            if name == key:
                btn.configure(bg=C["line"], fg=C["ink"], highlightbackground=C["ink"])
            else:
                btn.configure(bg=C["panel2"], fg=accent, highlightbackground=accent)

    def _page_main(self, parent: tk.Misc) -> tk.Frame:
        frame = tk.Frame(parent, bg=C["void"])
        left = tk.Frame(frame, bg=C["void"])
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.brain_canvas = tk.Canvas(left, bg=C["void"], highlightthickness=0)
        self.brain_canvas.pack(fill=tk.BOTH, expand=True)
        self.brain = BrainMesh(self.brain_canvas)
        self.brain_canvas.bind("<Configure>", lambda _e: self.brain.draw())

        # Logo mark bottom-left
        mark = tk.Canvas(left, width=72, height=72, bg=C["void"], highlightthickness=0)
        mark.place(x=8, y=-80, relheight=0, rely=1.0)
        mark.create_oval(6, 6, 66, 66, outline=C["amber"], width=2)
        mark.create_polygon(36, 16, 50, 40, 36, 56, 22, 40, fill=C["mint"], outline="")
        tk.Label(left, text="IVAN-CORE DATA STREAM", bg=C["void"], fg=C["mute"], font=self.f_ui).place(
            x=88, rely=1.0, y=-36
        )

        side = tk.Frame(frame, bg=C["panel"], width=320)
        side.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
        side.pack_propagate(False)
        tk.Label(side, text="NODE STATUS", bg=C["panel"], fg=C["cyan"], font=self.f_h1).pack(
            anchor="w", padx=14, pady=(14, 6)
        )
        self.node_list = tk.Text(
            side,
            bg=C["panel2"],
            fg=C["ink"],
            insertbackground=C["ink"],
            relief=tk.FLAT,
            font=self.f_mono,
            height=18,
            wrap=tk.WORD,
        )
        self.node_list.pack(fill=tk.BOTH, expand=True, padx=12, pady=8)
        self.node_list.configure(state=tk.DISABLED)

        tk.Label(side, text="LIVE TAPE", bg=C["panel"], fg=C["violet"], font=self.f_h1).pack(
            anchor="w", padx=14, pady=(4, 4)
        )
        self.tape = tk.Text(
            side,
            bg=C["panel2"],
            fg=C["mute"],
            relief=tk.FLAT,
            font=self.f_mono,
            height=10,
            wrap=tk.NONE,
        )
        self.tape.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))
        self.tape.configure(state=tk.DISABLED)
        return frame

    def _page_accounts(self, parent: tk.Misc) -> tk.Frame:
        frame = tk.Frame(parent, bg=C["void"])
        head = tk.Frame(frame, bg=C["void"])
        head.pack(fill=tk.X, pady=(4, 10))
        tk.Label(
            head,
            text="PER-CLIENT LOT SIZE",
            bg=C["void"],
            fg=C["cyan"],
            font=self.f_h1,
        ).pack(side=tk.LEFT)
        tk.Label(
            head,
            text="Writes runtime/accounts/<id>/lot.json — engine picks it up next cycle",
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

    def _page_requests(self, parent: tk.Misc) -> tk.Frame:
        frame = tk.Frame(parent, bg=C["void"])
        tk.Label(frame, text="BRIDGE / AUDIT REQUESTS", bg=C["void"], fg=C["violet"], font=self.f_h1).pack(
            anchor="w", pady=(4, 8)
        )
        self.requests_text = tk.Text(
            frame,
            bg=C["panel"],
            fg=C["ink"],
            relief=tk.FLAT,
            font=self.f_mono,
            wrap=tk.NONE,
        )
        self.requests_text.pack(fill=tk.BOTH, expand=True)
        self.requests_text.configure(state=tk.DISABLED)
        return frame

    def _page_settings(self, parent: tk.Misc) -> tk.Frame:
        frame = tk.Frame(parent, bg=C["void"])
        tk.Label(frame, text="SETTINGS", bg=C["void"], fg=C["amber"], font=self.f_h1).pack(anchor="w", pady=(4, 12))

        self.settings_info = tk.Label(frame, text="", bg=C["void"], fg=C["ink"], font=self.f_mono, justify=tk.LEFT)
        self.settings_info.pack(anchor="w")

        row = tk.Frame(frame, bg=C["void"])
        row.pack(anchor="w", pady=16)
        tk.Button(
            row,
            text="ENABLE TRADING",
            command=lambda: self._set_trading(True),
            bg=C["panel2"],
            fg=C["green"],
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=C["green"],
            font=self.f_ui_b,
            padx=12,
            pady=8,
            cursor="hand2",
        ).pack(side=tk.LEFT, padx=4)
        tk.Button(
            row,
            text="DISABLE TRADING",
            command=lambda: self._set_trading(False),
            bg=C["panel2"],
            fg=C["amber"],
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=C["amber"],
            font=self.f_ui_b,
            padx=12,
            pady=8,
            cursor="hand2",
        ).pack(side=tk.LEFT, padx=4)
        tk.Button(
            row,
            text="CLEAR STOP",
            command=self._clear_stop,
            bg=C["panel2"],
            fg=C["cyan"],
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=C["cyan"],
            font=self.f_ui_b,
            padx=12,
            pady=8,
            cursor="hand2",
        ).pack(side=tk.LEFT, padx=4)
        tk.Button(
            row,
            text="DEPLOY MT4",
            command=self._deploy,
            bg=C["panel2"],
            fg=C["violet"],
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=C["violet"],
            font=self.f_ui_b,
            padx=12,
            pady=8,
            cursor="hand2",
        ).pack(side=tk.LEFT, padx=4)
        return frame

    def _build_footer(self, parent: tk.Misc) -> None:
        foot = tk.Frame(parent, bg=C["panel"], height=48)
        foot.pack(fill=tk.X, side=tk.BOTTOM)
        foot.pack_propagate(False)
        inner = tk.Frame(foot, bg=C["panel"])
        inner.pack(fill=tk.BOTH, expand=True, padx=18)

        self.foot_vars = {
            "uptime": tk.StringVar(value="—"),
            "flow": tk.StringVar(value="—"),
            "conn": tk.StringVar(value="—"),
            "time": tk.StringVar(value="LOCAL"),
            "system": tk.StringVar(value="OFFLINE"),
        }
        specs = (
            ("UPTIME", "uptime", C["green"]),
            ("DATA FLOW", "flow", C["amber"]),
            ("CONNECTIONS", "conn", C["mint"]),
            ("SERVER TIME", "time", C["cyan"]),
            ("SYSTEM", "system", C["green"]),
        )
        for i, (label, key, color) in enumerate(specs):
            cell = tk.Frame(inner, bg=C["panel"])
            cell.pack(side=tk.LEFT, expand=True, fill=tk.X)
            tk.Label(cell, text=label, bg=C["panel"], fg=C["mute"], font=self.f_ui).pack(anchor="w", pady=(8, 0))
            tk.Label(cell, textvariable=self.foot_vars[key], bg=C["panel"], fg=color, font=self.f_ui_b).pack(
                anchor="w"
            )

    # ── actions ────────────────────────────────────────────────────────────
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
            self._pump_engine_logs()
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Start failed", str(exc))

    def _start_paper(self) -> None:
        if self.engine.running:
            messagebox.showinfo("Engine", "Engine already running")
            return
        clear_stop(self._rt())
        try:
            self.engine.start(mode="paper", config_path=self.config_path)
            self._pump_engine_logs()
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Start failed", str(exc))

    def _pump_engine_logs(self) -> None:
        proc = self.engine.proc
        if proc is None or proc.stdout is None:
            return

        def reader() -> None:
            assert proc.stdout is not None
            for line in proc.stdout:
                self.log_queue.put(line.rstrip("\n"))

        threading.Thread(target=reader, daemon=True).start()

    def _confirm_stop(self) -> None:
        if not messagebox.askyesno("STOP", "Write STOP_TRADING and halt the engine?"):
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
        messagebox.showinfo("Deploy MT4", out[-1500:] if out else f"exit={code}")

    def _save_lot(self, account_id: str) -> None:
        var = self._lot_vars.get(account_id)
        if var is None:
            return
        try:
            lot = float(var.get().replace(",", "."))
        except ValueError:
            messagebox.showerror("Lot", f"Invalid lot for {account_id}")
            return
        cfg = self._cfg_data()
        mn, mx, _step = lot_bounds(cfg)
        if lot < mn or lot > mx:
            messagebox.showerror("Lot", f"Lot must be between {mn} and {mx}")
            return
        write_account_lot_override(self._rt(), account_id, lot)
        messagebox.showinfo("Lot", f"{account_id} → fixed_lot={lot:.2f}\nApplies on next engine cycle.")
        self.refresh()

    def _reset_lot(self, account_id: str) -> None:
        clear_account_lot_override(self._rt(), account_id)
        self.refresh()

    def _rebuild_account_rows(self, health) -> None:
        cfg = self._cfg_data()
        rt = self._rt()
        default_lot = default_fixed_lot(cfg)
        accounts = list_known_accounts(health, rt)
        # Also include bridges with unknown placeholder skipped
        for child in list(self.accounts_host.winfo_children()):
            if child is self.accounts_empty:
                continue
            child.destroy()
        self._lot_vars.clear()

        if not accounts:
            self.accounts_empty.pack(pady=40)
            return
        self.accounts_empty.pack_forget()

        bridge_by = {b.account_id: b for b in health.bridges}

        header = tk.Frame(self.accounts_host, bg=C["panel"])
        header.pack(fill=tk.X, pady=(0, 6))
        for col, w in (("ACCOUNT", 16), ("BALANCE", 12), ("SYMBOL", 12), ("LOT", 10), ("SOURCE", 12), ("", 20)):
            tk.Label(header, text=col, bg=C["panel"], fg=C["mute"], font=self.f_ui_b, width=w, anchor="w").pack(
                side=tk.LEFT, padx=6, pady=8
            )

        for acct in accounts:
            row = tk.Frame(self.accounts_host, bg=C["panel2"])
            row.pack(fill=tk.X, pady=3)
            br = bridge_by.get(acct)
            bal = f"{br.balance:,.2f}" if br else "—"
            sym = br.symbol if br else "—"
            override = read_account_lot_override(rt, acct)
            effective = override if override is not None else default_lot
            source = "override" if override is not None else "config"

            tk.Label(row, text=acct, bg=C["panel2"], fg=C["ink"], font=self.f_ui_b, width=16, anchor="w").pack(
                side=tk.LEFT, padx=6, pady=10
            )
            tk.Label(row, text=bal, bg=C["panel2"], fg=C["mint"], font=self.f_mono, width=12, anchor="w").pack(
                side=tk.LEFT, padx=6
            )
            tk.Label(row, text=sym, bg=C["panel2"], fg=C["cyan"], font=self.f_ui, width=12, anchor="w").pack(
                side=tk.LEFT, padx=6
            )

            var = tk.StringVar(value=f"{effective:.2f}")
            self._lot_vars[acct] = var
            ent = tk.Entry(
                row,
                textvariable=var,
                bg=C["void"],
                fg=C["amber"],
                insertbackground=C["ink"],
                relief=tk.FLAT,
                width=8,
                font=self.f_mono,
                highlightthickness=1,
                highlightbackground=C["line"],
            )
            ent.pack(side=tk.LEFT, padx=6)
            tk.Label(
                row,
                text=source,
                bg=C["panel2"],
                fg=C["violet"] if source == "override" else C["mute"],
                font=self.f_ui,
                width=12,
                anchor="w",
            ).pack(side=tk.LEFT, padx=6)
            tk.Button(
                row,
                text="SAVE",
                command=lambda a=acct: self._save_lot(a),
                bg=C["panel"],
                fg=C["green"],
                relief=tk.FLAT,
                font=self.f_ui_b,
                padx=10,
                cursor="hand2",
            ).pack(side=tk.LEFT, padx=4)
            tk.Button(
                row,
                text="RESET",
                command=lambda a=acct: self._reset_lot(a),
                bg=C["panel"],
                fg=C["mute"],
                relief=tk.FLAT,
                font=self.f_ui_b,
                padx=8,
                cursor="hand2",
            ).pack(side=tk.LEFT, padx=2)

    # ── refresh / animation ────────────────────────────────────────────────
    def refresh(self) -> None:
        try:
            health = collect_health(self.config_path)
        except Exception as exc:  # noqa: BLE001
            self._selected_node.set(f"health error: {exc}")
            return
        self._health = health
        states = brain_node_states(
            health,
            engine_running=self.engine.running,
            engine_mode=self.engine.mode,
        )
        self.brain.set_states(states)

        online = self.engine.running and not health.stop_present
        self.online_lbl.configure(
            text="ONLINE" if online else ("HALTED" if health.stop_present else "STANDBY"),
            fg=C["green"] if online else (C["red"] if health.stop_present else C["amber"]),
        )

        # Node panel
        lines = []
        worst = "idle"
        for st in states:
            mark = {"ok": "●", "warn": "▲", "error": "✖", "idle": "○"}.get(st.level, "·")
            lines.append(f"{mark} {st.label:<6} {st.level.upper():<5}  {st.detail}")
            if st.level == "error":
                worst = "error"
            elif st.level == "warn" and worst != "error":
                worst = "warn"
            elif st.level == "ok" and worst == "idle":
                worst = "ok"
        self._set_text(self.node_list, "\n".join(lines))
        core = next((s for s in states if s.key == "core"), None)
        if core:
            self._selected_node.set(f"{core.label} · {core.detail}")

        # Tape
        af = audit_file(self._cfg_data())
        rows = audit_activity(af, limit=12)
        tape_lines = [format_audit_line(r) for r in rows] or ["(no audit yet)"]
        self._set_text(self.tape, "\n".join(tape_lines))

        # Requests page
        req_lines = []
        for b in health.bridges:
            req_lines.append(
                f"{b.account_id}  market={format_age(b.market_age_s)}  status={format_age(b.status_age_s)}  "
                f"cmds={b.commands} acks={b.acks}  connected={b.connected}  trade={b.trading_allowed}"
            )
            for p in b.positions:
                req_lines.append(
                    f"    pos {p.ticket} {p.symbol} {p.side} lot={p.lot} sl={p.stop_loss} tp={p.take_profit} pl={p.profit:.2f}"
                )
        req_lines.append("")
        req_lines.extend(tape_lines[:20])
        self._set_text(self.requests_text, "\n".join(req_lines) or "(quiet)")

        # Settings
        cfg = self._cfg_data()
        runtime = cfg.get("runtime") or {}
        pos = cfg.get("position_sizing") or {}
        self.settings_info.configure(
            text=(
                f"config: {self.config_path}\n"
                f"mode: {runtime.get('mode')}   trading_enabled: {runtime.get('trading_enabled')}\n"
                f"symbol: {(cfg.get('instrument') or {}).get('symbol')}\n"
                f"default lot: {pos.get('fixed_lot')}   min/max: {pos.get('min_lot')}/{pos.get('max_lot')}\n"
                f"engine: {'RUNNING pid=' + str(self.engine.pid) if self.engine.running else 'IDLE'}\n"
                f"stop file: {'YES' if health.stop_present else 'no'}"
            )
        )

        if self._page == "accounts":
            self._rebuild_account_rows(health)

        # Footer
        uptime_s = time.time() - (self.engine.started_at or self._started_wall)
        if self.engine.running and self.engine.started_at:
            self.foot_vars["uptime"].set(f"READY  {int(uptime_s)}s")
        else:
            self.foot_vars["uptime"].set("READY" if not health.stop_present else "STOPPED")

        fresh = any(b.market_age_s is not None and b.market_age_s <= 15 for b in health.bridges)
        self.foot_vars["flow"].set("STREAMING" if fresh else ("WAITING" if health.bridges else "IDLE"))
        conn_ok = any(b.connected for b in health.bridges)
        self.foot_vars["conn"].set("STABLE" if conn_ok else ("DEGRADED" if health.bridges else "NONE"))
        self.foot_vars["time"].set(time.strftime("%H:%M:%S"))
        self.foot_vars["system"].set("ONLINE" if online else ("FAULT" if worst == "error" else "STANDBY"))

    def _set_text(self, widget: tk.Text, text: str) -> None:
        widget.configure(state=tk.NORMAL)
        widget.delete("1.0", tk.END)
        widget.insert(tk.END, text)
        widget.configure(state=tk.DISABLED)

    def _motion_tick(self) -> None:
        self.brain.phase += 0.12
        if self._page == "main":
            self.brain.draw()
        # Drain log queue into tape lightly
        drained = 0
        while drained < 20:
            try:
                line = self.log_queue.get_nowait()
            except queue.Empty:
                break
            drained += 1
            if line:
                self.tape.configure(state=tk.NORMAL)
                self.tape.insert(tk.END, line + "\n")
                self.tape.see(tk.END)
                self.tape.configure(state=tk.DISABLED)
        code = self.engine.poll_exit()
        if code is not None and code != 0:
            self._selected_node.set(f"engine exited code={code}")
        self.root.after(80, self._motion_tick)

    def _tick(self) -> None:
        self.refresh()
        self.root.after(900, self._tick)

    def _on_close(self) -> None:
        if self.engine.running:
            if messagebox.askyesno("Quit", "Engine is running. Stop it and exit?"):
                write_stop(self._rt())
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
