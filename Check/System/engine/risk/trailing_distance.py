from __future__ import annotations
import statistics
from dataclasses import dataclass
from typing import Sequence
from engine.normalizer.market_normalizer import NormalizedMarketBar
from engine.protocol.errors import ValidationError
from engine.protocol.models import InstanceDefinition, SystemConfig, TradeManagementSettings

MODULE_NAME = 'risk.trailing_distance'
TRAILING_MODE_FIXED_PIPS = 'fixed_pips'
TRAILING_MODE_ATR_MULTIPLE = 'atr_multiple'
TRAILING_MODE_SL_FRACTION = 'sl_fraction'
TRAILING_MODES = frozenset({TRAILING_MODE_FIXED_PIPS, TRAILING_MODE_ATR_MULTIPLE, TRAILING_MODE_SL_FRACTION})

@dataclass(frozen=True)
class ResolvedTrailingParams:
    mode: str
    lookback_bars: int
    step_pips: float
    atr_mult: float
    atr_period: int
    sl_fraction: float
    spread_floor_mult: float
    stop_loss_buffer: float

@dataclass(frozen=True)
class TrailingDistances:
    price_trail_distance: float
    trailing_buffer: float
    mode_distance: float
    atr: float

def _validation_error(message: str, **context: object) -> ValidationError:
    return ValidationError(message, module=MODULE_NAME, context=dict(context))

def _bar_true_range(bar: NormalizedMarketBar, previous_close: float | None) -> float:
    bar_range = bar.high - bar.low
    if previous_close is None:
        return bar_range
    return max(bar_range, abs(bar.high - previous_close), abs(bar.low - previous_close))

def compute_atr(bars: Sequence[NormalizedMarketBar], *, period: int) -> float:
    if period <= 0:
        raise _validation_error('atr period must be > 0', period=period)
    materialized = tuple(bars)
    if len(materialized) < 2:
        return 0.0
    window = materialized[-period:]
    true_ranges: list[float] = []
    window_start = len(materialized) - len(window)
    for offset, bar in enumerate(window):
        bar_index = window_start + offset
        previous_close = materialized[bar_index - 1].close if bar_index > 0 else None
        true_ranges.append(_bar_true_range(bar, previous_close))
    if not true_ranges:
        return 0.0
    return float(statistics.fmean(true_ranges))

def compute_fixed_pips_distance(*, step_pips: float, pip: float) -> float:
    if step_pips < 0:
        raise _validation_error('step_pips must be >= 0', step_pips=step_pips)
    if pip < 0:
        raise _validation_error('pip must be >= 0', pip=pip)
    if step_pips <= 0 or pip <= 0:
        return 0.0
    return step_pips * pip

def compute_atr_distance(*, atr: float, atr_mult: float) -> float:
    if atr < 0:
        raise _validation_error('atr must be >= 0', atr=atr)
    if atr_mult < 0:
        raise _validation_error('atr_mult must be >= 0', atr_mult=atr_mult)
    if atr <= 0 or atr_mult <= 0:
        return 0.0
    return atr_mult * atr

def compute_sl_fraction_distance(*, entry_price: float, stop_loss: float, sl_fraction: float) -> float:
    if sl_fraction < 0:
        raise _validation_error('sl_fraction must be >= 0', sl_fraction=sl_fraction)
    risk = abs(entry_price - stop_loss)
    if risk <= 0 or sl_fraction <= 0:
        return 0.0
    return sl_fraction * risk

def compute_mode_distance(*, mode: str, step_pips: float, pip: float, atr: float, atr_mult: float, entry_price: float | None, stop_loss: float | None, sl_fraction: float) -> float:
    if mode not in TRAILING_MODES:
        raise _validation_error('unsupported trailing mode', mode=mode, allowed=sorted(TRAILING_MODES))
    if mode == TRAILING_MODE_FIXED_PIPS:
        return compute_fixed_pips_distance(step_pips=step_pips, pip=pip)
    if mode == TRAILING_MODE_ATR_MULTIPLE:
        atr_distance = compute_atr_distance(atr=atr, atr_mult=atr_mult)
        if atr_distance > 0:
            return atr_distance
        return compute_fixed_pips_distance(step_pips=step_pips, pip=pip)
    if entry_price is None or stop_loss is None:
        return compute_fixed_pips_distance(step_pips=step_pips, pip=pip)
    distance = compute_sl_fraction_distance(entry_price=entry_price, stop_loss=stop_loss, sl_fraction=sl_fraction)
    if distance > 0:
        return distance
    return compute_fixed_pips_distance(step_pips=step_pips, pip=pip)

def apply_spread_floor(distance: float, *, spread: float, floor_mult: float) -> float:
    if distance < 0:
        raise _validation_error('distance must be >= 0', distance=distance)
    if spread < 0:
        raise _validation_error('spread must be >= 0', spread=spread)
    if floor_mult < 0:
        raise _validation_error('floor_mult must be >= 0', floor_mult=floor_mult)
    return max(distance, spread * floor_mult)

def resolve_structure_buffer(*, configured_buffer: float, spread: float) -> float:
    if configured_buffer < 0:
        raise _validation_error('configured_buffer must be >= 0', configured_buffer=configured_buffer)
    if spread < 0:
        raise _validation_error('spread must be >= 0', spread=spread)
    return max(configured_buffer, spread)

def resolve_trailing_params(*, settings: TradeManagementSettings, analysis_stop_loss_buffer: float, instance_definition: InstanceDefinition | None=None) -> ResolvedTrailingParams:
    definition = instance_definition
    mode = definition.trailing_mode if definition is not None and definition.trailing_mode is not None else settings.trailing_mode
    lookback = definition.trailing_lookback_bars if definition is not None and definition.trailing_lookback_bars is not None else settings.trailing_lookback_bars
    step_pips = definition.trailing_step_pips if definition is not None and definition.trailing_step_pips is not None else settings.trailing_step_pips
    atr_mult = definition.trailing_atr_mult if definition is not None and definition.trailing_atr_mult is not None else settings.trailing_atr_mult
    atr_period = definition.trailing_atr_period if definition is not None and definition.trailing_atr_period is not None else settings.trailing_atr_period
    sl_fraction = definition.trailing_sl_fraction if definition is not None and definition.trailing_sl_fraction is not None else settings.trailing_sl_fraction
    spread_floor_mult = definition.trailing_spread_floor_mult if definition is not None and definition.trailing_spread_floor_mult is not None else settings.trailing_spread_floor_mult
    stop_loss_buffer = definition.stop_loss_buffer if definition is not None and definition.stop_loss_buffer is not None else analysis_stop_loss_buffer
    if mode not in TRAILING_MODES:
        raise _validation_error('unsupported trailing mode', mode=mode, allowed=sorted(TRAILING_MODES))
    if lookback < 1:
        raise _validation_error('lookback_bars must be >= 1', lookback_bars=lookback)
    if atr_period < 1:
        raise _validation_error('atr_period must be >= 1', atr_period=atr_period)
    return ResolvedTrailingParams(mode=mode, lookback_bars=lookback, step_pips=float(step_pips), atr_mult=float(atr_mult), atr_period=int(atr_period), sl_fraction=float(sl_fraction), spread_floor_mult=float(spread_floor_mult), stop_loss_buffer=float(stop_loss_buffer))

def find_instance_definition(config: SystemConfig, *, account_id: str, symbol: str, magic: int) -> InstanceDefinition | None:
    for definition in config.instances:
        if definition.account_id == account_id and definition.symbol == symbol and definition.magic == magic:
            return definition
    return None

def resolve_trailing_distances(*, params: ResolvedTrailingParams, pip: float, market_bars: Sequence[NormalizedMarketBar], current_spread: float, entry_price: float | None, stop_loss: float | None) -> TrailingDistances:
    atr = compute_atr(market_bars, period=params.atr_period) if params.mode == TRAILING_MODE_ATR_MULTIPLE else 0.0
    mode_distance = compute_mode_distance(mode=params.mode, step_pips=params.step_pips, pip=pip, atr=atr, atr_mult=params.atr_mult, entry_price=entry_price, stop_loss=stop_loss, sl_fraction=params.sl_fraction)
    price_trail_distance = apply_spread_floor(mode_distance, spread=current_spread, floor_mult=params.spread_floor_mult)
    trailing_buffer = resolve_structure_buffer(configured_buffer=params.stop_loss_buffer, spread=current_spread)
    return TrailingDistances(price_trail_distance=price_trail_distance, trailing_buffer=trailing_buffer, mode_distance=mode_distance, atr=atr)
