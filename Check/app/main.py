"""CHECK v5 desk — new architecture, new design. Per-account points risk."""

from __future__ import annotations

import contextlib
import os
import sys
import tkinter as tk
import tkinter.font as tkfont
from tkinter import messagebox, ttk

from app import paths

ROOT = paths.app_root()
os.chdir(ROOT)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import bridge, clients, settings as settings_mod  # noqa: E402
from app.engine import Engine  # noqa: E402

# Visual direction: graphite + signal coral + ice cyan (not purple / cream / broadsheet)
C = {
    "bg": "#0A0C10",
    "bg2": "#10141C",
    "panel": "#151A24",
    "line": "#2A3344",
    "ink": "#F2F4F7",
    "mute": "#8B95A8",
    "coral": "#FF4D2E",
    "ice": "#3DDCFF",
    "ok": "#5CFF9E",
    "warn": "#FFC14D",
    "stop": "#FF4D2E",
}


def _font(names: list[str], size: int, weight: str = "normal") -> tuple:
    fam = set(tkfont.families())
    for n in names:
        if n in fam:
            return (n, size, weight) if weight != "normal" else (n, size)
    return ("TkDefaultFont", size, weight) if weight != "normal" else ("TkDefaultFont", size)


class App:
    def __init__(self, root: tk.Tk) -> None:
        paths.ensure_layout()
        if not (ROOT / "config" / "settings.json").exists():
            settings_mod.save(settings_mod.load())

        self.root = root
        self.root.title("CHECK")
        self.root.geometry("1380x900")
        self.root.minsize(1100, 740)
        self.root.configure(bg=C["bg"])
        self.f_brand = _font(["Bahnschrift SemiBold", "Bahnschrift", "Segoe UI"], 42, "bold")
        self.f_sub = _font(["Bahnschrift", "Segoe UI"], 11)
        self.f_h = _font(["Bahnschrift", "Segoe UI"], 12, "bold")
        self.f_ui = _font(["Bahnschrift", "Segoe UI"], 10)
        self.f_mono = _font(["Cascadia Mono", "Consolas"], 9)

        self.engine = Engine(on_log=self._push_log)
        self._log_lines: list[str] = []
        self._gvars: dict[str, tk.StringVar] = {}
        self._page = "live"
        self._pulse = 0
        self.kpi: dict[str, tk.StringVar] = {}
        self.banner = tk.StringVar(value="")
        self.selected_cid: str | None = None

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
            "T.Treeview",
            background=C["panel"],
            foreground=C["ink"],
            fieldbackground=C["panel"],
            rowheight=28,
            font=self.f_mono,
            borderwidth=0,
        )
        st.configure("T.Treeview.Heading", background=C["bg2"], foreground=C["ice"], font=self.f_ui)
        st.map("T.Treeview", background=[("selected", C["line"])])

    def _btn(self, parent, text, color, cmd, **kw) -> tk.Button:
        return tk.Button(
            parent,
            text=text,
            command=cmd,
            bg=C["panel"],
            fg=color,
            activebackground=C["line"],
            activeforeground=color,
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=color,
            font=self.f_ui,
            padx=kw.get("padx", 14),
            pady=8,
            cursor="hand2",
        )

    def _build(self) -> None:
        # Hero brand strip — brand first
        hero = tk.Frame(self.root, bg=C["bg"])
        hero.pack(fill=tk.X, padx=20, pady=(18, 4))
        brand = tk.Frame(hero, bg=C["bg"])
        brand.pack(side=tk.LEFT)
        tk.Label(brand, text="CHECK", bg=C["bg"], fg=C["coral"], font=self.f_brand).pack(anchor="w")
        tk.Label(
            brand,
            text="v5 desk  ·  your MT4  ·  points risk per account",
            bg=C["bg"],
            fg=C["mute"],
            font=self.f_sub,
        ).pack(anchor="w")

        self.status = tk.Label(hero, text="IDLE", bg=C["bg"], fg=C["mute"], font=self.f_h)
        self.status.pack(side=tk.LEFT, padx=28)

        actions = tk.Frame(hero, bg=C["bg"])
        actions.pack(side=tk.RIGHT)
        self._btn(actions, "START LIVE", C["ok"], lambda: self._start("live")).pack(side=tk.LEFT, padx=4)
        self._btn(actions, "PAPER", C["ice"], lambda: self._start("paper")).pack(side=tk.LEFT, padx=4)
        self._btn(actions, "STOP", C["stop"], self._stop).pack(side=tk.LEFT, padx=4)

        # accent line
        self.accent = tk.Frame(self.root, bg=C["coral"], height=3)
        self.accent.pack(fill=tk.X, padx=20, pady=(8, 0))

        ban = tk.Frame(self.root, bg=C["bg2"])
        ban.pack(fill=tk.X, padx=20, pady=(10, 0))
        tk.Label(ban, textvariable=self.banner, bg=C["bg2"], fg=C["mute"], font=self.f_mono, anchor="w").pack(
            fill=tk.X, padx=12, pady=8
        )

        nav = tk.Frame(self.root, bg=C["bg"])
        nav.pack(fill=tk.X, padx=20, pady=(12, 0))
        self._nav: dict[str, tk.Button] = {}
        for key, label, col in (
            ("live", "LIVE", C["coral"]),
            ("accounts", "ACCOUNTS", C["ice"]),
            ("global", "GLOBAL", C["warn"]),
        ):
            b = self._btn(nav, label, col, lambda k=key: self._show(k))
            b.pack(side=tk.LEFT, padx=(0, 8))
            self._nav[key] = b

        self.body = tk.Frame(self.root, bg=C["bg"])
        self.body.pack(fill=tk.BOTH, expand=True, padx=20, pady=12)
        self.pages = {
            "live": self._page_live(self.body),
            "accounts": self._page_accounts(self.body),
            "global": self._page_global(self.body),
        }

        foot = tk.Frame(self.root, bg=C["panel"], height=36)
        foot.pack(fill=tk.X, side=tk.BOTTOM)
        self.foot = tk.Label(foot, text="", bg=C["panel"], fg=C["mute"], font=self.f_mono, anchor="w")
        self.foot.pack(fill=tk.X, padx=14, pady=8)

        self._show("live")

    def _page_live(self, parent) -> tk.Frame:
        f = tk.Frame(parent, bg=C["bg"])
        kpi = tk.Frame(f, bg=C["bg"])
        kpi.pack(fill=tk.X, pady=(0, 10))
        for key, title, col in (
            ("equity", "EQUITY", C["ok"]),
            ("pos", "OPEN", C["coral"]),
            ("bridges", "BRIDGES", C["ice"]),
            ("reason", "LAST", C["warn"]),
        ):
            self.kpi[key] = tk.StringVar(value="—")
            cell = tk.Frame(kpi, bg=C["panel"])
            cell.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
            tk.Label(cell, text=title, bg=C["panel"], fg=C["mute"], font=self.f_ui).pack(anchor="w", padx=12, pady=(10, 0))
            tk.Label(cell, textvariable=self.kpi[key], bg=C["panel"], fg=col, font=self.f_h).pack(anchor="w", padx=12, pady=(0, 12))

        grid = tk.Frame(f, bg=C["bg"])
        grid.pack(fill=tk.BOTH, expand=True)
        left = tk.Frame(grid, bg=C["bg"])
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        right = tk.Frame(grid, bg=C["bg"])
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(8, 0))

        tk.Label(left, text="BRIDGES", bg=C["bg"], fg=C["ice"], font=self.f_h).pack(anchor="w")
        self.tree = ttk.Treeview(
            left, columns=("account", "equity", "symbol", "market", "pos"), show="headings", style="T.Treeview", height=10
        )
        for c, t, w in (
            ("account", "ACCOUNT", 110),
            ("equity", "EQUITY", 90),
            ("symbol", "SYMBOL", 90),
            ("market", "AGE", 70),
            ("pos", "POS", 50),
        ):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, anchor="w")
        self.tree.pack(fill=tk.BOTH, expand=True, pady=4)

        tk.Label(right, text="POSITIONS", bg=C["bg"], fg=C["coral"], font=self.f_h).pack(anchor="w")
        self.pos = ttk.Treeview(
            right, columns=("account", "ticket", "side", "lot", "sl", "pl"), show="headings", style="T.Treeview", height=10
        )
        for c, t, w in (
            ("account", "ACC", 80),
            ("ticket", "TICKET", 80),
            ("side", "SIDE", 50),
            ("lot", "LOT", 50),
            ("sl", "SL", 90),
            ("pl", "P/L", 70),
        ):
            self.pos.heading(c, text=t)
            self.pos.column(c, width=w, anchor="w")
        self.pos.pack(fill=tk.BOTH, expand=True, pady=4)

        tk.Label(f, text="LOG", bg=C["bg"], fg=C["mute"], font=self.f_h).pack(anchor="w", pady=(10, 0))
        self.log = tk.Text(f, bg=C["panel"], fg=C["ink"], height=7, relief=tk.FLAT, font=self.f_mono, insertbackground=C["coral"])
        self.log.pack(fill=tk.X)
        self.log.configure(state=tk.DISABLED)
        return f

    def _page_accounts(self, parent) -> tk.Frame:
        f = tk.Frame(parent, bg=C["bg"])
        head = tk.Frame(f, bg=C["bg"])
        head.pack(fill=tk.X)
        tk.Label(head, text="ACCOUNTS", bg=C["bg"], fg=C["ice"], font=self.f_h).pack(side=tk.LEFT)
        tk.Label(
            head,
            text="  SL / BE / TRAIL = POINTS you set per account  (no ATR)",
            bg=C["bg"],
            fg=C["mute"],
            font=self.f_ui,
        ).pack(side=tk.LEFT, padx=8)
        self._btn(head, "+ ADD", C["ok"], self._add_account).pack(side=tk.RIGHT)

        split = tk.Frame(f, bg=C["bg"])
        split.pack(fill=tk.BOTH, expand=True, pady=10)
        self.clients_host = tk.Frame(split, bg=C["bg"])
        self.clients_host.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.risk_panel = tk.Frame(split, bg=C["panel"], width=360)
        self.risk_panel.pack(side=tk.RIGHT, fill=tk.Y, padx=(12, 0))
        self.risk_panel.pack_propagate(False)
        tk.Label(self.risk_panel, text="ACCOUNT RISK", bg=C["panel"], fg=C["coral"], font=self.f_h).pack(
            anchor="w", padx=14, pady=(14, 4)
        )
        tk.Label(
            self.risk_panel,
            text="Edit points for the selected account",
            bg=C["panel"],
            fg=C["mute"],
            font=self.f_ui,
        ).pack(anchor="w", padx=14)
        self._rvars: dict[str, tk.StringVar] = {}
        fields = (
            ("lot", "LOT"),
            ("sl_points", "SL POINTS"),
            ("be_start_points", "BE START POINTS"),
            ("be_offset_points", "BE OFFSET POINTS"),
            ("trail_start_points", "TRAIL START POINTS"),
            ("trail_lock_points", "TRAIL LOCK POINTS"),
        )
        for key, label in fields:
            tk.Label(self.risk_panel, text=label, bg=C["panel"], fg=C["mute"], font=self.f_ui).pack(
                anchor="w", padx=14, pady=(10, 0)
            )
            var = tk.StringVar(value="")
            self._rvars[key] = var
            tk.Entry(
                self.risk_panel,
                textvariable=var,
                bg=C["bg"],
                fg=C["ink"],
                insertbackground=C["coral"],
                relief=tk.FLAT,
                font=self.f_mono,
            ).pack(fill=tk.X, padx=14, pady=4)
        self._btn(self.risk_panel, "SAVE ACCOUNT", C["ok"], self._save_risk).pack(padx=14, pady=16, anchor="w")
        self._btn(self.risk_panel, "LAUNCH MT4", C["ice"], self._launch_selected).pack(padx=14, pady=4, anchor="w")
        return f

    def _page_global(self, parent) -> tk.Frame:
        f = tk.Frame(parent, bg=C["bg"])
        tk.Label(f, text="GLOBAL  (strategies only — risk is per account)", bg=C["bg"], fg=C["warn"], font=self.f_h).pack(
            anchor="w"
        )
        form = tk.Frame(f, bg=C["panel"])
        form.pack(fill=tk.BOTH, expand=True, pady=10)
        cfg = settings_mod.load()
        for i, (key, label) in enumerate(
            (("symbol", "SYMBOL"), ("cycle_sec", "CYCLE SEC"), ("magic", "MAGIC"))
        ):
            tk.Label(form, text=label, bg=C["panel"], fg=C["mute"], font=self.f_ui).grid(
                row=i, column=0, sticky="w", padx=14, pady=8
            )
            var = tk.StringVar(value=str(cfg.get(key, "")))
            self._gvars[key] = var
            tk.Entry(
                form, textvariable=var, bg=C["bg"], fg=C["ink"], insertbackground=C["ice"], relief=tk.FLAT, width=40, font=self.f_mono
            ).grid(row=i, column=1, sticky="w", padx=8, pady=8)
        self.trend_v = tk.BooleanVar(value=bool(cfg.get("trend", True)))
        self.bo_v = tk.BooleanVar(value=bool(cfg.get("breakout", True)))
        tk.Checkbutton(form, text="TREND", variable=self.trend_v, bg=C["panel"], fg=C["ink"], selectcolor=C["bg"]).grid(
            row=3, column=1, sticky="w"
        )
        tk.Checkbutton(form, text="BREAKOUT", variable=self.bo_v, bg=C["panel"], fg=C["ink"], selectcolor=C["bg"]).grid(
            row=4, column=1, sticky="w"
        )
        self._btn(form, "SAVE GLOBAL", C["ok"], self._save_global).grid(row=5, column=1, sticky="w", pady=16)

        st = clients.setup_status()
        tip = (
            f"Template MT4: {'OK — ' + st['master'] if st['template_ok'] else 'MISSING — put MT4 in template\\ then SETUP.bat'}"
        )
        tk.Label(f, text=tip, bg=C["bg"], fg=C["mute"], font=self.f_mono, wraplength=900, justify="left").pack(
            anchor="w", pady=8
        )
        return f

    def _show(self, key: str) -> None:
        self._page = key
        for name, fr in self.pages.items():
            if name == key:
                fr.pack(fill=tk.BOTH, expand=True)
            else:
                fr.pack_forget()
        if key == "accounts":
            self._render_clients()
        self.refresh()

    def _push_log(self, line: str) -> None:
        self._log_lines.append(line)
        self._log_lines = self._log_lines[-200:]

    def _start(self, mode: str) -> None:
        st = clients.setup_status()
        if not st["template_ok"]:
            messagebox.showwarning("SETUP", "Put original MT4 in Check\\template\\ and run SETUP.bat first.")
            return
        if mode == "live" and not st["ready"]:
            if not messagebox.askyesno(
                "START LIVE",
                "No live bridge yet.\nLAUNCH account MT4 → attach CHECK on M1 → continue?",
            ):
                return
        self.engine.start(mode)
        self.refresh()

    def _stop(self) -> None:
        self.engine.stop()
        self.refresh()

    def _save_global(self) -> None:
        try:
            data = settings_mod.load()
            data["symbol"] = self._gvars["symbol"].get().strip() or "AUTO"
            data["cycle_sec"] = float(self._gvars["cycle_sec"].get().replace(",", ".") or 3)
            data["magic"] = int(float(self._gvars["magic"].get() or 50001))
            data["trend"] = bool(self.trend_v.get())
            data["breakout"] = bool(self.bo_v.get())
            settings_mod.save(data)
            messagebox.showinfo("GLOBAL", "Saved.")
            self.refresh()
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("GLOBAL", str(exc))

    def _add_account(self) -> None:
        win = tk.Toplevel(self.root)
        win.title("Add account")
        win.configure(bg=C["panel"])
        win.geometry("460x520")
        fields: dict[str, tk.StringVar] = {}
        defaults = {
            "label": "",
            "login": "",
            "password": "",
            "server": "",
            "lot": "0.02",
            "sl_points": "150",
            "be_start_points": "50",
            "be_offset_points": "5",
            "trail_start_points": "80",
            "trail_lock_points": "40",
        }
        labels = {
            "label": "Label",
            "login": "Login",
            "password": "Password",
            "server": "Server",
            "lot": "Lot",
            "sl_points": "SL points",
            "be_start_points": "BE start points",
            "be_offset_points": "BE offset points",
            "trail_start_points": "Trail start points",
            "trail_lock_points": "Trail lock points",
        }
        for key, label in labels.items():
            tk.Label(win, text=label, bg=C["panel"], fg=C["mute"]).pack(anchor="w", padx=14, pady=(6, 0))
            var = tk.StringVar(value=defaults[key])
            fields[key] = var
            show = "*" if key == "password" else ""
            tk.Entry(win, textvariable=var, show=show, bg=C["bg"], fg=C["ink"], relief=tk.FLAT).pack(fill=tk.X, padx=14)

        def go() -> None:
            try:
                c = clients.add(
                    login=fields["login"].get(),
                    password=fields["password"].get(),
                    server=fields["server"].get(),
                    label=fields["label"].get(),
                    lot=float(fields["lot"].get().replace(",", ".") or 0.02),
                    sl_points=float(fields["sl_points"].get().replace(",", ".") or 150),
                    be_start_points=float(fields["be_start_points"].get().replace(",", ".") or 50),
                    be_offset_points=float(fields["be_offset_points"].get().replace(",", ".") or 5),
                    trail_start_points=float(fields["trail_start_points"].get().replace(",", ".") or 80),
                    trail_lock_points=float(fields["trail_lock_points"].get().replace(",", ".") or 40),
                )
                win.destroy()
                messagebox.showinfo(
                    "Account",
                    f"Created {c['id']}\nMT4 clone: {c.get('mt4_dir')}\n\nLAUNCH → attach CHECK on M1 → START LIVE",
                )
                self.selected_cid = c["id"]
                self._render_clients()
                self._load_risk(c["id"])
                self.refresh()
            except Exception as exc:  # noqa: BLE001
                messagebox.showerror("Add", str(exc))

        self._btn(win, "CREATE + CLONE MT4", C["ok"], go).pack(pady=14)

    def _render_clients(self) -> None:
        for w in self.clients_host.winfo_children():
            w.destroy()
        rows = clients.list_clients()
        if not rows:
            tk.Label(
                self.clients_host,
                text="No accounts — + ADD  (clones your template MT4 per account)",
                bg=C["bg"],
                fg=C["mute"],
                font=self.f_ui,
            ).pack(pady=20)
            return
        for row in rows:
            cid = str(row.get("id"))
            full = clients.read(cid) or row
            line = tk.Frame(self.clients_host, bg=C["panel"])
            line.pack(fill=tk.X, pady=4)
            txt = (
                f"{cid}  |  {full.get('login')}  |  lot={full.get('lot')}  |  "
                f"SL={full.get('sl_points')}  BE={full.get('be_start_points')}  "
                f"TR={full.get('trail_start_points')}/{full.get('trail_lock_points')}"
            )
            tk.Label(line, text=txt, bg=C["panel"], fg=C["ink"], font=self.f_mono, anchor="w").pack(
                side=tk.LEFT, padx=10, pady=10, fill=tk.X, expand=True
            )
            self._btn(line, "EDIT", C["warn"], lambda c=cid: self._load_risk(c), padx=8).pack(side=tk.RIGHT, padx=3)
            self._btn(line, "LAUNCH", C["ice"], lambda c=cid: self._launch(c), padx=8).pack(side=tk.RIGHT, padx=3)
            self._btn(line, "DEL", C["stop"], lambda c=cid: self._delete(c), padx=8).pack(side=tk.RIGHT, padx=3)

    def _load_risk(self, cid: str) -> None:
        self.selected_cid = cid
        full = clients.read(cid)
        if not full:
            return
        for k, var in self._rvars.items():
            var.set(str(full.get(k, "")))
        self._show("accounts")

    def _save_risk(self) -> None:
        if not self.selected_cid:
            messagebox.showwarning("Risk", "Select an account (EDIT) first.")
            return
        try:
            clients.update_risk(
                self.selected_cid,
                lot=float(self._rvars["lot"].get().replace(",", ".")),
                sl_points=float(self._rvars["sl_points"].get().replace(",", ".")),
                be_start_points=float(self._rvars["be_start_points"].get().replace(",", ".")),
                be_offset_points=float(self._rvars["be_offset_points"].get().replace(",", ".")),
                trail_start_points=float(self._rvars["trail_start_points"].get().replace(",", ".")),
                trail_lock_points=float(self._rvars["trail_lock_points"].get().replace(",", ".")),
            )
            messagebox.showinfo("Risk", f"Saved points for {self.selected_cid}")
            self._render_clients()
            self.refresh()
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Risk", str(exc))

    def _launch_selected(self) -> None:
        if not self.selected_cid:
            messagebox.showwarning("MT4", "Select an account first.")
            return
        self._launch(self.selected_cid)

    def _launch(self, cid: str) -> None:
        ok, msg = clients.launch(cid)
        (messagebox.showinfo if ok else messagebox.showwarning)("MT4", msg)

    def _delete(self, cid: str) -> None:
        if messagebox.askyesno("Delete", f"Delete {cid} and its MT4 clone?"):
            clients.delete(cid)
            if self.selected_cid == cid:
                self.selected_cid = None
            self._render_clients()
            self.refresh()

    def _banner_text(self) -> str:
        st = clients.setup_status()
        bits = [
            f"[{'OK' if st['template_ok'] else '!!'}] template MT4",
            f"[{'OK' if st['clients'] else '  '}] accounts={st['clients']}",
            f"[{'OK' if st['live_bridges'] else '  '}] live bridges={st['live_bridges']}",
            f"[{'ON' if self.engine.running else 'off'}] engine",
        ]
        return "   ".join(bits)

    def refresh(self) -> None:
        if not getattr(self, "foot", None) or not getattr(self, "tree", None):
            return
        online = self.engine.running
        self.status.configure(
            text="LIVE" if online and self.engine.mode == "live" else ("PAPER" if online else "IDLE"),
            fg=C["ok"] if online else C["mute"],
        )
        self.banner.set(self._banner_text())

        for i in self.tree.get_children():
            self.tree.delete(i)
        for i in self.pos.get_children():
            self.pos.delete(i)

        bridges = clients.all_bridges()
        equity_sum = 0.0
        pos_n = 0
        for b in bridges:
            market = bridge.load_market(b) or {}
            status = bridge.load_status(b) or {}
            account = str(status.get("account") or market.get("account") or b.parent.parent.parent.name)
            eq = float(status.get("equity") or 0)
            equity_sum += eq
            positions = status.get("positions") or []
            pos_n += len(positions) if isinstance(positions, list) else 0
            age = bridge.age_s(b / "market" / "latest.json")
            age_s = f"{age:.0f}s" if age is not None else "—"
            self.tree.insert(
                "",
                tk.END,
                values=(account, f"{eq:.2f}" if eq else "—", market.get("symbol") or "—", age_s, len(positions) if isinstance(positions, list) else 0),
            )
            if isinstance(positions, list):
                for p in positions:
                    if not isinstance(p, dict):
                        continue
                    self.pos.insert(
                        "",
                        tk.END,
                        values=(
                            account,
                            p.get("ticket"),
                            p.get("side"),
                            p.get("lot"),
                            p.get("sl"),
                            p.get("profit"),
                        ),
                    )

        self.kpi["equity"].set(f"{equity_sum:.2f}" if bridges else "—")
        self.kpi["pos"].set(str(pos_n))
        self.kpi["bridges"].set(str(len(bridges)))
        self.kpi["reason"].set(self.engine.last_reason)

        if self._log_lines:
            self.log.configure(state=tk.NORMAL)
            self.log.delete("1.0", tk.END)
            self.log.insert(tk.END, "\n".join(self._log_lines[-80:]))
            self.log.configure(state=tk.DISABLED)

        st = clients.setup_status()
        self.foot.configure(
            text=f"root={ROOT}  |  master={st.get('master') or 'NONE'}  |  mode={self.engine.mode}"
        )

    def _tick(self) -> None:
        # subtle accent pulse
        self._pulse = (self._pulse + 1) % 2
        if getattr(self, "accent", None):
            self.accent.configure(bg=C["coral"] if self._pulse == 0 else C["ice"])
        with contextlib.suppress(Exception):
            self.refresh()
        self.root.after(900, self._tick)

    def _close(self) -> None:
        if self.engine.running:
            if not messagebox.askyesno("Quit", "Stop engine and quit?"):
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
