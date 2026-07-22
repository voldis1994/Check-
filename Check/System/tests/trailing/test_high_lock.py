"""High-lock unit tests."""

from __future__ import annotations

from checktrader.config.models import HighLockConfig
from checktrader.domain.enums import Side
from checktrader.domain.money import SymbolSpecs, price_tolerance
from checktrader.position_management.high_lock import calculate_high_lock_sl
from tests.fixtures.helpers import EURUSD_SPECS


def test_high_lock_activation_and_ratio() -> None:
    # peak 1.0, lock 60% → 0.60 money; mppu=1000 → 0.00060 above open
    sl = calculate_high_lock_sl(
        side=Side.BUY,
        open_price=1.10000,
        volume=0.01,
        specs=EURUSD_SPECS,
        peak_net_profit=1.0,
        swap=0.0,
        commission=0.0,
        config=HighLockConfig(enabled=True, activation_peak_profit_money=1.0, lock_ratio=0.6),
        be_anchor=None,
        atr=0.0015,
        trailing_step_atr=0.20,
        tolerance=price_tolerance(point=0.00001, digits=5),
    )
    assert sl == 1.10060


def test_high_lock_not_before_activation() -> None:
    sl = calculate_high_lock_sl(
        side=Side.BUY,
        open_price=1.10000,
        volume=0.01,
        specs=EURUSD_SPECS,
        peak_net_profit=0.5,
        swap=0.0,
        commission=0.0,
        config=HighLockConfig(enabled=True, activation_peak_profit_money=1.0, lock_ratio=0.6),
        be_anchor=None,
        atr=0.0015,
        trailing_step_atr=0.20,
        tolerance=price_tolerance(point=0.00001, digits=5),
    )
    assert sl is None


def test_high_lock_snaps_to_grid_and_no_worsen() -> None:
    tol = price_tolerance(point=0.00001, digits=5)
    be = 1.10020
    sl = calculate_high_lock_sl(
        side=Side.BUY,
        open_price=1.10000,
        volume=0.01,
        specs=EURUSD_SPECS,
        peak_net_profit=2.0,  # lock 1.20 → raw 1.10120
        swap=0.0,
        commission=0.0,
        config=HighLockConfig(enabled=True, activation_peak_profit_money=1.0, lock_ratio=0.6),
        be_anchor=be,
        atr=0.0015,
        trailing_step_atr=0.20,
        tolerance=tol,
    )
    # snap to floor steps from be: (1.10120-1.10020)/0.00030 = 3.333 → 3 steps → 1.10110
    assert sl == 1.10110
    assert sl > be


def test_high_lock_missing_metadata() -> None:
    specs = SymbolSpecs(
        symbol="EURUSD",
        digits=5,
        point=0.00001,
        pip_size=0.0001,
        tick_size=0.0,
        tick_value=0.0,
        minimum_lot=0.01,
        maximum_lot=100.0,
        lot_step=0.01,
        stop_level_points=0,
        freeze_level_points=0,
    )
    sl = calculate_high_lock_sl(
        side=Side.SELL,
        open_price=1.10000,
        volume=0.01,
        specs=specs,
        peak_net_profit=2.0,
        swap=0.0,
        commission=0.0,
        config=HighLockConfig(enabled=True, activation_peak_profit_money=1.0, lock_ratio=0.6),
        be_anchor=None,
        atr=0.0015,
        trailing_step_atr=0.20,
        tolerance=0.00002,
    )
    assert sl is None
