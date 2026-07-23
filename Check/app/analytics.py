"""Simple portfolio analytics from live bridges + journal file."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app import bridge, clients, paths


def journal_path() -> Path:
    return paths.app_root() / "runtime" / "journal.jsonl"


def append_journal(event: dict[str, Any]) -> None:
    paths.ensure_layout()
    with journal_path().open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event) + "\n")


def read_journal(limit: int = 200) -> list[dict[str, Any]]:
    p = journal_path()
    if not p.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        for line in p.read_text(encoding="utf-8").splitlines():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except OSError:
        return []
    return rows[-limit:]


def snapshot() -> dict[str, Any]:
    """Live KPIs from bridges + closed journal stats."""
    equity = 0.0
    balance = 0.0
    open_n = 0
    symbols: dict[str, int] = {}
    for b in clients.all_bridges():
        st = bridge.load_status(b) or {}
        mk = bridge.load_market(b) or {}
        equity += float(st.get("equity") or 0)
        balance += float(st.get("balance") or st.get("equity") or 0)
        positions = st.get("positions") or []
        if isinstance(positions, list):
            open_n += len(positions)
        sym = str(mk.get("symbol") or "")
        if sym:
            symbols[sym] = symbols.get(sym, 0) + 1

    wins = losses = 0
    profit_sum = loss_sum = 0.0
    by_symbol: dict[str, float] = {}
    for row in read_journal(500):
        if row.get("type") != "CLOSE":
            continue
        pl = float(row.get("pl") or 0)
        sym = str(row.get("symbol") or "?")
        by_symbol[sym] = by_symbol.get(sym, 0) + pl
        if pl >= 0:
            wins += 1
            profit_sum += pl
        else:
            losses += 1
            loss_sum += abs(pl)

    closed = wins + losses
    win_rate = (wins / closed * 100.0) if closed else 0.0
    pf = (profit_sum / loss_sum) if loss_sum > 0 else (profit_sum if profit_sum > 0 else 0.0)
    daily = equity - balance
    return {
        "equity": equity,
        "daily_pl": daily,
        "open_positions": open_n,
        "win_rate": win_rate,
        "profit_factor": pf,
        "wins": wins,
        "losses": losses,
        "by_symbol": by_symbol,
        "symbols": symbols,
    }
