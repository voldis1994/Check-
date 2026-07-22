from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, PositiveFloat, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RuntimeConfig(StrictModel):
    mode: Literal["paper", "live"] = "paper"
    trading_enabled: bool = False
    cycle_interval_seconds: PositiveFloat = 5.0
    timezone: str = "UTC"
    instance_id: str = "check-system-v3"
    protocol_version: str = "3.0.0"


class InstrumentConfig(StrictModel):
    symbol: str = "AUTO"
    timeframe_execution: str = "M1"
    timeframe_management: str = "M5"
    timeframe_decision: str = "M15"
    digits: int = 2
    point: PositiveFloat = 0.01
    tick_size: PositiveFloat = 0.01
    pip_size: PositiveFloat = 0.10
    contract_size: PositiveFloat = 100.0
    stop_level_points: float = Field(0.0, ge=0.0)
    freeze_level_points: float = Field(0.0, ge=0.0)


class AccountConfig(StrictModel):
    account_id: str = "PAPER"
    currency: str = "USD"
    min_equity: PositiveFloat = 100.0
    max_drawdown_percent: float = Field(25.0, ge=0.0, le=100.0)


class PositionConfig(StrictModel):
    max_open_positions: int = Field(1, ge=0)
    allow_hedging: bool = False
    default_lot: PositiveFloat = 0.01


class PositionSizingConfig(StrictModel):
    method: Literal["fixed_lot"] = "fixed_lot"
    fixed_lot: PositiveFloat = 0.01
    min_lot: PositiveFloat = 0.01
    max_lot: PositiveFloat = 100.0
    lot_step: PositiveFloat = 0.01


class RegimeTrendConfig(StrictModel):
    ema20_period: int = Field(20, ge=1)
    ema50_period: int = Field(50, ge=1)
    ema200_period: int = Field(200, ge=1)
    atr_period: int = Field(14, ge=1)
    adx_period: int = Field(14, ge=1)
    # Slope measured over this many bars
    slope_lookback: int = Field(5, ge=1)
    # EMA20 slope (|delta| / ATR) must be >= ema20_slope_atr for standard trend
    ema20_slope_atr: float = Field(0.15, ge=0.0)
    # EMA50 slope must be >= ema50_slope_atr
    ema50_slope_atr: float = Field(0.08, ge=0.0)
    # Minimum ADX for standard trend
    adx_min: float = Field(20.0, ge=0.0)
    # ADX >= adx_strong overrides slope requirement (structure + strong ADX enough)
    adx_strong: float = Field(25.0, ge=0.0)
    # |EMA20 - EMA50| / ATR >= ema_sep_atr
    ema_sep_atr: float = Field(0.20, ge=0.0)


class RegimeRangeConfig(StrictModel):
    atr_period: int = Field(14, ge=1)
    adx_period: int = Field(14, ge=1)
    adx_max: float = Field(18.0, ge=0.0)
    ema20_period: int = Field(20, ge=1)
    ema50_period: int = Field(50, ge=1)
    # EMA50 flatness: slope over flat_lookback bars / ATR <= flat_atr
    ema50_flat_lookback: int = Field(8, ge=1)
    ema50_flat_atr: float = Field(0.20, ge=0.0)
    # Max EMA separation (|EMA20-EMA50| / ATR)
    ema_sep_atr: float = Field(0.35, ge=0.0)
    # Range boundary detection using last range_lookback M15 bars
    range_lookback: int = Field(24, ge=2)
    width_min_atr: float = Field(1.5, gt=0.0)
    width_max_atr: float = Field(6.0, gt=0.0)
    # Bar high/low must be within touch_tol_atr * ATR of boundary to count as touch
    touch_tol_atr: float = Field(0.15, ge=0.0)
    # Minimum bars between two touches of the same side
    min_bars_between_touches: int = Field(3, ge=0)
    # Minimum valid touches required on each side
    min_touches_per_side: int = Field(2, ge=1)


class RegimeTransitionConfig(StrictModel):
    hold_bars: int = Field(2, ge=1)
    min_bars_between_changes: int = Field(1, ge=0)


class RegimeConfig(StrictModel):
    trend: RegimeTrendConfig = Field(default_factory=RegimeTrendConfig)
    range: RegimeRangeConfig = Field(default_factory=RegimeRangeConfig)
    transition: RegimeTransitionConfig = Field(default_factory=RegimeTransitionConfig)


class TrendContinuationConfig(StrictModel):
    enabled: bool = True
    atr_period: int = Field(14, ge=1)
    adx_period: int = Field(14, ge=1)
    swing_lookback: int = Field(2, ge=1)
    # Pullback zone: EMA20 - zone_low_atr*ATR <= price <= EMA20 + zone_high_atr*ATR
    pullback_zone_low_atr: float = Field(0.25, ge=0.0)
    pullback_zone_high_atr: float = Field(0.20, ge=0.0)
    # Invalidation: BUY invalidated if close < EMA50 - invalidation_atr*ATR
    invalidation_atr: float = Field(0.10, ge=0.0)
    # Trigger confirmation buffer: max(trigger_buffer_atr*ATR, trigger_buffer_ticks*tick)
    trigger_buffer_atr: float = Field(0.05, ge=0.0)
    trigger_buffer_ticks: int = Field(2, ge=0)
    # Candle quality filters
    body_ratio_min: float = Field(0.55, ge=0.0, le=1.0)
    max_candle_atr: float = Field(2.5, gt=0.0)
    # Entry is entry_distance_atr * ATR above/below EMA20
    entry_distance_atr: float = Field(0.35, ge=0.0)
    # Stop placed stop_buffer_atr * ATR below swing low (or above swing high)
    stop_buffer_atr: float = Field(0.15, ge=0.0)
    # Stop may not exceed stop_max_atr * ATR from entry
    stop_max_atr: float = Field(2.0, gt=0.0)
    take_profit_rr: float = Field(2.0, gt=0.0)
    # Setup expires after this many M1 bars
    expiry_m1_bars: int = Field(8, ge=1)


class RangeReversionConfig(StrictModel):
    enabled: bool = True
    atr_period: int = Field(14, ge=1)
    adx_period: int = Field(14, ge=1)
    # Price must be in the outer zone_pct fraction of the range
    zone_pct: float = Field(0.20, ge=0.0, le=1.0)
    # Lower wick / candle range >= wick_pct (for buy signal)
    wick_pct: float = Field(0.35, ge=0.0, le=1.0)
    # Stop placed stop_buffer_atr * ATR beyond boundary
    stop_buffer_atr: float = Field(0.20, ge=0.0)
    take_profit_rr: float = Field(1.5, gt=0.0)
    expiry_m1_bars: int = Field(6, ge=1)


class BreakoutConfig(StrictModel):
    enabled: bool = True
    atr_period: int = Field(14, ge=1)
    # Box is defined by the last N M5 bars; N must be in [box_min_m5_bars, box_max_m5_bars]
    box_min_m5_bars: int = Field(12, ge=1)
    box_max_m5_bars: int = Field(30, ge=1)
    # Box width / M15 ATR must be in [width_min_atr, width_max_atr]
    width_min_atr: float = Field(0.80, gt=0.0)
    width_max_atr: float = Field(4.0, gt=0.0)
    # Bar high/low within touch_tol_atr * ATR of box boundary counts as touch
    touch_tol_atr: float = Field(0.12, ge=0.0)
    min_touches_per_side: int = Field(2, ge=1)
    # confirmation_mode: breakout_only → entry on break; breakout_and_retest → wait for retest
    confirmation_mode: Literal["breakout_only", "breakout_and_retest"] = "breakout_and_retest"
    # Price must close beyond boundary by breakout_buffer_atr * ATR
    breakout_buffer_atr: float = Field(0.10, ge=0.0)
    # Retest: price must return within retest_tol_atr * ATR of broken boundary
    retest_tol_atr: float = Field(0.15, ge=0.0)
    # False breakout: price closes back inside box by > false_breakout_close_back_atr * ATR
    false_breakout_close_back_atr: float = Field(0.10, ge=0.0)
    stop_buffer_atr: float = Field(0.20, ge=0.0)
    take_profit_rr: float = Field(2.0, gt=0.0)
    expiry_m1_bars: int = Field(8, ge=1)
    # M1 impulse: catch staircase / momentum breaks that never form a clean M5 box retest
    m1_impulse_enabled: bool = True
    m1_impulse_lookback: int = Field(30, ge=5)
    m1_impulse_min_body_atr: float = Field(0.12, ge=0.0)


class StrategiesConfig(StrictModel):
    trend_continuation: TrendContinuationConfig = Field(default_factory=TrendContinuationConfig)
    range_reversion: RangeReversionConfig = Field(default_factory=RangeReversionConfig)
    breakout: BreakoutConfig = Field(default_factory=BreakoutConfig)


class RiskConfig(StrictModel):
    # Maximum aggregate daily loss in R-multiples before trading halts
    daily_loss_limit_r: float = Field(3.0, ge=0.0)
    # Minimum reward:risk ratio for any trade
    min_reward_risk: float = Field(1.5, gt=0.0)
    # Maximum stop size in ATR; global safety net (strategies also cap internally)
    max_stop_atr: float = Field(2.0, gt=0.0)
    # Absolute minimum stop in points (covers instruments with zero stop_level)
    min_stop_points: float = Field(10.0, gt=0.0)
    # Absolute maximum stop in points (safety ceiling)
    max_stop_points: float = Field(10000.0, gt=0.0)


class ManagementConfig(StrictModel):
    breakeven_trigger_rr: float = Field(1.0, gt=0.0)
    breakeven_offset_points: float = Field(2.0, ge=0.0)
    trailing_start_rr: float = Field(1.5, gt=0.0)
    trend_trailing_atr_multiplier: float = Field(1.0, gt=0.0)
    breakout_trailing_atr_multiplier: float = Field(1.2, gt=0.0)
    range_trailing_atr_multiplier: float = Field(0.8, gt=0.0)
    take_profit_rr: float = Field(2.0, gt=0.0)
    partial_close_enabled: bool = False
    exit_on_regime_flip: bool = True


class ExecutionConfig(StrictModel):
    magic_number: int = 30001
    command_ttl_seconds: PositiveFloat = 30.0
    ack_timeout_seconds: PositiveFloat = 10.0
    dedupe_window_seconds: PositiveFloat = 300.0
    paper_fill_spread_points: float = Field(0.0, ge=0.0)
    max_retries: int = Field(1, ge=0)


class SpreadConfig(StrictModel):
    max_points: float = Field(30.0, ge=0.0)
    max_atr_fraction: float = Field(0.15, ge=0.0)


class PathsConfig(StrictModel):
    runtime_dir: Path = Path("runtime")
    history_file: Path = Path("runtime/history/history.json")
    state_file: Path = Path("runtime/state.json")
    audit_file: Path = Path("runtime/audit.jsonl")
    metrics_file: Path = Path("runtime/metrics.json")
    bridge_dir: Path | None = None
    bridge_discovery_roots: tuple[Path, ...] = ()
    appdata_metaquotes_discovery: bool = True


class LimitsConfig(StrictModel):
    # Max trades per calendar day
    max_daily_trades: int = Field(6, ge=0)
    # Halt after this many consecutive losses
    max_consecutive_losses: int = Field(3, ge=0)
    # Cooldown period after a loss, expressed as M1 bar count (1 bar = 1 minute)
    cooldown_m1_bars: int = Field(5, ge=0)
    # Cooldown after a bridge/execution error (seconds)
    cooldown_error_seconds: float = Field(30.0, ge=0.0)
    max_cycles_without_market: int = Field(12, ge=0)
    heartbeat_max_age_seconds: float = Field(90.0, ge=0.0)
    history_max_bars_m1: int = Field(5000, ge=1)
    history_max_bars_m5: int = Field(1500, ge=1)
    history_max_bars_m15: int = Field(1000, ge=1)


class SystemConfig(StrictModel):
    version: str = "3.0.0"
    protocol_version: str = "3.0.0"
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)
    instrument: InstrumentConfig = Field(default_factory=InstrumentConfig)
    account: AccountConfig = Field(default_factory=AccountConfig)
    position: PositionConfig = Field(default_factory=PositionConfig)
    position_sizing: PositionSizingConfig = Field(default_factory=PositionSizingConfig)
    regimes: RegimeConfig = Field(default_factory=RegimeConfig)
    strategies: StrategiesConfig = Field(default_factory=StrategiesConfig)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    management: ManagementConfig = Field(default_factory=ManagementConfig)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    spread: SpreadConfig = Field(default_factory=SpreadConfig)
    paths: PathsConfig = Field(default_factory=PathsConfig)
    limits: LimitsConfig = Field(default_factory=LimitsConfig)

    @field_validator("version", "protocol_version")
    @classmethod
    def must_be_v3(cls, v: str) -> str:
        if v != "3.0.0":
            raise ValueError("CHECK SYSTEM v3 requires version 3.0.0")
        return v

    @model_validator(mode="after")
    def coherent(self) -> SystemConfig:
        if self.runtime.protocol_version != self.protocol_version:
            raise ValueError("runtime.protocol_version must match top-level protocol_version")
        if self.position.default_lot != self.position_sizing.fixed_lot:
            raise ValueError("position.default_lot must equal position_sizing.fixed_lot")
        return self
