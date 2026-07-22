from __future__ import annotations
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, PositiveFloat, field_validator, model_validator
class StrictModel(BaseModel): model_config=ConfigDict(extra='forbid', frozen=True)
class RuntimeConfig(StrictModel):
    mode: Literal['paper','live']='paper'; trading_enabled: bool=False; cycle_interval_seconds: PositiveFloat=5.0; timezone: str='UTC'; instance_id: str='check-system-v3'; protocol_version: str='3.0.0'
class InstrumentConfig(StrictModel):
    symbol: str='XAUUSD'; timeframe_execution: str='M1'; timeframe_management: str='M5'; timeframe_decision: str='M15'; digits: int=2; point: PositiveFloat=0.01; pip_size: PositiveFloat=0.10; contract_size: PositiveFloat=100.0; stop_level_points: float=Field(0.0, ge=0.0); freeze_level_points: float=Field(0.0, ge=0.0)
class AccountConfig(StrictModel): account_id: str='PAPER'; currency: str='USD'; min_equity: PositiveFloat=100.0; max_drawdown_percent: float=Field(25.0, ge=0.0, le=100.0)
class PositionConfig(StrictModel): max_open_positions: int=Field(1, ge=0); allow_hedging: bool=False; default_lot: PositiveFloat=0.01
class PositionSizingConfig(StrictModel): method: Literal['fixed_lot']='fixed_lot'; fixed_lot: PositiveFloat=0.01; min_lot: PositiveFloat=0.01; max_lot: PositiveFloat=100.0; lot_step: PositiveFloat=0.01
class RegimeTrendConfig(StrictModel): ema_fast_period: int=Field(20, ge=1); ema_slow_period: int=Field(50, ge=1); adx_period: int=Field(14, ge=1); atr_period: int=Field(14, ge=1); min_adx: float=Field(25.0, ge=0.0); min_ema_separation_atr: float=Field(0.25, ge=0.0); min_slope_points: float=Field(5.0, ge=0.0); confirmation_bars: int=Field(2, ge=1)
class RegimeRangeConfig(StrictModel): ema_fast_period: int=Field(20, ge=1); ema_slow_period: int=Field(50, ge=1); adx_period: int=Field(14, ge=1); atr_period: int=Field(14, ge=1); max_adx: float=Field(20.0, ge=0.0); max_ema_separation_atr: float=Field(0.20, ge=0.0); lookback_bars: int=Field(48, ge=2); min_touches: int=Field(2, ge=1); boundary_tolerance_atr: float=Field(0.25, ge=0.0)
class RegimeTransitionConfig(StrictModel): hold_bars: int=Field(2, ge=1); min_bars_between_changes: int=Field(1, ge=0)
class RegimeConfig(StrictModel): trend: RegimeTrendConfig=Field(default_factory=RegimeTrendConfig); range: RegimeRangeConfig=Field(default_factory=RegimeRangeConfig); transition: RegimeTransitionConfig=Field(default_factory=RegimeTransitionConfig)
class TrendContinuationConfig(StrictModel): enabled: bool=True; pullback_ema_period: int=Field(20, ge=1); swing_lookback: int=Field(2, ge=1); max_pullback_atr: float=Field(1.0, ge=0.0); min_close_beyond_ema_points: float=Field(2.0, ge=0.0); entry_buffer_points: float=Field(2.0, ge=0.0); stop_atr_multiplier: float=Field(1.5, gt=0.0); take_profit_rr: float=Field(2.0, gt=0.0); min_adx: float=Field(25.0, ge=0.0); require_regime_alignment: bool=True
class RangeReversionConfig(StrictModel): enabled: bool=True; lookback_bars: int=Field(48, ge=2); boundary_tolerance_atr: float=Field(0.25, ge=0.0); rejection_close_fraction: float=Field(0.60, ge=0.0, le=1.0); stop_buffer_atr: float=Field(0.50, gt=0.0); take_profit_fraction: float=Field(0.50, gt=0.0, le=1.0); min_range_atr: float=Field(1.50, gt=0.0); max_adx: float=Field(20.0, ge=0.0)
class BreakoutConfig(StrictModel): enabled: bool=True; box_lookback_bars: int=Field(32, ge=2); min_box_atr: float=Field(1.0, gt=0.0); max_box_atr: float=Field(4.0, gt=0.0); breakout_buffer_atr: float=Field(0.10, ge=0.0); retest_required: bool=True; retest_tolerance_atr: float=Field(0.20, ge=0.0); stop_buffer_atr: float=Field(0.50, gt=0.0); take_profit_rr: float=Field(2.0, gt=0.0); setup_expiry_bars: int=Field(8, ge=1); min_adx: float=Field(20.0, ge=0.0)
class StrategiesConfig(StrictModel): trend_continuation: TrendContinuationConfig=Field(default_factory=TrendContinuationConfig); range_reversion: RangeReversionConfig=Field(default_factory=RangeReversionConfig); breakout: BreakoutConfig=Field(default_factory=BreakoutConfig)
class RiskConfig(StrictModel): max_daily_loss_percent: float=Field(3.0, ge=0.0, le=100.0); max_risk_per_trade_percent: float=Field(1.0, ge=0.0, le=100.0); min_stop_points: float=Field(50.0, gt=0.0); max_stop_points: float=Field(5000.0, gt=0.0); min_reward_risk: float=Field(1.20, gt=0.0); max_slippage_points: float=Field(20.0, ge=0.0)
class ManagementConfig(StrictModel): breakeven_trigger_rr: float=Field(1.0, gt=0.0); breakeven_offset_points: float=Field(2.0, ge=0.0); trailing_start_rr: float=Field(1.5, gt=0.0); trend_trailing_atr_multiplier: float=Field(1.0, gt=0.0); breakout_trailing_atr_multiplier: float=Field(1.2, gt=0.0); range_trailing_atr_multiplier: float=Field(0.8, gt=0.0); take_profit_rr: float=Field(2.0, gt=0.0); partial_close_enabled: bool=False; exit_on_regime_flip: bool=True
class ExecutionConfig(StrictModel): magic_number: int=30001; command_ttl_seconds: PositiveFloat=30.0; ack_timeout_seconds: PositiveFloat=10.0; dedupe_window_seconds: PositiveFloat=300.0; paper_fill_spread_points: float=Field(0.0, ge=0.0); max_retries: int=Field(1, ge=0)
class SpreadConfig(StrictModel): max_points: float=Field(30.0, ge=0.0); max_atr_fraction: float=Field(0.10, ge=0.0)
class PathsConfig(StrictModel): runtime_dir: Path=Path('runtime'); history_file: Path=Path('runtime/history/history.json'); state_file: Path=Path('runtime/state.json'); audit_file: Path=Path('runtime/audit.jsonl'); metrics_file: Path=Path('runtime/metrics.json'); bridge_dir: Path|None=None; bridge_discovery_roots: tuple[Path,...]=(); appdata_metaquotes_discovery: bool=True
class LimitsConfig(StrictModel): max_daily_trades: int=Field(3, ge=0); max_consecutive_losses: int=Field(2, ge=0); cooldown_minutes: float=Field(30.0, ge=0.0); max_cycles_without_market: int=Field(12, ge=0); heartbeat_max_age_seconds: float=Field(20.0, ge=0.0); history_max_bars_m1: int=Field(5000, ge=1); history_max_bars_m5: int=Field(1500, ge=1); history_max_bars_m15: int=Field(1000, ge=1)
class SystemConfig(StrictModel):
    version: str='3.0.0'; protocol_version: str='3.0.0'; runtime: RuntimeConfig=Field(default_factory=RuntimeConfig); instrument: InstrumentConfig=Field(default_factory=InstrumentConfig); account: AccountConfig=Field(default_factory=AccountConfig); position: PositionConfig=Field(default_factory=PositionConfig); position_sizing: PositionSizingConfig=Field(default_factory=PositionSizingConfig); regimes: RegimeConfig=Field(default_factory=RegimeConfig); strategies: StrategiesConfig=Field(default_factory=StrategiesConfig); risk: RiskConfig=Field(default_factory=RiskConfig); management: ManagementConfig=Field(default_factory=ManagementConfig); execution: ExecutionConfig=Field(default_factory=ExecutionConfig); spread: SpreadConfig=Field(default_factory=SpreadConfig); paths: PathsConfig=Field(default_factory=PathsConfig); limits: LimitsConfig=Field(default_factory=LimitsConfig)
    @field_validator('version','protocol_version')
    @classmethod
    def must_be_v3(cls, v: str) -> str:
        if v != '3.0.0': raise ValueError('CHECK SYSTEM v3 requires 3.0.0')
        return v
    @model_validator(mode='after')
    def coherent(self) -> 'SystemConfig':
        if self.runtime.protocol_version != self.protocol_version: raise ValueError('runtime.protocol_version must match protocol_version')
        if self.position.default_lot != self.position_sizing.fixed_lot: raise ValueError('default_lot must match fixed_lot')
        return self
