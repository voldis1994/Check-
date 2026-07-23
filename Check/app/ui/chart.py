"""Minimal candlestick canvas from M1 bars."""

from __future__ import annotations

import tkinter as tk
from typing import Any

from app.ui.theme import C


class CandleChart(tk.Canvas):
    def __init__(self, parent, **kw):
        super().__init__(parent, bg=C["panel2"], highlightthickness=0, **kw)
        self._bars: list[dict[str, Any]] = []
        self._signals: list[tuple[str, int]] = []
        self.bind("<Configure>", lambda _e: self.redraw())

    def set_data(self, bars: list[dict[str, Any]], signals: list[tuple[str, int]] | None = None) -> None:
        self._bars = bars[-120:] if bars else []
        self._signals = signals or []
        self.redraw()

    def redraw(self) -> None:
        self.delete("all")
        w = max(self.winfo_width(), 40)
        h = max(self.winfo_height(), 40)
        self.create_rectangle(0, 0, w, h, fill=C["panel2"], outline="")
        if len(self._bars) < 2:
            self.create_text(w // 2, h // 2, text="Waiting for M1 market…", fill=C["mute"], font=("Segoe UI", 11))
            return
        highs = [float(b["h"]) for b in self._bars]
        lows = [float(b["l"]) for b in self._bars]
        hi, lo = max(highs), min(lows)
        span = hi - lo or 1e-9
        n = len(self._bars)
        pad = 8
        cw = max(2, (w - 2 * pad) / n)

        for i, b in enumerate(self._bars):
            o, c, hh, ll = float(b["o"]), float(b["c"]), float(b["h"]), float(b["l"])
            x = pad + i * cw + cw / 2
            y_h = pad + (hi - hh) / span * (h - 2 * pad)
            y_l = pad + (hi - ll) / span * (h - 2 * pad)
            y_o = pad + (hi - o) / span * (h - 2 * pad)
            y_c = pad + (hi - c) / span * (h - 2 * pad)
            up = c >= o
            col = C["ok"] if up else C["bad"]
            self.create_line(x, y_h, x, y_l, fill=col, width=1)
            top, bot = min(y_o, y_c), max(y_o, y_c)
            self.create_rectangle(x - cw * 0.35, top, x + cw * 0.35, bot, fill=col, outline=col)

        for side, idx in self._signals:
            if idx < 0:
                idx = n + idx
            if 0 <= idx < n:
                x = pad + idx * cw + cw / 2
                col = C["ok"] if side == "BUY" else C["bad"]
                self.create_text(x, pad + 12, text=side, fill=col, font=("Segoe UI", 8, "bold"))
