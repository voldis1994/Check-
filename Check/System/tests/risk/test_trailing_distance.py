from __future__ import annotations
from datetime import datetime, timezone
import pytest
from engine.normalizer.market_normalizer import NormalizedMarketBar
from engine.protocol.errors import ValidationError
from engine.protocol.models import InstanceDefinition, TradeManagementSettings
from engine.risk.trailing_distance import TRAILING_MODE_ATR_MULTIPLE, TRAILING_MODE_FIXED_PIPS, TRAILING_MODE_SL_FRACTION, apply_spread_floor, compute_atr, compute_mode_distance, resolve_structure_buffer, resolve_trailing_distances, resolve_trailing_params

def _bars(*, symbol: str='EURUSD', point: float=1e-05, start: float=1.1, step: float=0.0002, count: int=20) -> tuple[NormalizedMarketBar, ...]:
    bars: list[NormalizedMarketBar] = []
    for index in range(count):
        open_price = start + index * step
        high = open_price + step
        low = open_price - step * 0.5
        close = open_price + step * 0.25
        bars.append(NormalizedMarketBar(time_utc=datetime(2026, 7, 7, 6, index % 60, tzinfo=timezone.utc), open=open_price, high=high, low=low, close=close, volume=100.0, symbol=symbol, timeframe='M1', digits=5 if point < 0.001 else 2, point=point, bar_index=index))
    return tuple(bars)

def _settings(**overrides: object) -> TradeManagementSettings:
    values: dict[str, object] = {'enabled': True, 'allow_close': False, 'use_fixed_take_profit': False, 'breakeven_progress_ratio': 0.25, 'partial_close_progress_ratio': 0.75, 'partial_close_volume_ratio': 0.5, 'time_stop_max_bars': 30, 'trailing_lookback_bars': 8, 'trailing_step_pips': 4.0, 'trailing_mode': TRAILING_MODE_ATR_MULTIPLE, 'trailing_atr_mult': 1.2, 'trailing_atr_period': 14, 'trailing_sl_fraction': 0.5, 'trailing_spread_floor_mult': 1.2}
    values.update(overrides)
    return TradeManagementSettings(**values)

def test_apply_spread_floor_raises_trail_when_spread_larger() -> None:
    assert apply_spread_floor(0.0003, spread=0.0003, floor_mult=1.2) == pytest.approx(0.00036)
    assert apply_spread_floor(0.0005, spread=0.0002, floor_mult=1.2) == pytest.approx(0.0005)

def test_resolve_structure_buffer_uses_spread_when_larger() -> None:
    assert resolve_structure_buffer(configured_buffer=0.0002, spread=0.00035) == pytest.approx(0.00035)
    assert resolve_structure_buffer(configured_buffer=0.0005, spread=0.0002) == pytest.approx(0.0005)

def test_fixed_pips_mode_eurusd() -> None:
    distance = compute_mode_distance(mode=TRAILING_MODE_FIXED_PIPS, step_pips=4.0, pip=0.0001, atr=0.0, atr_mult=1.2, entry_price=None, stop_loss=None, sl_fraction=0.5)
    assert distance == pytest.approx(0.0004)

def test_atr_mode_scales_for_gold_without_pip_dependency() -> None:
    gold_bars = _bars(symbol='XAUUSD', point=0.01, start=2300.0, step=1.5, count=20)
    atr = compute_atr(gold_bars, period=14)
    assert atr > 1.0
    distance = compute_mode_distance(mode=TRAILING_MODE_ATR_MULTIPLE, step_pips=4.0, pip=0.01, atr=atr, atr_mult=1.2, entry_price=None, stop_loss=None, sl_fraction=0.5)
    assert distance == pytest.approx(atr * 1.2)
    floored = apply_spread_floor(distance, spread=0.80, floor_mult=1.2)
    assert floored == pytest.approx(distance)

def test_atr_mode_falls_back_to_fixed_pips_when_atr_unavailable() -> None:
    distance = compute_mode_distance(mode=TRAILING_MODE_ATR_MULTIPLE, step_pips=4.0, pip=0.0001, atr=0.0, atr_mult=1.2, entry_price=None, stop_loss=None, sl_fraction=0.5)
    assert distance == pytest.approx(0.0004)

def test_sl_fraction_mode_uses_trade_risk() -> None:
    distance = compute_mode_distance(mode=TRAILING_MODE_SL_FRACTION, step_pips=4.0, pip=0.0001, atr=0.0, atr_mult=1.2, entry_price=1.1, stop_loss=1.098, sl_fraction=0.5)
    assert distance == pytest.approx(0.001)

def test_spread_floor_protects_tight_fixed_trail_on_eurusd() -> None:
    params = resolve_trailing_params(settings=_settings(trailing_mode=TRAILING_MODE_FIXED_PIPS, trailing_step_pips=3.0), analysis_stop_loss_buffer=0.0002)
    distances = resolve_trailing_distances(params=params, pip=0.0001, market_bars=_bars(count=5), current_spread=0.0003, entry_price=1.1, stop_loss=1.098)
    assert distances.mode_distance == pytest.approx(0.0003)
    assert distances.price_trail_distance == pytest.approx(0.00036)
    assert distances.trailing_buffer == pytest.approx(0.0003)

def test_instance_overrides_replace_global_trailing_params() -> None:
    settings = _settings(trailing_mode=TRAILING_MODE_FIXED_PIPS, trailing_step_pips=4.0, trailing_lookback_bars=8)
    definition = InstanceDefinition(account_id='231054', symbol='XAUUSD', magic=100002, enabled=True, trailing_mode=TRAILING_MODE_ATR_MULTIPLE, trailing_atr_mult=1.5, trailing_lookback_bars=12, stop_loss_buffer=0.5)
    params = resolve_trailing_params(settings=settings, analysis_stop_loss_buffer=0.0002, instance_definition=definition)
    assert params.mode == TRAILING_MODE_ATR_MULTIPLE
    assert params.atr_mult == pytest.approx(1.5)
    assert params.lookback_bars == 12
    assert params.stop_loss_buffer == pytest.approx(0.5)
    assert params.step_pips == pytest.approx(4.0)

def test_resolve_trailing_params_rejects_unknown_mode() -> None:
    with pytest.raises(ValidationError, match='trailing_mode'):
        resolve_trailing_params(settings=_settings(trailing_mode='nope'), analysis_stop_loss_buffer=0.0002)

def test_gold_and_fx_share_atr_path_with_spread_floor() -> None:
    fx_params = resolve_trailing_params(settings=_settings(), analysis_stop_loss_buffer=0.0002)
    gold_params = resolve_trailing_params(settings=_settings(), analysis_stop_loss_buffer=0.0002)
    fx = resolve_trailing_distances(params=fx_params, pip=0.0001, market_bars=_bars(count=20), current_spread=0.0002, entry_price=1.1, stop_loss=1.098)
    gold = resolve_trailing_distances(params=gold_params, pip=0.01, market_bars=_bars(symbol='XAUUSD', point=0.01, start=2300.0, step=1.2, count=20), current_spread=0.80, entry_price=2300.0, stop_loss=2295.0)
    assert fx.price_trail_distance >= 0.0002 * 1.2
    assert gold.price_trail_distance >= 0.80 * 1.2
    assert gold.price_trail_distance > fx.price_trail_distance
