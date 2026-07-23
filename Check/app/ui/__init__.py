"""Nexus visual theme + shared widgets."""

from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont
from typing import Callable

C = {
    "bg": "#0A0D14",
    "sidebar": "#0D111C",
    "panel": "#121826",
    "panel2": "#182033",
    "line": "#2A3550",
    "ink": "#EEF1F8",
    "mute": "#8B95B0",
    "violet": "#6C5CE7",
    "violet2": "#A29BFE",
    "ok": "#00C853",
    "bad": "#FF5252",
    "warn": "#FFB300",
    "ice": "#40C4FF",
    "pink": "#FF4081",
}


def font(names: list[str], size: int, weight: str = "normal") -> tuple:
    fam = set(tkfont.families())
    for n in names:
        if n in fam:
            return (n, size, weight) if weight != "normal" else (n, size)
    return ("TkDefaultFont", size, weight) if weight != "normal" else ("TkDefaultFont", size)


class Toggle(tk.Frame):
    def __init__(
        self,
        parent,
        var: tk.BooleanVar,
        text: str = "",
        on_change: Callable | None = None,
        *,
        bg: str | None = None,
    ):
        bg = bg or (parent.cget("bg") if str(parent.cget("bg")) else C["panel"])
        super().__init__(parent, bg=bg)
        self.var = var
        self.on_change = on_change
        self.btn = tk.Label(
            self,
            text="ON" if var.get() else "OFF",
            bg=C["ok"] if var.get() else C["line"],
            fg=C["ink"],
            font=("Segoe UI", 8, "bold"),
            width=4,
            cursor="hand2",
            padx=8,
            pady=2,
        )
        self.btn.pack(side=tk.LEFT)
        self.btn.bind("<Button-1>", self._flip)
        if text:
            tk.Label(self, text=text, bg=bg, fg=C["ink"], font=("Segoe UI", 10)).pack(side=tk.LEFT, padx=8)
        var.trace_add("write", lambda *_: self._paint())

    def _flip(self, _e=None) -> None:
        self.var.set(not self.var.get())
        if self.on_change:
            self.on_change()

    def _paint(self) -> None:
        on = bool(self.var.get())
        self.btn.configure(text="ON" if on else "OFF", bg=C["ok"] if on else C["line"])


def pill_btn(parent, text: str, color: str, cmd, *, bg: str | None = None) -> tk.Button:
    return tk.Button(
        parent,
        text=text,
        command=cmd,
        bg=bg or C["panel"],
        fg=color,
        activebackground=C["line"],
        activeforeground=color,
        relief=tk.FLAT,
        highlightthickness=1,
        highlightbackground=color,
        font=("Segoe UI", 9),
        padx=12,
        pady=6,
        cursor="hand2",
    )
