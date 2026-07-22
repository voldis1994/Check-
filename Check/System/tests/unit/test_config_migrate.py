from __future__ import annotations

import json
from pathlib import Path

from checktrader.config.migrate import apply_shipped_trading_profile, sync_system_json


def test_apply_shipped_trading_profile_keeps_runtime() -> None:
    example = {
        "regimes": {"trend": {"adx_min": 12.0}},
        "strategies": {"breakout": {"confirmation_mode": "breakout_only"}},
    }
    local = {
        "runtime": {"mode": "live", "trading_enabled": True},
        "regimes": {"trend": {"adx_min": 99.0}},
        "strategies": {"breakout": {"confirmation_mode": "breakout_and_retest"}},
    }
    merged = apply_shipped_trading_profile(local, example=example)
    assert merged["runtime"]["mode"] == "live"
    assert merged["runtime"]["trading_enabled"] is True
    assert merged["regimes"]["trend"]["adx_min"] == 12.0
    assert merged["strategies"]["breakout"]["confirmation_mode"] == "breakout_only"


def test_sync_system_json_rewrites_stale_profile(tmp_path: Path) -> None:
    example = tmp_path / "system.example.json"
    target = tmp_path / "system.json"
    example.write_text(
        json.dumps(
            {
                "runtime": {"mode": "paper", "trading_enabled": False},
                "regimes": {"trend": {"adx_min": 12.0}},
                "strategies": {"breakout": {"m1_impulse_lookback": 15}},
            }
        ),
        encoding="utf-8",
    )
    target.write_text(
        json.dumps(
            {
                "runtime": {"mode": "live", "trading_enabled": True},
                "account": {"account_id": "231054"},
                "regimes": {"trend": {"adx_min": 99.0}},
                "strategies": {"breakout": {"m1_impulse_lookback": 99}},
            }
        ),
        encoding="utf-8",
    )
    assert sync_system_json(target, example_path=example) is True
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["runtime"]["mode"] == "live"
    assert data["runtime"]["trading_enabled"] is True
    assert data["account"]["account_id"] == "231054"
    assert data["regimes"]["trend"]["adx_min"] == 12.0
    assert data["strategies"]["breakout"]["m1_impulse_lookback"] == 15
    assert sync_system_json(target, example_path=example) is False
