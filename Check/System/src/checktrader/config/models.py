"""Configuration models (Pydantic)."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator, model_validator


class RuntimeConfig(BaseModel):
    mode: str = "live"
    trading_enabled: bool = True
    cycle_interval_ms: int = 250
    timezone: str = "UTC"
    instance_id: str = "PRIMARY"


class AccountConfig(BaseModel):
    """Empty / AUTO allow-list → accept the account reported by the MT4 status snapshot."""

    allowed_account_numbers: list[str] = Field(default_factory=list)
    required_server: str = ""
    require_trade_allowed: bool = True
    require_expert_enabled: bool = True


class InstrumentConfig(BaseModel):
    """``symbol`` may be a concrete MT4 name, or AUTO to follow the EA chart."""

    symbol: str = "AUTO"
    entry_timeframe: str = "M1"
    setup_timeframe: str = "M5"
    context_timeframe: str = "M15"


class PositionConfig(BaseModel):
    maximum_open_positions: int = 1
    one_position_per_symbol_magic: bool = True
    magic_number: int = 19942026


class PositionSizingConfig(BaseModel):
    """Production lot source — fixed lot only."""

    mode: str = "fixed_lot"
    fixed_lot: float = 0.01
    allow_broker_lot_normalization: bool = False

    @field_validator("mode")
    @classmethod
    def only_fixed_lot(cls, value: str) -> str:
        if value != "fixed_lot":
            raise ValueError("position_sizing.mode must be 'fixed_lot'")
        return value

    @field_validator("fixed_lot")
    @classmethod
    def positive_lot(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("fixed_lot must be > 0")
        return value

    @field_validator("allow_broker_lot_normalization")
    @classmethod
    def no_silent_normalize(cls, value: bool) -> bool:
        if value:
            raise ValueError("allow_broker_lot_normalization must be false in production")
        return value


class StrategyConfig(BaseModel):
    enabled_setup: str = "trend_pullback_break"
    use_closed_bars_only: bool = True
    setup_expiry_bars: int = 8
    minimum_structure_bars: int = 30
    hma_period: int = 21
    atr_period: int = 14
    pullback_min_atr: float = 0.25
    pullback_max_atr: float = 0.75
    trigger_buffer_atr: float = 0.05
    maximum_stop_atr: float = 2.5
    require_stop_loss: bool = True

    @model_validator(mode="after")
    def pullback_bounds(self) -> StrategyConfig:
        if self.pullback_min_atr < 0 or self.pullback_max_atr <= 0:
            raise ValueError("pullback ATR bounds must be positive")
        if self.pullback_min_atr > self.pullback_max_atr:
            raise ValueError("pullback_min_atr must be <= pullback_max_atr")
        if self.trigger_buffer_atr < 0 or self.maximum_stop_atr <= 0:
            raise ValueError("trigger_buffer_atr / maximum_stop_atr invalid")
        return self


class ExecutionConfig(BaseModel):
    maximum_status_age_ms: int = 4000
    maximum_market_age_ms: int = 3500
    ack_timeout_ms: int = 5000
    maximum_retries: int = 3
    retry_delay_ms: int = 750
    price_tolerance_points: int = 2
    maximum_spread_points: float | None = None
    maximum_spread_atr: float | None = None
    slippage_points: int = 3

    @field_validator("slippage_points")
    @classmethod
    def positive_slippage(cls, value: int) -> int:
        if value < 0:
            raise ValueError("slippage_points must be >= 0")
        return value


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
    be_activation_r: float | None = None
    be_activation_atr: float = 0.60
    be_net_profit_money: float = 0.20
    trailing_activation_atr: float = 0.70
    trailing_distance_atr: float = 0.80
    trailing_step_atr: float = 0.20
    fixed_take_profit_enabled: bool = False
    minimum_reward_risk: float = 1.5
    high_lock: HighLockConfig = Field(default_factory=HighLockConfig)
    exit_pressure: ExitPressureConfig = Field(default_factory=ExitPressureConfig)

    @field_validator("be_activation_r")
    @classmethod
    def r_disabled(cls, value: float | None) -> float | None:
        if value is not None:
            raise ValueError("be_activation_r must be null — R/account-risk sizing is not used")
        return value

    @field_validator("be_activation_atr", "trailing_activation_atr", "trailing_distance_atr", "trailing_step_atr")
    @classmethod
    def positive_atr(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("ATR trade-management multipliers must be > 0")
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
    position_sizing: PositionSizingConfig = Field(default_factory=PositionSizingConfig)
    strategy: StrategyConfig = Field(default_factory=StrategyConfig)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    trade_management: TradeManagementConfig = Field(default_factory=TradeManagementConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    dashboard: DashboardConfig = Field(default_factory=DashboardConfig)
    paths: PathsConfig = Field(default_factory=PathsConfig)
