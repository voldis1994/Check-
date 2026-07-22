"""CHECK SYSTEM v3 desktop control panel (Tkinter, no browser)."""

from __future__ import annotations

import contextlib
import queue
import sys
import threading
import time
import tkinter as tk
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
    audit_file,
    clear_stop,
    collect_health,
    format_age,
    format_audit_line,
    load_config_json,
    resolve_config,
    run_deploy_mt4,
    runtime_dir,
    validate_live_config,
    write_stop,
)

# Cool steel ops console — not purple, not cream/terracotta, not dark-mode chrome.
COLORS = {
    "bg": "#E7EEF3",
    "panel": "#F8FBFD",
    "ink": "#152033",
    "muted": "#5B6B7C",
    "line": "#C5D2DE",
    "go": "#0F6E56",
    "go_bg": "#D8F3E7",
    "warn": "#B54708",
    "warn_bg": "#FDEAD7",
    "stop": "#B42318",
    "stop_bg": "#FEE4E2",
    "idle": "#344054",
    "log_bg": "#101828",
    "log_fg": "#E4E7EC",
}


class DashboardApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("CHECK SYSTEM")
        self.root.geometry("1100x720")
        self.root.minsize(900, 600)
        self.root.configure(bg=COLORS["bg"])

        self.config_path = resolve_config()
        self.engine = EngineProcess()
        self.log_queue: queue.Queue[str] = queue.Queue()
        self._reader_thread: threading.Thread | None = None
        self._audit_offset = 0
        self._stopping = False
        self._stale_warned = False

        self._build_style()
        self._build_ui()
        self._tail_audit_init()
        self.refresh_status()
        self.root.after(400, self._tick)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_style(self) -> None:
        style = ttk.Style(self.root)
        with contextlib.suppress(tk.TclError):
            style.theme_use("clam")
        style.configure("Root.TFrame", background=COLORS["bg"])
        style.configure("Panel.TFrame", background=COLORS["panel"])
        style.configure(
            "Title.TLabel",
            background=COLORS["bg"],
            foreground=COLORS["ink"],
            font=("Segoe UI Semibold", 22),
        )
        style.configure("Sub.TLabel", background=COLORS["bg"], foreground=COLORS["muted"], font=("Segoe UI", 11))
        style.configure(
            "PanelTitle.TLabel",
            background=COLORS["panel"],
            foreground=COLORS["ink"],
            font=("Segoe UI Semibold", 12),
        )
        style.configure("Value.TLabel", background=COLORS["panel"], foreground=COLORS["ink"], font=("Consolas", 11))
        style.configure("Muted.TLabel", background=COLORS["panel"], foreground=COLORS["muted"], font=("Segoe UI", 10))
        style.configure("Go.TButton", font=("Segoe UI Semibold", 11), padding=(14, 8))
        style.configure("Stop.TButton", font=("Segoe UI Semibold", 11), padding=(14, 8))
        style.configure("Ghost.TButton", font=("Segoe UI", 10), padding=(10, 6))

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, style="Root.TFrame", padding=18)
        outer.pack(fill=tk.BOTH, expand=True)

        header = ttk.Frame(outer, style="Root.TFrame")
        header.pack(fill=tk.X)
        ttk.Label(header, text="CHECK SYSTEM", style="Title.TLabel").pack(anchor=tk.W)
        ttk.Label(
            header,
            text="Desktop vadības panelis — palaiž motoru, rāda ciklus, aptur tirdzniecību.",
            style="Sub.TLabel",
        ).pack(anchor=tk.W, pady=(2, 12))

        controls = ttk.Frame(outer, style="Root.TFrame")
        controls.pack(fill=tk.X, pady=(0, 12))

        self.btn_paper = ttk.Button(controls, text="Start Paper", style="Go.TButton", command=self.start_paper)
        self.btn_paper.pack(side=tk.LEFT, padx=(0, 8))
        self.btn_live = ttk.Button(controls, text="Start Live", style="Go.TButton", command=self.start_live)
        self.btn_live.pack(side=tk.LEFT, padx=(0, 8))
        self.btn_stop = ttk.Button(controls, text="Stop", style="Stop.TButton", command=self.stop_engine)
        self.btn_stop.pack(side=tk.LEFT, padx=(0, 8))
        self.btn_deploy = ttk.Button(controls, text="Deploy MT4", style="Ghost.TButton", command=self.deploy_mt4)
        self.btn_deploy.pack(side=tk.LEFT, padx=(0, 8))
        self.btn_refresh = ttk.Button(controls, text="Refresh", style="Ghost.TButton", command=self.refresh_status)
        self.btn_refresh.pack(side=tk.LEFT)

        self.state_banner = tk.Label(
            outer,
            text="STOPPED",
            bg=COLORS["stop_bg"],
            fg=COLORS["stop"],
            font=("Segoe UI Semibold", 12),
            padx=12,
            pady=8,
            anchor="w",
        )
        self.state_banner.pack(fill=tk.X, pady=(0, 12))

        body = ttk.Frame(outer, style="Root.TFrame")
        body.pack(fill=tk.BOTH, expand=True)

        left = tk.Frame(body, bg=COLORS["panel"], highlightbackground=COLORS["line"], highlightthickness=1)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 12))
        left.configure(width=360)
        left.pack_propagate(False)

        ttk.Label(left, text="Status", style="PanelTitle.TLabel").pack(anchor=tk.W, padx=14, pady=(12, 8))
        self.status_vars: dict[str, tk.StringVar] = {}
        for key, label in (
            ("engine", "Engine"),
            ("mode", "Mode"),
            ("trading", "Trading enabled"),
            ("symbol", "Symbol"),
            ("config", "Config"),
            ("stop", "STOP_TRADING"),
            ("bridge", "Bridge"),
            ("market", "Market"),
            ("status", "Status JSON"),
            ("decision", "Last decision"),
            ("reason", "Last reason"),
            ("regime", "Regime"),
            ("strategy", "Strategy"),
        ):
            row = ttk.Frame(left, style="Panel.TFrame")
            row.pack(fill=tk.X, padx=14, pady=2)
            ttk.Label(row, text=label, style="Muted.TLabel", width=16).pack(side=tk.LEFT)
            var = tk.StringVar(value="-")
            self.status_vars[key] = var
            ttk.Label(row, textvariable=var, style="Value.TLabel", wraplength=200).pack(side=tk.LEFT, fill=tk.X)

        right = tk.Frame(body, bg=COLORS["panel"], highlightbackground=COLORS["line"], highlightthickness=1)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ttk.Label(right, text="Activity", style="PanelTitle.TLabel").pack(anchor=tk.W, padx=14, pady=(12, 6))
        log_frame = tk.Frame(right, bg=COLORS["panel"])
        log_frame.pack(fill=tk.BOTH, expand=True, padx=14, pady=(0, 14))
        self.activity = tk.Text(
            log_frame,
            wrap=tk.NONE,
            bg=COLORS["log_bg"],
            fg=COLORS["log_fg"],
            insertbackground=COLORS["log_fg"],
            font=("Consolas", 10),
            relief=tk.FLAT,
            padx=10,
            pady=10,
        )
        yscroll = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.activity.yview)
        self.activity.configure(yscrollcommand=yscroll.set, state=tk.DISABLED)
        self.activity.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        yscroll.pack(side=tk.RIGHT, fill=tk.Y)

        footer = ttk.Frame(outer, style="Root.TFrame")
        footer.pack(fill=tk.X, pady=(10, 0))
        ttk.Label(
            footer,
            text="Live: config jābūt mode=live un trading_enabled=true. Stop uzraksta STOP_TRADING un aptur procesu.",
            style="Sub.TLabel",
        ).pack(anchor=tk.W)

    def _append_activity(self, line: str) -> None:
        self.activity.configure(state=tk.NORMAL)
        self.activity.insert(tk.END, line.rstrip() + "\n")
        # Keep last ~2000 lines
        total = int(float(self.activity.index("end-1c").split(".")[0]))
        if total > 2000:
            self.activity.delete("1.0", f"{total - 2000}.0")
        self.activity.see(tk.END)
        self.activity.configure(state=tk.DISABLED)

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
                import json

                entry = json.loads(raw)
            except Exception:  # noqa: BLE001
                self._append_activity(f"AUDIT  {raw[:240]}")
                continue
            if isinstance(entry, dict):
                self._append_activity("CYCLE  " + format_audit_line(entry))

    def _start_reader(self) -> None:
        if self.engine.proc is None or self.engine.proc.stdout is None:
            return

        def _feed() -> None:
            assert self.engine.proc is not None
            assert self.engine.proc.stdout is not None
            for line in self.engine.proc.stdout:
                self.log_queue.put(line.rstrip("\n"))
            code = self.engine.proc.poll()
            self.log_queue.put(f"[engine exited code={code}]")

        self._reader_thread = threading.Thread(target=_feed, daemon=True)
        self._reader_thread.start()

    def _drain_logs(self) -> None:
        while True:
            try:
                line = self.log_queue.get_nowait()
            except queue.Empty:
                break
            self._append_activity("ENGINE " + line)

    def refresh_status(self) -> None:
        try:
            self.config_path = resolve_config(self.config_path)
            health = collect_health(self.config_path)
        except Exception as exc:  # noqa: BLE001
            self.status_vars["engine"].set(f"error: {exc}")
            return

        running = self.engine.running
        pid = self.engine.pid
        engine_mode = self.engine.mode or health.mode
        ages = [b.market_age_s for b in health.bridges if b.market_age_s is not None]
        stale = bool(ages) and all(a > 30 for a in ages)
        partial_stale = bool(ages) and any(a > 30 for a in ages) and not stale
        n_accounts = len(health.bridges)

        if running and stale:
            self.status_vars["engine"].set(f"RUNNING pid={pid} ({engine_mode}) — ALL BRIDGES STALE")
            self.state_banner.configure(
                text="RUNNING — ALL BRIDGES STALE (pārbaudi abus MT4 EA)",
                bg=COLORS["warn_bg"],
                fg=COLORS["warn"],
            )
        elif running and partial_stale:
            self.status_vars["engine"].set(f"RUNNING pid={pid} ({engine_mode}) — {n_accounts} accounts")
            self.state_banner.configure(
                text=f"RUNNING — {engine_mode.upper()} · {n_accounts} accounts (daži STALE)",
                bg=COLORS["warn_bg"],
                fg=COLORS["warn"],
            )
        elif running:
            self.status_vars["engine"].set(f"RUNNING pid={pid} ({engine_mode}) — {n_accounts} accounts")
            self.state_banner.configure(
                text=f"RUNNING — {engine_mode.upper()} · {n_accounts} accounts",
                bg=COLORS["go_bg"] if engine_mode == "paper" else COLORS["warn_bg"],
                fg=COLORS["go"] if engine_mode == "paper" else COLORS["warn"],
            )
        else:
            self.status_vars["engine"].set("STOPPED")
            if health.stop_present:
                self.state_banner.configure(
                    text="STOPPED — STOP_TRADING present",
                    bg=COLORS["stop_bg"],
                    fg=COLORS["stop"],
                )
            else:
                self.state_banner.configure(text="STOPPED", bg=COLORS["stop_bg"], fg=COLORS["stop"])

        self.status_vars["mode"].set(health.mode)
        self.status_vars["trading"].set("true" if health.trading_enabled else "false")
        self.status_vars["symbol"].set(health.symbol)
        try:
            config_display = str(self.config_path.relative_to(ROOT))
        except ValueError:
            config_display = str(self.config_path)
        self.status_vars["config"].set(config_display)
        self.status_vars["stop"].set("PRESENT" if health.stop_present else "absent")

        if health.bridges:
            accounts = ", ".join(
                f"{b.account_id}:{format_age(b.market_age_s)}" for b in health.bridges
            )
            self.status_vars["bridge"].set(f"{len(health.bridges)} accounts · {accounts}")
            # Show freshest bridge detail in market/status rows
            bridge = sorted(
                health.bridges,
                key=lambda b: b.market_age_s if b.market_age_s is not None else 1e9,
            )[0]
            self.status_vars["market"].set(
                f"{format_age(bridge.market_age_s)} acct={bridge.account_id} ({bridge.market_file or '-'})"
            )
            self.status_vars["status"].set(
                f"{format_age(bridge.status_age_s)} acct={bridge.account_id} ({bridge.status_file or '-'})"
            )
            if stale and not self._stale_warned:
                self._stale_warned = True
                self._append_activity(
                    "WARN   Bridge STALE — redeploy MT4 EA, Allow DLL imports, check chart comment EXPORT OK"
                )
            if not stale:
                self._stale_warned = False
        else:
            self.status_vars["bridge"].set("none discovered")
            self.status_vars["market"].set("missing")
            self.status_vars["status"].set("missing")

        audit = health.last_audit or {}
        self.status_vars["decision"].set(str(audit.get("decision") or "-"))
        self.status_vars["reason"].set(str(audit.get("reason_code") or audit.get("human_readable_reason") or "-"))
        self.status_vars["regime"].set(str(audit.get("market_regime") or "-"))
        self.status_vars["strategy"].set(str(audit.get("selected_strategy") or "-"))

        self.btn_paper.configure(state=tk.DISABLED if running else tk.NORMAL)
        self.btn_live.configure(state=tk.DISABLED if running else tk.NORMAL)
        self.btn_stop.configure(state=tk.NORMAL if running or health.stop_present else tk.NORMAL)

    def start_paper(self) -> None:
        self._start_mode("paper")

    def start_live(self) -> None:
        ok, detail = validate_live_config(self.config_path)
        if not ok:
            messagebox.showerror(
                "Live config invalid",
                "Live start blocked.\n\n"
                "Set in config/system.json:\n"
                '  runtime.mode = "live"\n'
                "  runtime.trading_enabled = true\n\n"
                f"{detail}",
            )
            self._append_activity(f"ERROR  live validation failed: {detail}")
            return
        if not messagebox.askyesno(
            "Confirm LIVE",
            "Start LIVE trading?\n\n"
            "Confirm MT4 AutoTrading ON, DLL imports allowed,\n"
            "EA attached to M1, and risk settings reviewed.",
        ):
            return
        self._start_mode("live")

    def _start_mode(self, mode: str) -> None:
        try:
            cfg = load_config_json(self.config_path)
            rt = runtime_dir(cfg)
            cleared = clear_stop(rt)
            self.engine.start(mode=mode, config_path=self.config_path)
            self._start_reader()
            msg = f"Started {mode} with {self.config_path.name}"
            if cleared:
                msg += " (cleared STOP_TRADING)"
            self._append_activity("CTRL   " + msg)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Start failed", str(exc))
            self._append_activity(f"ERROR  start failed: {exc}")
        self.refresh_status()

    def stop_engine(self) -> None:
        try:
            cfg = load_config_json(self.config_path)
            rt = runtime_dir(cfg)
            path = write_stop(rt)
            self._append_activity(f"CTRL   wrote {path.name}")
            if self.engine.running:
                self._stopping = True

                def _wait_then_kill() -> None:
                    deadline = time.time() + 10
                    while time.time() < deadline and self.engine.running:
                        time.sleep(0.2)
                    if self.engine.running:
                        self.engine.stop_hard()
                        self.log_queue.put("[hard-stopped process]")
                    self._stopping = False

                threading.Thread(target=_wait_then_kill, daemon=True).start()
            self._append_activity("CTRL   stop requested — also disable AutoTrading in MT4 for live")
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Stop failed", str(exc))
        self.refresh_status()

    def deploy_mt4(self) -> None:
        self._append_activity("CTRL   deploying MT4 files…")
        code, out = run_deploy_mt4()
        for line in out.splitlines() or [f"exit={code}"]:
            self._append_activity("DEPLOY " + line)
        if code != 0:
            messagebox.showerror("Deploy failed", out[-1000:] or f"exit {code}")
        else:
            messagebox.showinfo("Deploy", "MT4 files deployed.\nOpen EA from Data Folder and press F7.")
        self.refresh_status()

    def _tick(self) -> None:
        self._drain_logs()
        self._poll_audit()
        if self.engine.proc is not None and not self.engine.running and not self._stopping:
            code = self.engine.poll_exit()
            if code is not None:
                self.engine.proc = None
        self.refresh_status()
        self.root.after(500, self._tick)

    def _on_close(self) -> None:
        if self.engine.running:
            if not messagebox.askyesno("Engine running", "Engine is still running. Stop and exit?"):
                return
            try:
                cfg = load_config_json(self.config_path)
                write_stop(runtime_dir(cfg))
            except Exception:  # noqa: BLE001
                pass
            self.engine.stop_hard(timeout_s=5)
        self.root.destroy()


def main() -> int:
    try:
        resolve_config()
    except FileNotFoundError as exc:
        print(exc, file=sys.stderr)
        return 1

    root = tk.Tk()
    DashboardApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
