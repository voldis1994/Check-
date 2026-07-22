"""Config defaults and example payload helpers."""

from __future__ import annotations

from checktrader.config.models import SystemConfig


def default_system_config() -> SystemConfig:
    return SystemConfig()


EXAMPLE_SYSTEM_CONFIG: dict[str, object] = {
    "version": "2.0.0",
    "runtime": {
        "mode": "live",
        "trading_enabled": True,
        "cycle_interval_ms": 250,
        "timezone": "UTC",
        "instance_id": "EURUSD_M1_PRIMARY",
    },
    "account": {
        "allowed_account_numbers": [],
        "required_server": "",
        "require_trade_allowed": True,
        "require_expert_enabled": True,
    },
    "instrument": {
        "symbol": "EURUSD",
        "entry_timeframe": "M1",
        "setup_timeframe": "M5",
        "context_timeframe": "M15",
    },
    "position": {
        "maximum_open_positions": 1,
        "one_position_per_symbol_magic": True,
        "magic_number": 19942026,
    },
    "risk": {
        "sizing_mode": "fixed_lot",
        "fixed_lot": 0.01,
        "risk_percent": None,
        "require_stop_loss": True,
        "maximum_stop_loss_pips": 25.0,
        "minimum_reward_risk": 1.5,
        "daily_loss_limit_enabled": False,
        "drawdown_limit_enabled": False,
        "allow_lot_normalization": False,
    },
    "strategy": {
        "enabled_setup": "trend_pullback_break",
        "use_closed_bars_only": True,
        "setup_expiry_bars": 8,
        "minimum_structure_bars": 30,
        "hma_period": 21,
        "atr_period": 14,
        "pullback_atr_distance": 0.50,
        "trigger_break_buffer_pips": 0.20,
    },
    "execution": {
        "maximum_status_age_ms": 2000,
        "maximum_market_age_ms": 1500,
        "ack_timeout_ms": 5000,
        "maximum_retries": 3,
        "retry_delay_ms": 750,
        "price_tolerance_points": 2,
        "maximum_spread_pips": None,
    },
    "trade_management": {
        "enabled": True,
        "activation_profit_money": 0.50,
        "be_net_profit_money": 0.20,
        "trailing_step_pips": 3.0,
        "fixed_take_profit_enabled": False,
        "high_lock": {
            "enabled": True,
            "activation_peak_profit_money": 1.00,
            "lock_ratio": 0.60,
        },
        "exit_pressure": {
            "enabled": True,
            "pullback_weight": 0.30,
            "speed_weight": 0.20,
            "trend_weight": 0.20,
            "rejection_weight": 0.20,
            "spread_weight": 0.10,
            "tighten_threshold": 0.45,
            "high_lock_threshold": 0.70,
            "critical_threshold": 0.85,
            "critical_close_enabled": True,
            "minimum_non_spread_confirmations_for_close": 3,
        },
    },
    "logging": {
        "level": "INFO",
        "signal_audit_enabled": True,
        "trailing_audit_enabled": True,
        "execution_audit_enabled": True,
        "rotate_mb": 50,
        "retention_days": 30,
    },
    "dashboard": {"enabled": True, "host": "127.0.0.1", "port": 8765},
    "paths": {
        "root": ".",
        "bridge": "runtime/bridge",
        "state": "runtime/state",
        "logs": "runtime/logs",
    },
}
