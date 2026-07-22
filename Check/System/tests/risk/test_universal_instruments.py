"""Universal instrument coverage: Forex, Natural Gas, gold, indices."""

from __future__ import annotations

import pytest

from checktrader.config.models import PositionSizingConfig
from checktrader.domain.enums import RiskDecision, Side
from checktrader.domain.money import SymbolSpecs, money_per_price_unit, spread_price
from checktrader.observability.reason_codes import ReasonCode
from checktrader.position_management.atr_grid_trailing import atr_step_price, compute_grid_stop_loss
from checktrader.position_management.breakeven import calculate_be_stop_loss
from checktrader.risk.broker_constraints import round_price_to_tick
from checktrader.risk.engine import approve_order
from checktrader.risk.stop_loss import atr_to_price_distance


def _specs(
    *,
    symbol: str,
    digits: int,
    point: float,
    tick_size: float,
    tick_value: float,
    minimum_lot: float = 0.01,
    lot_step: float = 0.01,
) -> SymbolSpecs:
    return SymbolSpecs(
        symbol=symbol,
        digits=digits,
        point=point,
        tick_size=tick_size,
        tick_value=tick_value,
        minimum_lot=minimum_lot,
        maximum_lot=100.0,
        lot_step=lot_step,
        stop_level_points=0,
        freeze_level_points=0,
    )


INSTRUMENTS = [
    pytest.param(_specs(symbol="EURUSD", digits=5, point=0.00001, tick_size=0.00001, tick_value=1.0), id="forex"),
    pytest.param(_specs(symbol="NATGAS", digits=3, point=0.001, tick_size=0.001, tick_value=10.0), id="natgas"),
    pytest.param(_specs(symbol="XAUUSD", digits=2, point=0.01, tick_size=0.01, tick_value=1.0), id="gold"),
    pytest.param(_specs(symbol="US500", digits=1, point=0.1, tick_size=0.1, tick_value=1.0), id="index"),
]


@pytest.mark.parametrize("specs", INSTRUMENTS)
def test_fixed_lot_001_across_instruments(specs: SymbolSpecs) -> None:
    entry = 100.0 if specs.symbol != "EURUSD" else 1.10000
    if specs.symbol == "EURUSD":
        entry = 1.10000
        sl = 1.09800
        atr = 0.001
    elif specs.symbol == "NATGAS":
        entry = 3.500
        sl = 3.400
        atr = 0.050
    elif specs.symbol == "XAUUSD":
        entry = 2300.00
        sl = 2290.00
        atr = 5.0
    else:
        entry = 5000.0
        sl = 4980.0
        atr = 10.0
    result = approve_order(
        side=Side.BUY,
        entry=entry,
        stop_loss=sl,
        specs=specs,
        sizing=PositionSizingConfig(),
        atr=atr,
        maximum_stop_atr=5.0,
        free_margin=50_000,
        broker_server="Demo",
    )
    assert result.decision is RiskDecision.APPROVED
    assert result.volume == 0.01


@pytest.mark.parametrize("specs", INSTRUMENTS)
def test_atr_distance_rounds_to_tick(specs: SymbolSpecs) -> None:
    dist = atr_to_price_distance(0.050 if specs.symbol != "US500" else 5.0, 0.20, specs)
    assert dist > 0
    assert abs(dist / specs.tick_size - round(dist / specs.tick_size)) < 1e-9
    assert dist == round_price_to_tick(dist, specs.tick_size)


@pytest.mark.parametrize("specs", INSTRUMENTS)
def test_be_020_uses_tick_value_and_fixed_lot(specs: SymbolSpecs) -> None:
    open_px = 1.10000 if specs.symbol == "EURUSD" else 100.0 * specs.tick_size * 10
    if specs.symbol == "NATGAS":
        open_px = 3.500
    elif specs.symbol == "XAUUSD":
        open_px = 2300.00
    elif specs.symbol == "US500":
        open_px = 5000.0
    be, reason = calculate_be_stop_loss(
        side=Side.BUY,
        open_price=open_px,
        volume=0.01,
        specs=specs,
        be_net_profit_money=0.20,
        swap=0.0,
        commission=0.0,
    )
    assert reason is ReasonCode.BE_CALCULATED
    assert be is not None
    mppu = money_per_price_unit(tick_value=specs.tick_value, tick_size=specs.tick_size, volume=0.01)
    expected = open_px + 0.20 / mppu
    assert abs(be - round_price_to_tick(expected, specs.tick_size)) <= specs.tick_size + 1e-12


@pytest.mark.parametrize("specs", INSTRUMENTS)
def test_atr_trailing_grid_never_worsens(specs: SymbolSpecs) -> None:
    atr = 0.050 if specs.digits >= 3 else 5.0
    if specs.symbol == "EURUSD":
        atr = 0.0015
        be = 1.10020
        price = 1.10150
    elif specs.symbol == "NATGAS":
        atr = 0.050
        be = 3.510
        price = 3.560
    elif specs.symbol == "XAUUSD":
        atr = 5.0
        be = 2301.00
        price = 2310.00
    else:
        atr = 5.0
        be = 5001.0
        price = 5020.0
    step = atr_step_price(atr=atr, trailing_step_atr=0.20, specs=specs)
    assert step >= specs.tick_size - 1e-12
    sl, steps = compute_grid_stop_loss(
        side=Side.BUY,
        confirmed_be_sl=be,
        current_price=price,
        atr=atr,
        trailing_step_atr=0.20,
        specs=specs,
    )
    if sl is not None:
        assert steps >= 1
        assert sl > be


def test_spread_price_is_ask_minus_bid() -> None:
    assert spread_price(bid=2300.00, ask=2300.25) == pytest.approx(0.25)
    assert spread_price(bid=3.500, ask=3.503) == pytest.approx(0.003)
