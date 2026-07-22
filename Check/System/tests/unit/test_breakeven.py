"""Breakeven calculation tests."""

from __future__ import annotations

from checktrader.domain.enums import Side
from checktrader.domain.money import SymbolSpecs
from checktrader.observability.reason_codes import ReasonCode
from checktrader.position_management.breakeven import calculate_be_stop_loss
from tests.fixtures.helpers import EURUSD_SPECS


def test_be_buy_net_020_lot_001_five_digits() -> None:
    sl, reason = calculate_be_stop_loss(
        side=Side.BUY,
        open_price=1.10000,
        volume=0.01,
        specs=EURUSD_SPECS,
        be_net_profit_money=0.20,
        swap=0.0,
        commission=0.0,
    )
    assert reason is ReasonCode.BE_CALCULATED
    assert sl == 1.10020


def test_be_sell_net_020_with_commission_swap() -> None:
    # required_gross = 0.20 - (-0.05) - (-0.10) = 0.35; mppu=1000 → 0.00035
    sl, reason = calculate_be_stop_loss(
        side=Side.SELL,
        open_price=1.10000,
        volume=0.01,
        specs=EURUSD_SPECS,
        be_net_profit_money=0.20,
        swap=-0.05,
        commission=-0.10,
    )
    assert reason is ReasonCode.BE_CALCULATED
    assert sl == 1.09965


def test_be_buy_lot_010() -> None:
    sl, reason = calculate_be_stop_loss(
        side=Side.BUY,
        open_price=1.10000,
        volume=0.10,
        specs=EURUSD_SPECS,
        be_net_profit_money=0.20,
        swap=0.0,
        commission=0.0,
    )
    assert reason is ReasonCode.BE_CALCULATED
    assert sl == 1.10002


def test_be_missing_tick_value() -> None:
    specs = SymbolSpecs(
        symbol="EURUSD",
        digits=5,
        point=0.00001,
        pip_size=0.0001,
        tick_size=0.00001,
        tick_value=0.0,
        minimum_lot=0.01,
        maximum_lot=100.0,
        lot_step=0.01,
        stop_level_points=0,
        freeze_level_points=0,
    )
    sl, reason = calculate_be_stop_loss(
        side=Side.BUY,
        open_price=1.10000,
        volume=0.01,
        specs=specs,
        be_net_profit_money=0.20,
        swap=0.0,
        commission=0.0,
    )
    assert sl is None
    assert reason is ReasonCode.BE_PRICE_METADATA_MISSING
