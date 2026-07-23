"""CHECK Platform v4 — single EXE trading desk."""

from __future__ import annotations

import contextlib
import os
import sys
import tkinter as tk
import tkinter.font as tkfont
from pathlib import Path
from tkinter import messagebox, ttk

# Ensure package root on path (source + frozen)
if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).resolve().parent
else:
    ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import bridge, clients, settings as settings_mod  # noqa: E402
from app.engine import Engine  # noqa: E402

C = {
    "bg": "#0B1210",
    "panel": "#15201C",
    "line": "#2A3C34",
    "ink": "#EAF2EE",
    "mute": "#7E9288",
    "brass": "#D4A84B",
    "ok": "#3DDC97",
    "sky": "#5BB8C8",
    "warn": "#E0A045",
    "stop": "#E85D4C",
}


def _font(names: list[str], size: int, weight: str = "normal") -> tuple:
    fam = set(tkfont.families())
    for n in names:
        if n in fam:
            return (n, size, weight) if weight != "normal" else (n, size)
    return ("TkDefaultFont", size, weight) if weight != "normal" else ("TkDefaultFont", size)


class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("CHECK · Platform v4")
        self.root.geometry("1280x820")
        self.root.minsize(1024, 700)
        self.root.configure(bg=C["bg"])
        self.f_brand = _font(["Bahnschrift", "Segoe UI"], 28, "bold")
        self.f_h = _font(["Bahnschrift", "Segoe UI"], 12, "bold")
        self.f_ui = _font(["Bahnschrift", "Segoe UI"], 10)
        self.f_mono = _font(["Cascadia Mono", "Consolas"], 9)

        (ROOT / "clients").mkdir(exist_ok=True)
        (ROOT / "runtime").mkdir(exist_ok=True)
        if not (ROOT / "config" / "settings.json").exists():
            settings_mod.save(settings_mod.load())

        self.engine = Engine(on_log=self._push_log)
        self._log_lines: list[str] = []
        self._vars: dict[str, tk.StringVar] = {}
        self._page = "floor"
        self._nav: dict[str, tk.Button] = {}

        self._style()
        self._build()
        self.refresh()
        self.root.after(1000, self._tick)
        self.root.protocol("WM_DELETE_WINDOW", self._close)

    def _style(self) -> None:
        st = ttk.Style()
        with contextlib.suppress(tk.TclError):
            st.theme_use("clam")
        st.configure("T.Treeview", background=C["panel"], foreground=C["ink"], fieldbackground=C["panel"], rowheight=26, font=self.f_mono)
        st.configure("T.Treeview.Heading", background=C["bg"], foreground=C["brass"], font=self.f_ui)
        st.map("T.Treeview", background=[("selected", C["line"])])

    def _btn(self, parent, text, color, cmd, **kw) -> tk.Button:
        return tk.Button(
            parent, text=text, command=cmd, bg=C["panel"], fg=color, activebackground=C["line"],
            activeforeground=color, relief=tk.FLAT, highlightthickness=1, highlightbackground=color,
            font=self.f_ui, padx=kw.get("padx", 12), pady=7, cursor="hand2",
        )

    def _build(self) -> None:
        top = tk.Frame(self.root, bg=C["bg"])
        top.pack(fill=tk.X, padx=16, pady=12)
        tk.Label(top, text="CHECK", bg=C["bg"], fg=C["brass"], font=self.f_brand).pack(side=tk.LEFT)
        tk.Label(top, text="  PLATFORM v4", bg=C["bg"], fg=C["ink"], font=self.f_brand).pack(side=tk.LEFT)
        self.status = tk.Label(top, text="OFFLINE", bg=C["bg"], fg=C["stop"], font=self.f_h)
        self.status.pack(side=tk.LEFT, padx=16)
        right = tk.Frame(top, bg=C["bg"])
        right.pack(side=tk.RIGHT)
        self._btn(right, "START LIVE", C["ok"], lambda: self._start("live")).pack(side=tk.LEFT, padx=3)
        self._btn(right, "PAPER", C["sky"], lambda: self._start("paper")).pack(side=tk.LEFT, padx=3)
        self._btn(right, "DEPLOY MT4", C["brass"], self._deploy_mt4).pack(side=tk.LEFT, padx=3)
        self._btn(right, "STOP", C["stop"], self._stop).pack(side=tk.LEFT, padx=3)

        nav = tk.Frame(self.root, bg=C["panel"])
        nav.pack(fill=tk.X)
        for key, label, col in (("floor", "FLOOR", C["brass"]), ("accounts", "ACCOUNTS", C["sky"]), ("settings", "SETTINGS", C["warn"])):
            b = self._btn(nav, label, col, lambda k=key: self._show(k))
            b.pack(side=tk.LEFT, padx=6, pady=8)
            self._nav[key] = b

        self.body = tk.Frame(self.root, bg=C["bg"])
        self.body.pack(fill=tk.BOTH, expand=True, padx=12, pady=8)
        self.pages = {
            "floor": self._page_floor(self.body),
            "accounts": self._page_accounts(self.body),
            "settings": self._page_settings(self.body),
        }

        # Footer BEFORE first _show/refresh — otherwise AttributeError: no 'foot'
        foot = tk.Frame(self.root, bg=C["panel"], height=36)
        foot.pack(fill=tk.X, side=tk.BOTTOM)
        self.foot = tk.Label(foot, text="", bg=C["panel"], fg=C["mute"], font=self.f_mono, anchor="w")
        self.foot.pack(fill=tk.X, padx=12, pady=8)

        self._show("floor")

    def _page_floor(self, parent) -> tk.Frame:
        f = tk.Frame(parent, bg=C["bg"])
        kpi = tk.Frame(f, bg=C["bg"])
        kpi.pack(fill=tk.X, pady=(0, 8))
        self.kpi = {}
        for key, title, col in (
            ("equity", "EQUITY", C["ok"]),
            ("pos", "POSITIONS", C["brass"]),
            ("bridges", "BRIDGES", C["sky"]),
            ("reason", "LAST", C["warn"]),
        ):
            self.kpi[key] = tk.StringVar(value="—")
            cell = tk.Frame(kpi, bg=C["panel"], highlightthickness=1, highlightbackground=C["line"])
            cell.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=3)
            tk.Label(cell, text=title, bg=C["panel"], fg=C["mute"], font=self.f_ui).pack(anchor="w", padx=10, pady=(6, 0))
            tk.Label(cell, textvariable=self.kpi[key], bg=C["panel"], fg=col, font=self.f_h).pack(anchor="w", padx=10, pady=(0, 8))

        tk.Label(f, text="ACCOUNTS / BRIDGES", bg=C["bg"], fg=C["brass"], font=self.f_h).pack(anchor="w")
        self.tree = ttk.Treeview(
            f, columns=("account", "equity", "symbol", "market", "pos", "conn"), show="headings", style="T.Treeview", height=8
        )
        for c, t, w in (
            ("account", "ACCOUNT", 100), ("equity", "EQUITY", 90), ("symbol", "SYMBOL", 100),
            ("market", "MARKET", 80), ("pos", "POS", 50), ("conn", "CONN", 60),
        ):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, anchor="w")
        self.tree.pack(fill=tk.BOTH, expand=True, pady=4)

        tk.Label(f, text="POSITIONS", bg=C["bg"], fg=C["ok"], font=self.f_h).pack(anchor="w", pady=(8, 0))
        self.pos = ttk.Treeview(
            f, columns=("account", "ticket", "side", "lot", "open", "sl", "pl"), show="headings", style="T.Treeview", height=6
        )
        for c, t, w in (
            ("account", "ACCOUNT", 90), ("ticket", "TICKET", 80), ("side", "SIDE", 50),
            ("lot", "LOT", 50), ("open", "OPEN", 90), ("sl", "SL", 90), ("pl", "P/L", 70),
        ):
            self.pos.heading(c, text=t)
            self.pos.column(c, width=w, anchor="w")
        self.pos.pack(fill=tk.BOTH, expand=True, pady=4)

        tk.Label(f, text="ENGINE LOG", bg=C["bg"], fg=C["mute"], font=self.f_h).pack(anchor="w", pady=(8, 0))
        self.log = tk.Text(f, bg=C["panel"], fg=C["ink"], height=6, relief=tk.FLAT, font=self.f_mono)
        self.log.pack(fill=tk.X)
        self.log.configure(state=tk.DISABLED)
        return f

    def _page_accounts(self, parent) -> tk.Frame:
        f = tk.Frame(parent, bg=C["bg"])
        head = tk.Frame(f, bg=C["bg"])
        head.pack(fill=tk.X)
        tk.Label(head, text="CLIENTS", bg=C["bg"], fg=C["sky"], font=self.f_h).pack(side=tk.LEFT)
        self._btn(head, "+ ADD ACCOUNT", C["ok"], self._add_account).pack(side=tk.RIGHT)
        self.clients_host = tk.Frame(f, bg=C["bg"])
        self.clients_host.pack(fill=tk.BOTH, expand=True, pady=8)
        return f

    def _page_settings(self, parent) -> tk.Frame:
        f = tk.Frame(parent, bg=C["bg"])
        tk.Label(f, text="SETTINGS (saved into EXE config)", bg=C["bg"], fg=C["brass"], font=self.f_h).pack(anchor="w")
        form = tk.Frame(f, bg=C["panel"])
        form.pack(fill=tk.BOTH, expand=True, pady=8)
        cfg = settings_mod.load()
        fields = (
            ("lot", "LOT"), ("sl_atr", "SL ATR ×"), ("be_start_atr", "BE START ATR ×"),
            ("be_offset_atr", "BE OFFSET ATR ×"), ("trail_start_atr", "TRAIL START ATR ×"),
            ("trail_lock_atr", "TRAIL LOCK ATR ×"), ("symbol", "SYMBOL"),
            ("mt4_exe", "MT4 terminal.exe"), ("cycle_sec", "CYCLE SEC"), ("magic", "MAGIC"),
        )
        for i, (key, label) in enumerate(fields):
            tk.Label(form, text=label, bg=C["panel"], fg=C["mute"], font=self.f_ui).grid(row=i, column=0, sticky="w", padx=12, pady=5)
            var = tk.StringVar(value=str(cfg.get(key, "")))
            self._vars[key] = var
            tk.Entry(form, textvariable=var, bg=C["bg"], fg=C["ink"], insertbackground=C["brass"], relief=tk.FLAT, width=48, font=self.f_mono).grid(
                row=i, column=1, sticky="w", padx=8, pady=5
            )
        self.trend_v = tk.BooleanVar(value=bool(cfg.get("trend", True)))
        self.bo_v = tk.BooleanVar(value=bool(cfg.get("breakout", True)))
        self.force_v = tk.BooleanVar(value=bool(cfg.get("force_idle", True)))
        row = len(fields)
        tk.Checkbutton(form, text="TREND", variable=self.trend_v, bg=C["panel"], fg=C["ink"], selectcolor=C["bg"]).grid(row=row, column=1, sticky="w")
        tk.Checkbutton(form, text="BREAKOUT", variable=self.bo_v, bg=C["panel"], fg=C["ink"], selectcolor=C["bg"]).grid(row=row + 1, column=1, sticky="w")
        tk.Checkbutton(form, text="FORCE IDLE", variable=self.force_v, bg=C["panel"], fg=C["ink"], selectcolor=C["bg"]).grid(row=row + 2, column=1, sticky="w")
        self._btn(form, "SAVE SETTINGS", C["ok"], self._save_settings).grid(row=row + 3, column=1, sticky="w", pady=12)
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
        self.engine.start(mode)
        self.refresh()

    def _stop(self) -> None:
        self.engine.stop()
        self.refresh()

    def _save_settings(self) -> None:
        try:
            data = settings_mod.load()
            for k, var in self._vars.items():
                raw = var.get().strip()
                if k in {"lot", "sl_atr", "be_start_atr", "be_offset_atr", "trail_start_atr", "trail_lock_atr", "cycle_sec"}:
                    data[k] = float(raw.replace(",", "."))
                elif k == "magic":
                    data[k] = int(float(raw))
                else:
                    data[k] = raw
            data["trend"] = bool(self.trend_v.get())
            data["breakout"] = bool(self.bo_v.get())
            data["force_idle"] = bool(self.force_v.get())
            settings_mod.save(data)
            messagebox.showinfo("Settings", "Saved.")
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Settings", str(exc))

    def _add_account(self) -> None:
        win = tk.Toplevel(self.root)
        win.title("Add account")
        win.configure(bg=C["panel"])
        win.geometry("420x300")
        fields = {}
        for key, label, show in (
            ("label", "Label", ""),
            ("login", "Login", ""),
            ("password", "Password", "*"),
            ("server", "Server", ""),
            ("lot", "Lot", ""),
        ):
            tk.Label(win, text=label, bg=C["panel"], fg=C["mute"]).pack(anchor="w", padx=14, pady=(8, 0))
            var = tk.StringVar(value="0.02" if key == "lot" else "")
            fields[key] = var
            tk.Entry(win, textvariable=var, show=show, bg=C["bg"], fg=C["ink"], relief=tk.FLAT).pack(fill=tk.X, padx=14)

        def go() -> None:
            try:
                cfg = settings_mod.load()
                c = clients.add(
                    login=fields["login"].get(),
                    password=fields["password"].get(),
                    server=fields["server"].get(),
                    label=fields["label"].get(),
                    lot=float(fields["lot"].get().replace(",", ".") or 0.02),
                    mt4_exe=str(cfg.get("mt4_exe") or ""),
                )
                win.destroy()
                messagebox.showinfo(
                    "Client",
                    f"Created {c['id']}\nBridgePath → see BRIDGE.txt\nThen LAUNCH MT4 + attach CHECK.mq4 on M1",
                )
                self._render_clients()
            except Exception as exc:  # noqa: BLE001
                messagebox.showerror("Add", str(exc))

        self._btn(win, "CREATE", C["ok"], go).pack(pady=14)

    def _render_clients(self) -> None:
        for w in self.clients_host.winfo_children():
            w.destroy()
        rows = clients.list_clients()
        if not rows:
            tk.Label(self.clients_host, text="No clients — press + ADD ACCOUNT", bg=C["bg"], fg=C["mute"], font=self.f_ui).pack(pady=20)
            return
        for row in rows:
            cid = str(row.get("id"))
            full = clients.read(cid) or row
            line = tk.Frame(self.clients_host, bg=C["panel"])
            line.pack(fill=tk.X, pady=3)
            tk.Label(
                line,
                text=f"{cid}  |  {full.get('login')}  |  {full.get('server')}  |  lot={full.get('lot', '—')}",
                bg=C["panel"], fg=C["ink"], font=self.f_mono, anchor="w",
            ).pack(side=tk.LEFT, padx=10, pady=8)
            self._btn(line, "LAUNCH MT4", C["ok"], lambda c=cid: self._launch(c), padx=8).pack(side=tk.RIGHT, padx=4)
            self._btn(line, "DELETE", C["stop"], lambda c=cid: self._delete(c), padx=8).pack(side=tk.RIGHT, padx=4)

    def _launch(self, cid: str) -> None:
        ok, msg = clients.launch(cid)
        (messagebox.showinfo if ok else messagebox.showwarning)("MT4", msg)

    def _delete(self, cid: str) -> None:
        if messagebox.askyesno("Delete", f"Delete client {cid}?"):
            clients.delete(cid)
            self._render_clients()

    def refresh(self) -> None:
        if not getattr(self, "foot", None) or not getattr(self, "tree", None):
            return
        online = self.engine.running
        self.status.configure(text="ONLINE" if online else "OFFLINE", fg=C["ok"] if online else C["stop"])
        bridges = clients.all_bridges()
        eq = 0.0
        npos = 0
        self.tree.delete(*self.tree.get_children())
        self.pos.delete(*self.pos.get_children())
        for b in bridges:
            st = bridge.load_status(b) or {}
            mk = bridge.load_market(b) or {}
            acct = str(st.get("account") or mk.get("account") or b.parent.name)
            equity = float(st.get("equity") or 0)
            eq += equity
            positions = st.get("positions") or []
            npos += len(positions)
            age = bridge.age_s(b / "market" / "latest.json")
            age_s = f"{age:.0f}s" if age is not None else "—"
            conn = "YES" if st.get("connected") else ("—" if not st else "NO")
            self.tree.insert("", tk.END, values=(acct, f"{equity:.2f}", mk.get("symbol") or "—", age_s, len(positions), conn))
            for p in positions:
                if not isinstance(p, dict):
                    continue
                self.pos.insert(
                    "",
                    tk.END,
                    values=(
                        acct, p.get("ticket"), p.get("side"), p.get("lot"),
                        p.get("open"), p.get("sl"), p.get("profit"),
                    ),
                )
        if not bridges:
            self.tree.insert("", tk.END, values=("(no clients)", "0", "—", "—", "0", "—"))
        if npos == 0:
            self.pos.insert("", tk.END, values=("(flat)", "—", "—", "—", "—", "—", "—"))

        self.kpi["equity"].set(f"{eq:.2f}")
        self.kpi["pos"].set(str(npos))
        self.kpi["bridges"].set(str(len(bridges)))
        self.kpi["reason"].set(self.engine.last_reason)

        self.log.configure(state=tk.NORMAL)
        self.log.delete("1.0", tk.END)
        self.log.insert("1.0", "\n".join(self._log_lines[-40:]))
        self.log.configure(state=tk.DISABLED)
        self.foot.configure(
            text=f"root={ROOT}  |  mode={self.engine.mode}  |  clients={len(clients.list_clients())}  |  reason={self.engine.last_reason}"
        )

    def _tick(self) -> None:
        with contextlib.suppress(Exception):
            self.refresh()
        self.root.after(1000, self._tick)

    def _close(self) -> None:
        if self.engine.running:
            if not messagebox.askyesno("Quit", "Stop engine and quit?"):
                return
            self.engine.stop()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    with contextlib.suppress(tk.TclError):
        root.state("zoomed")
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
