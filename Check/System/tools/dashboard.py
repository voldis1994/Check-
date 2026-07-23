"""ACCOUNT BRAIN — CHECK SYSTEM neural ops console (Tkinter).

Prototype-style neural brain backdrop + interactive status nodes.
Every visible node is clickable and runs a real dashboard function.
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
ASSETS = ROOT / "assets"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

from dashboard_core import (  # noqa: E402
    BRAIN_HUB_META,
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

C = {
    "void": "#03050A",
    "panel": "#070B14",
    "panel2": "#0C1220",
    "line": "#1A2A48",
    "ink": "#EAF2FF",
    "mute": "#6E7F9C",
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

LEVEL_BASE = {"ok": C["mint"], "warn": C["amber"], "error": C["red"], "idle": C["blue"]}
LEVEL_HOT = {"ok": C["green"], "warn": C["orange"], "error": C["magenta"], "idle": C["cyan"]}

# Normalized positions on the brain image (side-view silhouette).
HUB_LAYOUT = {
    "core": (0.50, 0.46),
    "engine": (0.34, 0.30),
    "bridge": (0.68, 0.34),
    "connections": (0.74, 0.52),
    "trading": (0.28, 0.50),
    "data_flow": (0.52, 0.22),
    "risk": (0.40, 0.70),
    "trail": (0.62, 0.68),
    "accounts": (0.24, 0.38),
}

# Lobe regions → parent hub (every mesh point maps to a real action via parent).
LOBE_SEEDS = [
    ("engine", 0.30, 0.28, 0.10, 0.10),
    ("trading", 0.26, 0.48, 0.09, 0.10),
    ("accounts", 0.22, 0.38, 0.08, 0.08),
    ("data_flow", 0.50, 0.24, 0.12, 0.08),
    ("bridge", 0.68, 0.32, 0.10, 0.10),
    ("connections", 0.74, 0.50, 0.08, 0.09),
    ("trail", 0.62, 0.66, 0.10, 0.08),
    ("risk", 0.42, 0.68, 0.10, 0.08),
    ("core", 0.50, 0.46, 0.14, 0.12),
]


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


class BrainMesh:
    """Neural brain HUD: backdrop image + dense interactive functional nodes."""

    def __init__(self, canvas: tk.Canvas, on_click, on_hover) -> None:
        self.canvas = canvas
        self.on_click = on_click
        self.on_hover = on_hover
        self.phase = 0.0
        self._states: dict[str, object] = {}
        self._points: list[dict] = []
        self._edges: list[tuple[int, int]] = []
        self._built_for: tuple[int, int, tuple] | None = None
        self._bg_img: tk.PhotoImage | None = None
        self._bg_box = (0, 0, 1, 1)  # x0,y0,w,h
        self._hover_key: str | None = None
        canvas.bind("<Button-1>", self._click)
        canvas.bind("<Motion>", self._motion)
        canvas.bind("<Leave>", lambda _e: self.on_hover(None))

    def set_states(self, states: list) -> None:
        self._states = {s.key: s for s in states}
        # Force relayout when dynamic account/pos nodes change.
        sig = tuple(sorted(self._states))
        if self._built_for and self._built_for[2] != sig:
            self._built_for = None

    def ensure_layout(self) -> None:
        w = max(self.canvas.winfo_width(), 120)
        h = max(self.canvas.winfo_height(), 120)
        sig = tuple(sorted(self._states))
        key = (w, h, sig)
        if self._built_for == key and self._points:
            return
        self._built_for = key
        self._layout(w, h)

    def _load_backdrop(self, w: int, h: int) -> None:
        self._bg_img = None
        for name in ("account_brain_mesh_hud.png", "account_brain_mesh.png"):
            path = ASSETS / name
            if not path.exists():
                continue
            try:
                img = tk.PhotoImage(file=str(path))
            except tk.TclError:
                continue
            iw, ih = img.width(), img.height()
            # Integer subsample to fit canvas while keeping brain dominant.
            factor = max(1, math.ceil(max(iw / max(w * 0.98, 1), ih / max(h * 0.98, 1))))
            if factor > 1:
                img = img.subsample(factor, factor)
                iw, ih = img.width(), img.height()
            # Optional integer zoom if much smaller than canvas.
            zx = max(1, int(w * 0.92 / max(iw, 1)))
            zy = max(1, int(h * 0.92 / max(ih, 1)))
            z = min(zx, zy)
            if z > 1:
                img = img.zoom(z, z)
                iw, ih = img.width(), img.height()
            self._bg_img = img
            x0 = (w - iw) // 2
            y0 = (h - ih) // 2
            self._bg_box = (x0, y0, iw, ih)
            return
        # Fallback box if image missing
        bw, bh = int(w * 0.78), int(h * 0.82)
        self._bg_box = ((w - bw) // 2, (h - bh) // 2, bw, bh)

    def _map(self, nx: float, ny: float) -> tuple[float, float]:
        x0, y0, bw, bh = self._bg_box
        return x0 + nx * bw, y0 + ny * bh

    def _layout(self, w: int, h: int) -> None:
        self._load_backdrop(w, h)
        rng = random.Random(7)
        points: list[dict] = []

        # Hub nodes (large, labeled)
        for key, (nx, ny) in HUB_LAYOUT.items():
            meta = BRAIN_HUB_META[key]
            x, y = self._map(nx, ny)
            points.append(
                {
                    "key": key,
                    "kind": "hub",
                    "x": x,
                    "y": y,
                    "r": 11,
                    "nx": nx,
                    "ny": ny,
                    "phase": rng.uniform(0, math.tau),
                    "parent": key,
                    "action": meta["action"],
                    "hint": meta["hint"],
                    "label": meta["label"],
                }
            )

        # Dense functional mesh — every point inherits a hub action
        for parent, cx, cy, rx, ry in LOBE_SEEDS:
            meta = BRAIN_HUB_META[parent]
            count = 18 if parent == "core" else 14
            for i in range(count):
                ang = rng.uniform(0, math.tau)
                rr = rng.uniform(0.15, 1.0) ** 0.55
                nx = cx + math.cos(ang) * rx * rr
                ny = cy + math.sin(ang) * ry * rr * (0.9 + 0.1 * math.cos(ang * 2))
                # Keep inside brain-ish oval
                if (nx - 0.5) ** 2 / 0.28**2 + (ny - 0.48) ** 2 / 0.36**2 > 1.05:
                    continue
                x, y = self._map(nx, ny)
                points.append(
                    {
                        "key": f"mesh:{parent}:{i}",
                        "kind": "mesh",
                        "x": x,
                        "y": y,
                        "r": rng.uniform(2.2, 3.8),
                        "nx": nx,
                        "ny": ny,
                        "phase": rng.uniform(0, math.tau),
                        "parent": parent,
                        "action": meta["action"],
                        "hint": meta["hint"],
                        "label": meta["label"],
                    }
                )

        # Dynamic account / position nodes from state keys
        acct_nodes = [k for k in self._states if str(k).startswith("acct:")]
        pos_nodes = [k for k in self._states if str(k).startswith("pos:")]
        for i, key in enumerate(acct_nodes):
            st = self._states[key]
            nx = 0.18 + (i % 3) * 0.07
            ny = 0.56 + (i // 3) * 0.08
            x, y = self._map(nx, ny)
            points.append(
                {
                    "key": key,
                    "kind": "account",
                    "x": x,
                    "y": y,
                    "r": 8,
                    "nx": nx,
                    "ny": ny,
                    "phase": rng.uniform(0, math.tau),
                    "parent": "accounts",
                    "action": getattr(st, "action", "edit_lot"),
                    "hint": getattr(st, "hint", "Edit lot"),
                    "label": getattr(st, "label", key),
                }
            )
        for i, key in enumerate(pos_nodes):
            st = self._states[key]
            nx = 0.58 + (i % 4) * 0.06
            ny = 0.58 + (i // 4) * 0.07
            x, y = self._map(nx, ny)
            points.append(
                {
                    "key": key,
                    "kind": "position",
                    "x": x,
                    "y": y,
                    "r": 6,
                    "nx": nx,
                    "ny": ny,
                    "phase": rng.uniform(0, math.tau),
                    "parent": "trail",
                    "action": getattr(st, "action", "show_position"),
                    "hint": getattr(st, "hint", "Position"),
                    "label": getattr(st, "label", "POS"),
                }
            )

        # Nearest-neighbor edges for wireframe overlay
        edges: list[tuple[int, int]] = []
        for i, p in enumerate(points):
            dists = []
            for j, q in enumerate(points):
                if j <= i:
                    continue
                d = (p["x"] - q["x"]) ** 2 + (p["y"] - q["y"]) ** 2
                dists.append((d, j))
            dists.sort()
            for d, j in dists[:2]:
                if d < (min(w, h) * 0.12) ** 2:
                    edges.append((i, j))

        self._points = points
        self._edges = edges

    def _status_for(self, point: dict) -> object | None:
        if point["key"] in self._states:
            return self._states[point["key"]]
        return self._states.get(point["parent"])

    def draw(self) -> None:
        self.ensure_layout()
        c = self.canvas
        c.delete("brain")
        w = max(c.winfo_width(), 2)
        h = max(c.winfo_height(), 2)
        c.create_rectangle(0, 0, w, h, fill=C["void"], outline="", tags="brain")

        x0, y0, bw, bh = self._bg_box
        if self._bg_img is not None:
            c.create_image(x0 + bw // 2, y0 + bh // 2, image=self._bg_img, tags="brain")
        else:
            # Procedural fallback silhouette
            c.create_oval(x0, y0, x0 + bw, y0 + bh, fill="#081018", outline="#123050", width=2, tags="brain")
            c.create_oval(
                x0 + bw * 0.35,
                y0 + bh * 0.35,
                x0 + bw * 0.65,
                y0 + bh * 0.62,
                fill="#1A0A28",
                outline="",
                tags="brain",
            )

        # Soft magenta core pulse over backdrop
        pulse = 0.5 + 0.5 * math.sin(self.phase * 1.3)
        cx, cy = self._map(0.50, 0.46)
        glow = 55 + 30 * pulse
        c.create_oval(cx - glow, cy - glow * 0.8, cx + glow, cy + glow * 0.8, outline=C["core"], width=1, tags="brain")

        for i, j in self._edges:
            p, q = self._points[i], self._points[j]
            c.create_line(p["x"], p["y"], q["x"], q["y"], fill="#0E3A6A", width=1, tags="brain")

        for p in self._points:
            st = self._status_for(p)
            level = getattr(st, "level", "idle") if st else "idle"
            base = LEVEL_BASE.get(level, C["blue"])
            hot = LEVEL_HOT.get(level, C["cyan"])
            blink = level in {"error", "warn"}
            speed = 5.2 if level == "error" else 2.6
            t = 0.5 + 0.5 * math.sin(self.phase * speed + p["phase"])
            if not blink:
                t = 0.2 + 0.15 * math.sin(self.phase * 1.2 + p["phase"])
            color = _lerp_hex(base, hot, t if blink else t)
            r = p["r"] * (1.0 + (0.55 * t if blink else 0.0))
            if p["kind"] == "hub":
                c.create_oval(p["x"] - r - 5, p["y"] - r - 5, p["x"] + r + 5, p["y"] + r + 5, outline=color, width=2, tags="brain")
            c.create_oval(p["x"] - r, p["y"] - r, p["x"] + r, p["y"] + r, fill=color, outline="", tags=("brain", "node", p["key"]))
            if p["kind"] in {"hub", "account", "position"} or self._hover_key == p["key"]:
                c.create_text(
                    p["x"],
                    p["y"] - r - 11,
                    text=str(p["label"]),
                    fill=C["ink"] if blink or p["kind"] == "hub" else C["mute"],
                    font=("Segoe UI", 8, "bold"),
                    tags="brain",
                )
            if p["kind"] == "hub" and (blink or p["key"] == "core"):
                detail = getattr(st, "detail", "") if st else ""
                c.create_text(p["x"], p["y"] + r + 12, text=str(detail)[:26], fill=color, font=("Segoe UI", 7), tags="brain")

        # Hint strip
        c.create_text(
            12,
            h - 14,
            anchor="w",
            text="Click any glowing node — each point runs a system function",
            fill=C["mute"],
            font=("Segoe UI", 8),
            tags="brain",
        )

    def _hit(self, x: float, y: float) -> dict | None:
        best = None
        best_d = 1e18
        for p in self._points:
            pad = 10 if p["kind"] == "hub" else 6
            d = (p["x"] - x) ** 2 + (p["y"] - y) ** 2
            if d <= (p["r"] + pad) ** 2 and d < best_d:
                best = p
                best_d = d
        return best

    def _click(self, event) -> None:
        hit = self._hit(event.x, event.y)
        if hit:
            self.on_click(hit)

    def _motion(self, event) -> None:
        hit = self._hit(event.x, event.y)
        key = hit["key"] if hit else None
        if key != self._hover_key:
            self._hover_key = key
            self.canvas.configure(cursor="hand2" if hit else "")
            self.on_hover(hit)


class DashboardApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("ACCOUNT BRAIN · CHECK SYSTEM")
        self.root.geometry("1520x940")
        self.root.minsize(1220, 760)
        self.root.configure(bg=C["void"])

        self.f_mega = _font(["Bahnschrift", "Segoe UI Variable Display", "Arial Black"], 28, "bold")
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
        self._started_wall = time.time()
        self._selected_node = tk.StringVar(value="Hover a node · click to run its function")
        self._focus_account: str | None = None
        self._action_btns: list[tk.Button] = []

        self._build()
        self.refresh()
        self.root.after(70, self._motion_tick)
        self.root.after(800, self._tick)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build(self) -> None:
        shell = tk.Frame(self.root, bg=C["void"])
        shell.pack(fill=tk.BOTH, expand=True)
        self._build_nav(shell)

        title_row = tk.Frame(shell, bg=C["void"])
        title_row.pack(fill=tk.X, padx=22, pady=(10, 0))
        tk.Label(title_row, text="ACCOUNT BRAIN — ", bg=C["void"], fg=C["ink"], font=self.f_mega, anchor="w").pack(
            side=tk.LEFT
        )
        self.online_lbl = tk.Label(title_row, text="OFFLINE", bg=C["void"], fg=C["red"], font=self.f_mega, anchor="w")
        self.online_lbl.pack(side=tk.LEFT)
        tk.Label(title_row, textvariable=self._selected_node, bg=C["void"], fg=C["mute"], font=self.f_ui, anchor="e").pack(
            side=tk.RIGHT
        )

        # Action tray under title — filled when a node is selected
        self.action_tray = tk.Frame(shell, bg=C["panel"], height=46)
        self.action_tray.pack(fill=tk.X, padx=16, pady=(8, 0))
        self.action_tray.pack_propagate(False)
        self.action_label = tk.Label(
            self.action_tray,
            text="Select a brain node to activate its function",
            bg=C["panel"],
            fg=C["cyan"],
            font=self.f_ui_b,
            anchor="w",
        )
        self.action_label.pack(side=tk.LEFT, padx=14)
        self.action_btns_host = tk.Frame(self.action_tray, bg=C["panel"])
        self.action_btns_host.pack(side=tk.RIGHT, padx=10)

        mid = tk.Frame(shell, bg=C["void"])
        mid.pack(fill=tk.BOTH, expand=True, padx=16, pady=8)
        self.pages: dict[str, tk.Frame] = {}
        self.pages["main"] = self._page_main(mid)
        self.pages["accounts"] = self._page_accounts(mid)
        self.pages["requests"] = self._page_requests(mid)
        self.pages["settings"] = self._page_settings(mid)
        self._show_page("main")
        self._build_footer(shell)

    def _tray_button(self, text: str, color: str, command) -> None:
        btn = tk.Button(
            self.action_btns_host,
            text=text,
            command=command,
            bg=C["panel2"],
            fg=color,
            activebackground=C["line"],
            activeforeground=color,
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=color,
            font=self.f_ui_b,
            padx=12,
            pady=6,
            cursor="hand2",
        )
        btn.pack(side=tk.LEFT, padx=4, pady=6)
        self._action_btns.append(btn)

    def _clear_tray(self) -> None:
        for b in self._action_btns:
            b.destroy()
        self._action_btns.clear()

    def _set_tray(self, title: str, buttons: list[tuple[str, str, object]]) -> None:
        self._clear_tray()
        self.action_label.configure(text=title)
        for text, color, cmd in buttons:
            self._tray_button(text, color, cmd)

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
            accent = {"main": C["cyan"], "accounts": C["blue"], "requests": C["violet"], "settings": C["amber"]}.get(
                name, C["mute"]
            )
            if name == key:
                btn.configure(bg=C["line"], fg=C["ink"], highlightbackground=C["ink"])
            else:
                btn.configure(bg=C["panel2"], fg=accent, highlightbackground=accent)
        if key == "accounts":
            self.refresh()

    def _page_main(self, parent: tk.Misc) -> tk.Frame:
        frame = tk.Frame(parent, bg=C["void"])
        left = tk.Frame(frame, bg=C["void"])
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.brain_canvas = tk.Canvas(left, bg=C["void"], highlightthickness=0)
        self.brain_canvas.pack(fill=tk.BOTH, expand=True)
        self.brain = BrainMesh(self.brain_canvas, on_click=self._on_brain_click, on_hover=self._on_brain_hover)
        self.brain_canvas.bind("<Configure>", lambda _e: self.brain.draw())

        mark = tk.Canvas(left, width=72, height=72, bg=C["void"], highlightthickness=0)
        mark.place(x=8, y=-80, rely=1.0)
        mark.create_oval(6, 6, 66, 66, outline=C["amber"], width=2)
        mark.create_polygon(36, 16, 50, 40, 36, 56, 22, 40, fill=C["mint"], outline="")
        tk.Label(left, text="IVAN-CORE DATA STREAM", bg=C["void"], fg=C["mute"], font=self.f_ui).place(
            x=88, rely=1.0, y=-36
        )

        side = tk.Frame(frame, bg=C["panel"], width=340)
        side.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
        side.pack_propagate(False)
        tk.Label(side, text="NODE STATUS", bg=C["panel"], fg=C["cyan"], font=self.f_h1).pack(
            anchor="w", padx=14, pady=(14, 6)
        )
        self.node_list = tk.Text(side, bg=C["panel2"], fg=C["ink"], relief=tk.FLAT, font=self.f_mono, height=18, wrap=tk.WORD)
        self.node_list.pack(fill=tk.BOTH, expand=True, padx=12, pady=8)
        self.node_list.configure(state=tk.DISABLED)
        tk.Label(side, text="LIVE TAPE", bg=C["panel"], fg=C["violet"], font=self.f_h1).pack(anchor="w", padx=14, pady=(4, 4))
        self.tape = tk.Text(side, bg=C["panel2"], fg=C["mute"], relief=tk.FLAT, font=self.f_mono, height=10, wrap=tk.NONE)
        self.tape.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))
        self.tape.configure(state=tk.DISABLED)
        return frame

    def _page_accounts(self, parent: tk.Misc) -> tk.Frame:
        frame = tk.Frame(parent, bg=C["void"])
        head = tk.Frame(frame, bg=C["void"])
        head.pack(fill=tk.X, pady=(4, 10))
        tk.Label(head, text="PER-CLIENT LOT SIZE", bg=C["void"], fg=C["cyan"], font=self.f_h1).pack(side=tk.LEFT)
        tk.Label(
            head,
            text="Each account node on the brain opens this editor",
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
        self.requests_text = tk.Text(frame, bg=C["panel"], fg=C["ink"], relief=tk.FLAT, font=self.f_mono, wrap=tk.NONE)
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
        for text, color, cmd in (
            ("ENABLE TRADING", C["green"], lambda: self._set_trading(True)),
            ("DISABLE TRADING", C["amber"], lambda: self._set_trading(False)),
            ("CLEAR STOP", C["cyan"], self._clear_stop),
            ("DEPLOY MT4", C["violet"], self._deploy),
        ):
            tk.Button(
                row,
                text=text,
                command=cmd,
                bg=C["panel2"],
                fg=color,
                relief=tk.FLAT,
                highlightthickness=1,
                highlightbackground=color,
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
        for label, key, color in (
            ("UPTIME", "uptime", C["green"]),
            ("DATA FLOW", "flow", C["amber"]),
            ("CONNECTIONS", "conn", C["mint"]),
            ("SERVER TIME", "time", C["cyan"]),
            ("SYSTEM", "system", C["green"]),
        ):
            cell = tk.Frame(inner, bg=C["panel"])
            cell.pack(side=tk.LEFT, expand=True, fill=tk.X)
            tk.Label(cell, text=label, bg=C["panel"], fg=C["mute"], font=self.f_ui).pack(anchor="w", pady=(8, 0))
            tk.Label(cell, textvariable=self.foot_vars[key], bg=C["panel"], fg=color, font=self.f_ui_b).pack(anchor="w")

    # ── brain interactions ─────────────────────────────────────────────────
    def _on_brain_hover(self, point: dict | None) -> None:
        if point is None:
            self._selected_node.set("Hover a node · click to run its function")
            return
        st = self.brain._states.get(point["key"]) or self.brain._states.get(point["parent"])
        detail = getattr(st, "detail", "") if st else ""
        self._selected_node.set(f"{point['label']} · {detail} · {point['hint']}")

    def _on_brain_click(self, point: dict) -> None:
        action = point.get("action") or ""
        key = point.get("key") or ""
        label = point.get("label") or key
        st = self.brain._states.get(key) or self.brain._states.get(point.get("parent"))
        detail = getattr(st, "detail", "") if st else ""
        self._selected_node.set(f"ACTIVE {label} · {detail}")

        if action == "core_pulse":
            self._set_tray(
                f"CORE · {detail}",
                [
                    ("START LIVE", C["green"], self._start_live),
                    ("PAPER", C["cyan"], self._start_paper),
                    ("SUMMARY", C["violet"], self._show_core_summary),
                ],
            )
            if not self.engine.running and not (self._health and self._health.stop_present):
                # One-click recover when core is faulted
                pass
            return
        if action == "engine_control":
            buttons = []
            if self.engine.running:
                buttons.append(("STOP ENGINE", C["red"], self._confirm_stop))
            else:
                buttons.append(("START LIVE", C["green"], self._start_live))
                buttons.append(("PAPER", C["cyan"], self._start_paper))
            buttons.append(("SETTINGS", C["amber"], lambda: self._show_page("settings")))
            self._set_tray(f"ENGINE · {detail}", buttons)
            return
        if action == "trading_control":
            buttons = []
            if self._health and self._health.stop_present:
                buttons.append(("CLEAR STOP", C["cyan"], self._clear_stop))
            buttons.append(("ENABLE TRADE", C["green"], lambda: self._set_trading(True)))
            buttons.append(("DISABLE TRADE", C["amber"], lambda: self._set_trading(False)))
            self._set_tray(f"TRADE · {detail}", buttons)
            return
        if action == "risk_control":
            buttons = [("CLEAR STOP", C["cyan"], self._clear_stop), ("SETTINGS", C["amber"], lambda: self._show_page("settings"))]
            self._set_tray(f"RISK · {detail}", buttons)
            if self._health and self._health.stop_present:
                if messagebox.askyesno("RISK", "STOP_TRADING is armed. Clear it now?"):
                    self._clear_stop()
            return
        if action == "open_requests":
            self._set_tray(f"{label} · {detail}", [("OPEN REQUESTS", C["violet"], lambda: self._show_page("requests"))])
            self._show_page("requests")
            return
        if action == "trail_inspect":
            self._set_tray(
                f"TRAIL · {detail}",
                [
                    ("POSITIONS", C["mint"], lambda: self._show_page("requests")),
                    ("REQUESTS", C["violet"], lambda: self._show_page("requests")),
                ],
            )
            self._show_positions_popup()
            return
        if action == "open_accounts":
            self._focus_account = None
            self._set_tray(f"ACCOUNTS · {detail}", [("EDIT LOTS", C["cyan"], lambda: self._show_page("accounts"))])
            self._show_page("accounts")
            return
        if action == "edit_lot":
            acct = key.split(":", 1)[-1] if key.startswith("acct:") else None
            self._focus_account = acct
            self._set_tray(
                f"ACCOUNT {acct} · edit lot size",
                [("OPEN LOT EDITOR", C["cyan"], lambda: self._show_page("accounts"))],
            )
            self._show_page("accounts")
            return
        if action == "show_position":
            self._set_tray(f"POSITION · {detail}", [("REQUESTS", C["violet"], lambda: self._show_page("requests"))])
            messagebox.showinfo("Position", detail or key)
            return
        self._set_tray(f"{label} · {detail or 'ready'}", [("MAIN", C["cyan"], lambda: self._show_page("main"))])

    def _show_core_summary(self) -> None:
        h = self._health
        if h is None:
            return
        lines = [
            f"mode={h.mode} trading={h.trading_enabled} stop={h.stop_present}",
            f"engine={'UP' if self.engine.running else 'DOWN'} pid={self.engine.pid}",
            f"bridges={len(h.bridges)} symbol={h.symbol}",
        ]
        for b in h.bridges:
            lines.append(
                f"  {b.account_id} eq={b.equity:.2f} market={format_age(b.market_age_s)} conn={b.connected}"
            )
        messagebox.showinfo("CORE", "\n".join(lines))

    def _show_positions_popup(self) -> None:
        h = self._health
        if h is None:
            return
        rows = []
        for b in h.bridges:
            for p in b.positions:
                rows.append(f"{b.account_id} #{p.ticket} {p.symbol} {p.side} lot={p.lot} sl={p.stop_loss} pl={p.profit:.2f}")
        messagebox.showinfo("TRAIL / POSITIONS", "\n".join(rows) if rows else "No open positions")

    # ── engine / config actions ────────────────────────────────────────────
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
            self.refresh()
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
            self.refresh()
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
        mn, mx, _ = lot_bounds(self._cfg_data())
        if lot < mn or lot > mx:
            messagebox.showerror("Lot", f"Lot must be between {mn} and {mx}")
            return
        write_account_lot_override(self._rt(), account_id, lot)
        messagebox.showinfo("Lot", f"{account_id} → fixed_lot={lot:.2f}")
        self.refresh()

    def _reset_lot(self, account_id: str) -> None:
        clear_account_lot_override(self._rt(), account_id)
        self.refresh()

    def _rebuild_account_rows(self, health) -> None:
        cfg = self._cfg_data()
        rt = self._rt()
        default_lot = default_fixed_lot(cfg)
        accounts = list_known_accounts(health, rt)
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
            focused = self._focus_account == acct
            row = tk.Frame(self.accounts_host, bg=C["line"] if focused else C["panel2"])
            row.pack(fill=tk.X, pady=3)
            br = bridge_by.get(acct)
            bal = f"{br.balance:,.2f}" if br else "—"
            sym = br.symbol if br else "—"
            override = read_account_lot_override(rt, acct)
            effective = override if override is not None else default_lot
            source = "override" if override is not None else "config"
            bg = C["line"] if focused else C["panel2"]
            tk.Label(row, text=acct, bg=bg, fg=C["ink"], font=self.f_ui_b, width=16, anchor="w").pack(
                side=tk.LEFT, padx=6, pady=10
            )
            tk.Label(row, text=bal, bg=bg, fg=C["mint"], font=self.f_mono, width=12, anchor="w").pack(side=tk.LEFT, padx=6)
            tk.Label(row, text=sym, bg=bg, fg=C["cyan"], font=self.f_ui, width=12, anchor="w").pack(side=tk.LEFT, padx=6)
            var = tk.StringVar(value=f"{effective:.2f}")
            self._lot_vars[acct] = var
            tk.Entry(
                row,
                textvariable=var,
                bg=C["void"],
                fg=C["amber"],
                insertbackground=C["ink"],
                relief=tk.FLAT,
                width=8,
                font=self.f_mono,
                highlightthickness=1,
                highlightbackground=C["amber"] if focused else C["line"],
            ).pack(side=tk.LEFT, padx=6)
            tk.Label(
                row,
                text=source,
                bg=bg,
                fg=C["violet"] if source == "override" else C["mute"],
                font=self.f_ui,
                width=12,
                anchor="w",
            ).pack(side=tk.LEFT, padx=6)
            tk.Button(
                row, text="SAVE", command=lambda a=acct: self._save_lot(a), bg=C["panel"], fg=C["green"], relief=tk.FLAT, font=self.f_ui_b, padx=10, cursor="hand2"
            ).pack(side=tk.LEFT, padx=4)
            tk.Button(
                row, text="RESET", command=lambda a=acct: self._reset_lot(a), bg=C["panel"], fg=C["mute"], relief=tk.FLAT, font=self.f_ui_b, padx=8, cursor="hand2"
            ).pack(side=tk.LEFT, padx=2)

    def refresh(self) -> None:
        try:
            health = collect_health(self.config_path)
        except Exception as exc:  # noqa: BLE001
            self._selected_node.set(f"health error: {exc}")
            return
        self._health = health
        states = brain_node_states(health, engine_running=self.engine.running, engine_mode=self.engine.mode)
        self.brain.set_states(states)

        online = self.engine.running and not health.stop_present
        self.online_lbl.configure(
            text="ONLINE" if online else ("HALTED" if health.stop_present else "STANDBY"),
            fg=C["green"] if online else (C["red"] if health.stop_present else C["amber"]),
        )

        lines = []
        worst = "idle"
        for st in states:
            if st.key.startswith(("acct:", "pos:")):
                continue
            mark = {"ok": "●", "warn": "▲", "error": "✖", "idle": "○"}.get(st.level, "·")
            lines.append(f"{mark} {st.label:<6} {st.level.upper():<5}  {st.detail}")
            lines.append(f"    → {st.hint}")
            if st.level == "error":
                worst = "error"
            elif st.level == "warn" and worst != "error":
                worst = "warn"
            elif st.level == "ok" and worst == "idle":
                worst = "ok"
        # Account lines
        for st in states:
            if st.key.startswith("acct:"):
                mark = {"ok": "●", "warn": "▲", "error": "✖", "idle": "○"}.get(st.level, "·")
                lines.append(f"{mark} {st.label:<6} LOT     {st.detail}")
        self._set_text(self.node_list, "\n".join(lines))

        af = audit_file(self._cfg_data())
        rows = audit_activity(af, limit=12)
        tape_lines = [format_audit_line(r) for r in rows] or ["(no audit yet)"]
        self._set_text(self.tape, "\n".join(tape_lines))

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

        if self.engine.running and self.engine.started_at:
            self.foot_vars["uptime"].set(f"READY  {int(time.time() - self.engine.started_at)}s")
        else:
            self.foot_vars["uptime"].set("READY" if not health.stop_present else "STOPPED")
        fresh = any(b.market_age_s is not None and b.market_age_s <= 15 for b in health.bridges)
        self.foot_vars["flow"].set("STREAMING" if fresh else ("WAITING" if health.bridges else "IDLE"))
        self.foot_vars["conn"].set(
            "STABLE" if any(b.connected for b in health.bridges) else ("DEGRADED" if health.bridges else "NONE")
        )
        self.foot_vars["time"].set(time.strftime("%H:%M:%S"))
        self.foot_vars["system"].set("ONLINE" if online else ("FAULT" if worst == "error" else "STANDBY"))

    def _set_text(self, widget: tk.Text, text: str) -> None:
        widget.configure(state=tk.NORMAL)
        widget.delete("1.0", tk.END)
        widget.insert(tk.END, text)
        widget.configure(state=tk.DISABLED)

    def _motion_tick(self) -> None:
        self.brain.phase += 0.14
        if self._page == "main":
            self.brain.draw()
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
        self.engine.poll_exit()
        self.root.after(70, self._motion_tick)

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
