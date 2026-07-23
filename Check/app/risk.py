"""Hard-number risk rules + toggles (no percentages, no ATR)."""

from __future__ import annotations

from typing import Any

# Defaults for every account — user edits hard numbers; toggles enable features
ACCOUNT_RISK_DEFAULTS: dict[str, Any] = {
    "lot": 0.02,
    "sl_points": 150,
    # BE
    "be_enabled": True,
    "be_start_points": 50,
    "be_offset_points": 5,
    # Trail
    "trail_enabled": True,
    "trail_start_points": 80,
    "trail_lock_points": 40,
    # Protection (money = account currency units)
    "equity_protection_enabled": False,
    "equity_floor": 0.0,
    "daily_loss_limit_enabled": False,
    "daily_loss_limit": 200.0,
    "profit_lock_enabled": False,
    "profit_lock": 300.0,
    "auto_stop_enabled": False,
    "auto_stop_after_losses": 3,
    "spread_filter_enabled": True,
    "max_spread_points": 40,
    "max_open_trades_enabled": True,
    "max_open_trades": 1,
}

GLOBAL_RISK_DEFAULTS: dict[str, Any] = {
    "magic": 50001,
    "cycle_sec": 3.0,
    "trend": True,
    "breakout": True,
    "range": False,
    "scalping": False,
    "symbol": "AUTO",
    "max_bars": 300,
    # portfolio-level hard caps
    "max_total_open_enabled": False,
    "max_total_open": 10,
    "global_daily_loss_enabled": False,
    "global_daily_loss": 1000.0,
    "global_equity_floor_enabled": False,
    "global_equity_floor": 0.0,
}


def merge_account_risk(raw: dict[str, Any] | None) -> dict[str, Any]:
    out = dict(ACCOUNT_RISK_DEFAULTS)
    if raw:
        out.update(raw)
    return out


def as_bool(v: Any, default: bool = False) -> bool:
    if isinstance(v, bool):
        return v
    if v is None:
        return default
    if isinstance(v, (int, float)):
        return bool(v)
    s = str(v).strip().lower()
    if s in {"1", "true", "yes", "on"}:
        return True
    if s in {"0", "false", "no", "off", ""}:
        return False
    return default


def as_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def as_int(v: Any, default: int = 0) -> int:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def block_new_entries(
    *,
    account: dict[str, Any],
    global_cfg: dict[str, Any],
    positions: list,
    spread_points: float | None,
    equity: float | None,
    daily_pl: float | None,
    consecutive_losses: int,
    total_open: int,
) -> str | None:
    """Return reason code if new OPEN must be blocked, else None."""
    acc = merge_account_risk(account)

    if as_bool(acc.get("max_open_trades_enabled"), True):
        max_n = as_int(acc.get("max_open_trades"), 1)
        if len(positions) >= max_n:
            return "MAX_OPEN"

    if as_bool(global_cfg.get("max_total_open_enabled"), False):
        if total_open >= as_int(global_cfg.get("max_total_open"), 10):
            return "MAX_TOTAL_OPEN"

    if as_bool(acc.get("spread_filter_enabled"), True) and spread_points is not None:
        if spread_points > as_float(acc.get("max_spread_points"), 40):
            return "SPREAD"

    if as_bool(acc.get("equity_protection_enabled"), False) and equity is not None:
        floor = as_float(acc.get("equity_floor"), 0)
        if floor > 0 and equity <= floor:
            return "EQUITY_FLOOR"

    if as_bool(global_cfg.get("global_equity_floor_enabled"), False) and equity is not None:
        gfloor = as_float(global_cfg.get("global_equity_floor"), 0)
        if gfloor > 0 and equity <= gfloor:
            return "GLOBAL_EQUITY_FLOOR"

    if as_bool(acc.get("daily_loss_limit_enabled"), False) and daily_pl is not None:
        lim = as_float(acc.get("daily_loss_limit"), 0)
        if lim > 0 and daily_pl <= -lim:
            return "DAILY_LOSS"

    if as_bool(global_cfg.get("global_daily_loss_enabled"), False) and daily_pl is not None:
        glim = as_float(global_cfg.get("global_daily_loss"), 0)
        if glim > 0 and daily_pl <= -glim:
            return "GLOBAL_DAILY_LOSS"

    if as_bool(acc.get("profit_lock_enabled"), False) and daily_pl is not None:
        lock = as_float(acc.get("profit_lock"), 0)
        if lock > 0 and daily_pl >= lock:
            return "PROFIT_LOCK"

    if as_bool(acc.get("auto_stop_enabled"), False):
        n = as_int(acc.get("auto_stop_after_losses"), 3)
        if n > 0 and consecutive_losses >= n:
            return "AUTO_STOP_LOSSES"

    if as_float(acc.get("sl_points"), 0) <= 0:
        return "SET_SL_POINTS"

    return None
