"""Configuration models (Pydantic)."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator, model_validator


class RuntimeConfig(BaseModel):
    mode: str = "live"
    trading_enabled: bool = True
    cycle_interval_ms: int = 250
    timezone: str = "UTC"
    instance_id: str = "EURUSD_M1_PRIMARY"


class AccountConfig(BaseModel):
    allowed_account_numbers: list[str] = Field(default_factory=list)
    required_server: str = ""
    require_trade_allowed: bool = True
    require_expert_enabled: bool = True


class InstrumentConfig(BaseModel):
    symbol: str = "EURUSD"
    entry_timeframe: str = "M1"
    setup_timeframe: str = "M5"
    context_timeframe: str = "M15"


class PositionConfig(BaseModel):
    maximum_open_positions: int = 1
    one_position_per_symbol_magic: bool = True
    magic_number: int = 19942026


class RiskConfig(BaseModel):
    sizing_mode: str = "fixed_lot"
    fixed_lot: float | None = 0.01
    risk_percent: float | None = None
    require_stop_loss: bool = True
    maximum_stop_loss_pips: float = 25.0
    minimum_reward_risk: float = 1.5
    daily_loss_limit_enabled: bool = False
    drawdown_limit_enabled: bool = False
    allow_lot_normalization: bool = False


class StrategyConfig(BaseModel):
    enabled_setup: str = "trend_pullback_break"
    use_closed_bars_only: bool = True
    setup_expiry_bars: int = 8
    minimum_structure_bars: int = 30
    hma_period: int = 21
    atr_period: int = 14
    pullback_atr_distance: float = 0.50
    trigger_break_buffer_pips: float = 0.20


class ExecutionConfig(BaseModel):
    maximum_status_age_ms: int = 2000
    maximum_market_age_ms: int = 1500
    ack_timeout_ms: int = 5000
    maximum_retries: int = 3
    retry_delay_ms: int = 750
    price_tolerance_points: int = 2
    maximum_spread_pips: float | None = None


class HighLockConfig(BaseModel):
    enabled: bool = True
    activation_peak_profit_money: float = 1.0
    lock_ratio: float = 0.60


class ExitPressureConfig(BaseModel):
    enabled: bool = True
    pullback_weight: float = 0.30
    speed_weight: float = 0.20
    trend_weight: float = 0.20
    rejection_weight: float = 0.20
    spread_weight: float = 0.10
    tighten_threshold: float = 0.45
    high_lock_threshold: float = 0.70
    critical_threshold: float = 0.85
    critical_close_enabled: bool = True
    minimum_non_spread_confirmations_for_close: int = 3

    @model_validator(mode="after")
    def weights_sum_to_one(self) -> ExitPressureConfig:
        total = (
            self.pullback_weight + self.speed_weight + self.trend_weight + self.rejection_weight + self.spread_weight
        )
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"exit_pressure weights must sum to 1.0, got {total}")
        return self


class TradeManagementConfig(BaseModel):
    enabled: bool = True
    activation_profit_money: float = 0.50
    be_net_profit_money: float = 0.20
    trailing_step_pips: float = 3.0
    fixed_take_profit_enabled: bool = False
    high_lock: HighLockConfig = Field(default_factory=HighLockConfig)
    exit_pressure: ExitPressureConfig = Field(default_factory=ExitPressureConfig)

    @field_validator("trailing_step_pips")
    @classmethod
    def positive_step(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("trailing_step_pips must be > 0")
        return value


class LoggingConfig(BaseModel):
    level: str = "INFO"
    signal_audit_enabled: bool = True
    trailing_audit_enabled: bool = True
    execution_audit_enabled: bool = True
    rotate_mb: int = 50
    retention_days: int = 30


class DashboardConfig(BaseModel):
    enabled: bool = True
    host: str = "127.0.0.1"
    port: int = 8765


class PathsConfig(BaseModel):
    root: str = "."
    bridge: str = "runtime/bridge"
    state: str = "runtime/state"
    logs: str = "runtime/logs"


class SystemConfig(BaseModel):
    version: str = "2.0.0"
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)
    account: AccountConfig = Field(default_factory=AccountConfig)
    instrument: InstrumentConfig = Field(default_factory=InstrumentConfig)
    position: PositionConfig = Field(default_factory=PositionConfig)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    strategy: StrategyConfig = Field(default_factory=StrategyConfig)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    trade_management: TradeManagementConfig = Field(default_factory=TradeManagementConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    dashboard: DashboardConfig = Field(default_factory=DashboardConfig)
    paths: PathsConfig = Field(default_factory=PathsConfig)
