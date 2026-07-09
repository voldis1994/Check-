from __future__ import annotations

from typing import Any

from engine.protocol.constants import CONFIG_SCHEMA_VERSION

FIXTURE_CYCLE_UTC = "2026-07-07T06:02:00.000Z"


def valid_system_config_payload() -> dict[str, Any]:
    return {
        "schema_version": CONFIG_SCHEMA_VERSION,
        "system": {
            "name": "SYSTEM",
            "root_path": r"C:\SYSTEM",
            "timeframe": "M1",
        },
        "paths": {
            "clients": "data/clients",
            "logs": "data/logs",
            "cache": "data/cache",
            "history": "data/history",
            "universe": "data/universe",
        },
        "runtime": {
            "cycle_interval_ms": 1000,
            "ack_timeout_ms": 5000,
            "retry_max": 3,
            "retry_delay_ms": 200,
            "data_stale_threshold_ms": 15000,
            "cycle_max_duration_ms": 30000,
            "metrics_interval_ms": 60000,
            "auto_discover_instances": True,
        },
        "instances": [
            {
                "account_id": "12345",
                "symbol": "EURUSD",
                "magic": 100001,
                "enabled": True,
            }
        ],
        "risk": {
            "max_open_positions_per_instance": 1,
            "max_daily_loss_percent": 2.0,
            "max_drawdown_percent": 10.0,
            "reward_ratio": 2.0,
            "max_risk_per_trade_percent": 1.0,
            "max_stop_loss_pips": 100.0,
            "volume_step": 0.01,
        },
        "analysis": {
            "lookback_bars": 120,
            "spread_relative_threshold": 1.5,
            "volatility_relative_threshold": 1.5,
            "block_high_impact_news": True,
            "stop_loss_buffer": 0.0002,
            "weights": {
                "momentum": 1.0,
                "trend": 1.0,
                "structure": 1.0,
                "pressure": 1.0,
                "behavior": 1.0,
                "impact": 1.0,
                "context": 1.0,
            },
        },
        "journal": {"retention_days": 30},
        "trade_management": {
            "enabled": True,
            "breakeven_progress_ratio": 0.5,
            "partial_close_progress_ratio": 0.75,
            "partial_close_volume_ratio": 0.5,
            "time_stop_max_bars": 120,
        },
        "dashboard": {"refresh_interval_ms": 1000},
        "logging": {"level": "INFO", "format": "standard"},
        "ai": {
            "mode": "advisory",
            "fail_closed": False,
            "reject_action": "BLOCK",
            "timeout_ms": 10000,
            "retry_max": 2,
            "retry_delay_ms": 500,
        },
    }
