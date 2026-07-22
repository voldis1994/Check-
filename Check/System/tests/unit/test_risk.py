"""Risk engine tests."""

from __future__ import annotations

from checktrader.config.models import RiskConfig
from checktrader.domain.enums import RiskDecision, Side
from checktrader.domain.money import SymbolSpecs
from checktrader.risk.engine import approve_order
from tests.fixtures.helpers import EURUSD_SPECS


def test_fixed_lot_approved() -> None:
    risk = RiskConfig(sizing_mode="fixed_lot", fixed_lot=0.01, maximum_stop_loss_pips=50)
    result = approve_order(
        side=Side.BUY,
        entry=1.10000,
        stop_loss=1.09800,
        specs=EURUSD_SPECS,
        risk=risk,
        equity=10_000,
        free_margin=5_000,
    )
    assert result.decision is RiskDecision.APPROVED
    assert result.volume == 0.01
    assert result.take_profit is None
    with_tp = approve_order(
        side=Side.BUY,
        entry=1.10000,
        stop_loss=1.09800,
        specs=EURUSD_SPECS,
        risk=risk,
        equity=10_000,
        free_margin=5_000,
        fixed_take_profit_enabled=True,
    )
    assert with_tp.take_profit is not None
    assert with_tp.take_profit > 1.10000


def test_risk_percent_sizing() -> None:
    risk = RiskConfig(
        sizing_mode="risk_percent",
        risk_percent=1.0,
        fixed_lot=None,
        maximum_stop_loss_pips=50,
        allow_lot_normalization=True,
    )
    result = approve_order(
        side=Side.BUY,
        entry=1.10000,
        stop_loss=1.09900,  # 10 pips
        specs=EURUSD_SPECS,
        risk=risk,
        equity=10_000,
        free_margin=5_000,
    )
    assert result.decision is RiskDecision.APPROVED
    assert result.volume >= EURUSD_SPECS.minimum_lot


def test_lot_outside_min_max() -> None:
    risk = RiskConfig(sizing_mode="fixed_lot", fixed_lot=0.001, maximum_stop_loss_pips=50)
    result = approve_order(
        side=Side.BUY,
        entry=1.10000,
        stop_loss=1.09800,
        specs=EURUSD_SPECS,
        risk=risk,
        equity=10_000,
        free_margin=5_000,
    )
    assert result.decision is RiskDecision.INVALID_VOLUME


def test_lot_step_mismatch() -> None:
    risk = RiskConfig(
        sizing_mode="fixed_lot", fixed_lot=0.015, maximum_stop_loss_pips=50, allow_lot_normalization=False
    )
    specs = SymbolSpecs(
        symbol="EURUSD",
        digits=5,
        point=0.00001,
        pip_size=0.0001,
        tick_size=0.00001,
        tick_value=1.0,
        minimum_lot=0.01,
        maximum_lot=100.0,
        lot_step=0.01,
        stop_level_points=0,
        freeze_level_points=0,
    )
    result = approve_order(
        side=Side.BUY,
        entry=1.10000,
        stop_loss=1.09800,
        specs=specs,
        risk=risk,
        equity=10_000,
        free_margin=5_000,
    )
    assert result.decision is RiskDecision.INVALID_VOLUME


def test_margin_insufficient() -> None:
    risk = RiskConfig(sizing_mode="fixed_lot", fixed_lot=0.01, maximum_stop_loss_pips=50)
    result = approve_order(
        side=Side.BUY,
        entry=1.10000,
        stop_loss=1.09800,
        specs=EURUSD_SPECS,
        risk=risk,
        equity=10_000,
        free_margin=0.0,
    )
    assert result.decision is RiskDecision.MARGIN_INSUFFICIENT


def test_invalid_sl_buy_above_entry() -> None:
    risk = RiskConfig(sizing_mode="fixed_lot", fixed_lot=0.01, maximum_stop_loss_pips=50)
    result = approve_order(
        side=Side.BUY,
        entry=1.10000,
        stop_loss=1.10100,
        specs=EURUSD_SPECS,
        risk=risk,
        equity=10_000,
        free_margin=5_000,
    )
    assert result.decision is RiskDecision.INVALID_STOP


def test_missing_tick_data() -> None:
    risk = RiskConfig(sizing_mode="fixed_lot", fixed_lot=0.01, maximum_stop_loss_pips=50)
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
    result = approve_order(
        side=Side.SELL,
        entry=1.10000,
        stop_loss=1.10200,
        specs=specs,
        risk=risk,
        equity=10_000,
        free_margin=5_000,
    )
    assert result.decision is RiskDecision.SYMBOL_SPEC_MISSING
