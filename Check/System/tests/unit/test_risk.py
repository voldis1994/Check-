"""Fixed-lot risk engine tests."""

from __future__ import annotations

from checktrader.config.models import PositionSizingConfig
from checktrader.domain.enums import RiskDecision, Side
from checktrader.domain.money import SymbolSpecs
from checktrader.risk.engine import approve_order
from tests.fixtures.helpers import EURUSD_SPECS


def _sizing(lot: float = 0.01) -> PositionSizingConfig:
    return PositionSizingConfig(mode="fixed_lot", fixed_lot=lot, allow_broker_lot_normalization=False)


def _approve(**kwargs: object):
    defaults = dict(
        side=Side.BUY,
        entry=1.10000,
        stop_loss=1.09800,
        specs=EURUSD_SPECS,
        sizing=_sizing(),
        atr=0.00100,
        maximum_stop_atr=2.5,
        free_margin=5_000,
        broker_server="Demo-Server",
    )
    defaults.update(kwargs)
    return approve_order(**defaults)  # type: ignore[arg-type]


def test_fixed_lot_approved() -> None:
    result = _approve()
    assert result.decision is RiskDecision.APPROVED
    assert result.volume == 0.01
    assert result.take_profit is None
    with_tp = _approve(fixed_take_profit_enabled=True, minimum_reward_risk=1.5)
    assert with_tp.take_profit is not None
    assert with_tp.take_profit > 1.10000


def test_equity_does_not_change_lot() -> None:
    a = _approve()
    # equity is intentionally not an approve_order parameter anymore
    b = _approve(free_margin=50_000)
    assert a.volume == b.volume == 0.01


def test_sl_distance_does_not_change_lot() -> None:
    a = _approve(stop_loss=1.09900)
    b = _approve(stop_loss=1.09850)
    assert a.volume == b.volume == 0.01


def test_atr_does_not_change_lot() -> None:
    a = _approve(atr=0.001)
    b = _approve(atr=0.010)
    assert a.volume == b.volume == 0.01


def test_min_lot_001_allowed() -> None:
    result = _approve()
    assert result.decision is RiskDecision.APPROVED


def test_min_lot_010_rejects_001() -> None:
    specs = SymbolSpecs(
        symbol="EURUSD",
        digits=5,
        point=0.00001,
        pip_size=0.0001,
        tick_size=0.00001,
        tick_value=1.0,
        minimum_lot=0.10,
        maximum_lot=100.0,
        lot_step=0.10,
        stop_level_points=0,
        freeze_level_points=0,
    )
    result = _approve(specs=specs)
    assert result.decision is RiskDecision.FIXED_LOT_NOT_SUPPORTED
    assert result.requested_lot == 0.01
    assert result.minimum_lot == 0.10
    assert result.lot_step == 0.10
    assert result.volume == 0.0


def test_lot_step_001_ok() -> None:
    assert _approve().decision is RiskDecision.APPROVED


def test_lot_step_010_rejects_001() -> None:
    specs = SymbolSpecs(
        symbol="EURUSD",
        digits=5,
        point=0.00001,
        pip_size=0.0001,
        tick_size=0.00001,
        tick_value=1.0,
        minimum_lot=0.01,
        maximum_lot=100.0,
        lot_step=0.10,
        stop_level_points=0,
        freeze_level_points=0,
    )
    result = _approve(specs=specs)
    assert result.decision is RiskDecision.FIXED_LOT_NOT_SUPPORTED
    assert "lot_step" in result.reason


def test_margin_insufficient_for_fixed_lot() -> None:
    result = _approve(free_margin=0.0)
    assert result.decision is RiskDecision.MARGIN_INSUFFICIENT_FOR_FIXED_LOT
    assert result.volume == 0.0


def test_never_auto_resize_lot() -> None:
    specs = SymbolSpecs(
        symbol="EURUSD",
        digits=5,
        point=0.00001,
        pip_size=0.0001,
        tick_size=0.00001,
        tick_value=1.0,
        minimum_lot=0.10,
        maximum_lot=100.0,
        lot_step=0.10,
        stop_level_points=0,
        freeze_level_points=0,
    )
    result = _approve(specs=specs)
    assert result.volume == 0.0
    assert result.requested_lot == 0.01


def test_invalid_sl_buy_above_entry() -> None:
    result = _approve(stop_loss=1.10100)
    assert result.decision is RiskDecision.INVALID_STOP


def test_sl_exceeds_maximum_stop_atr() -> None:
    result = _approve(atr=0.00010, maximum_stop_atr=1.0, stop_loss=1.09800)
    assert result.decision is RiskDecision.INVALID_STOP


def test_missing_tick_data() -> None:
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
    result = _approve(side=Side.SELL, stop_loss=1.10200, specs=specs)
    assert result.decision is RiskDecision.SYMBOL_SPEC_MISSING
