from __future__ import annotations

import json
from pathlib import Path

from checktrader.config.migrate import apply_shipped_trading_profile, sync_system_json


def test_apply_shipped_trading_profile_keeps_runtime() -> None:
    example = {
        "regimes": {"trend": {"adx_min": 12.0}},
        "strategies": {
            "breakout": {"confirmation_mode": "breakout_only"},
            "force_entry_when_idle": True,
            "force_stop_atr": 0.18,
        },
        "risk": {
            "daily_loss_limit_r": 0.0,
            "enforce_account_status": False,
            "max_stop_atr": 1.5,
        },
        "limits": {"max_daily_trades": 0},
        "spread": {"max_points": 500.0},
        "position": {
            "max_open_positions": 1,
            "allow_hedging": False,
            "default_lot": 0.02,
        },
        "position_sizing": {
            "method": "fixed_lot",
            "fixed_lot": 0.02,
            "min_lot": 0.01,
            "max_lot": 100.0,
            "lot_step": 0.01,
        },
        "management": {
            "hard_take_profit": False,
            "trailing_start_rr": 0.35,
            "breakeven_trigger_rr": 0.40,
        },
        "account": {
            "account_id": "PAPER",
            "currency": "USD",
            "min_equity": 0.0,
            "max_drawdown_percent": 100.0,
        },
    }
    local = {
        "runtime": {"mode": "live", "trading_enabled": True},
        "account": {
            "account_id": "231054",
            "currency": "USD",
            "min_equity": 100.0,
            "max_drawdown_percent": 25.0,
        },
        "regimes": {"trend": {"adx_min": 99.0}},
        "strategies": {
            "breakout": {"confirmation_mode": "breakout_and_retest"},
            "force_stop_atr": 0.50,
        },
        "risk": {"daily_loss_limit_r": 9.0, "max_stop_atr": 3.0},
        "limits": {"max_daily_trades": 6},
        "position": {
            "max_open_positions": 1,
            "allow_hedging": False,
            "default_lot": 0.01,
        },
        "position_sizing": {
            "method": "fixed_lot",
            "fixed_lot": 0.01,
            "min_lot": 0.01,
            "max_lot": 100.0,
            "lot_step": 0.01,
        },
        "management": {
            "hard_take_profit": True,
            "trailing_start_rr": 1.5,
        },
    }
    merged = apply_shipped_trading_profile(local, example=example)
    assert merged["runtime"]["mode"] == "live"
    assert merged["account"]["account_id"] == "231054"
    assert merged["account"]["min_equity"] == 0.0
    assert merged["regimes"]["trend"]["adx_min"] == 12.0
    assert merged["risk"]["daily_loss_limit_r"] == 0.0
    assert merged["risk"]["max_stop_atr"] == 1.5
    assert merged["limits"]["max_daily_trades"] == 0
    assert merged["strategies"]["force_entry_when_idle"] is True
    assert merged["strategies"]["force_stop_atr"] == 0.18
    assert merged["position"]["default_lot"] == 0.02
    assert merged["position_sizing"]["fixed_lot"] == 0.02
    assert merged["management"]["hard_take_profit"] is False
    assert merged["management"]["trailing_start_rr"] == 0.35


def test_sync_system_json_rewrites_stale_profile(tmp_path: Path) -> None:
    example = tmp_path / "system.example.json"
    target = tmp_path / "system.json"
    example.write_text(
        json.dumps(
            {
                "runtime": {"mode": "paper", "trading_enabled": False},
                "account": {
                    "account_id": "PAPER",
                    "currency": "USD",
                    "min_equity": 0.0,
                    "max_drawdown_percent": 100.0,
                },
                "regimes": {"trend": {"adx_min": 12.0}},
                "strategies": {
                    "breakout": {"m1_impulse_lookback": 15},
                    "force_entry_when_idle": True,
                    "force_stop_atr": 0.18,
                },
                "risk": {
                    "daily_loss_limit_r": 0.0,
                    "enforce_account_status": False,
                    "max_stop_atr": 1.5,
                },
                "limits": {"max_daily_trades": 0},
                "spread": {"max_points": 500.0},
                "position": {
                    "max_open_positions": 1,
                    "allow_hedging": False,
                    "default_lot": 0.02,
                },
                "position_sizing": {
                    "method": "fixed_lot",
                    "fixed_lot": 0.02,
                    "min_lot": 0.01,
                    "max_lot": 100.0,
                    "lot_step": 0.01,
                },
            }
        ),
        encoding="utf-8",
    )
    target.write_text(
        json.dumps(
            {
                "runtime": {"mode": "live", "trading_enabled": True},
                "account": {
                    "account_id": "231054",
                    "currency": "USD",
                    "min_equity": 100.0,
                    "max_drawdown_percent": 25.0,
                },
                "regimes": {"trend": {"adx_min": 99.0}},
                "strategies": {
                    "breakout": {"m1_impulse_lookback": 99},
                    "force_stop_atr": 0.50,
                },
                "risk": {"daily_loss_limit_r": 3.0, "max_stop_atr": 3.0},
                "limits": {"max_daily_trades": 6},
                "position": {
                    "max_open_positions": 1,
                    "allow_hedging": False,
                    "default_lot": 0.01,
                },
                "position_sizing": {
                    "method": "fixed_lot",
                    "fixed_lot": 0.01,
                    "min_lot": 0.01,
                    "max_lot": 100.0,
                    "lot_step": 0.01,
                },
            }
        ),
        encoding="utf-8",
    )
    assert sync_system_json(target, example_path=example) is True
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["runtime"]["mode"] == "live"
    assert data["runtime"]["trading_enabled"] is True
    assert data["account"]["account_id"] == "231054"
    assert data["account"]["min_equity"] == 0.0
    assert data["regimes"]["trend"]["adx_min"] == 12.0
    assert data["risk"]["daily_loss_limit_r"] == 0.0
    assert data["limits"]["max_daily_trades"] == 0
    assert data["strategies"]["breakout"]["m1_impulse_lookback"] == 15
    assert data["strategies"]["force_stop_atr"] == 0.18
    assert data["position"]["default_lot"] == 0.02
    assert data["position_sizing"]["fixed_lot"] == 0.02
    assert sync_system_json(target, example_path=example) is False
