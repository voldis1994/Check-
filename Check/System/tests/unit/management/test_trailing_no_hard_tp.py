"""Digit-aware SL/trail: 100 NG points vs 10 EURUSD pips."""

from __future__ import annotations

from datetime import UTC, datetime

from checktrader.config.loader import load_config
from checktrader.config.models import ManagementConfig, StrategiesConfig
from checktrader.domain.enums import Decision, MarketRegime, ReasonCode, Side, StrategyType
from checktrader.domain.models import Position, SymbolSpecs
from checktrader.management.atr_stops import (
    distance_pips,
    distance_points,
    pip_size,
    stop_target_distance,
    trail_lock_distance,
    uses_pip_quotation,
)
from checktrader.management.trailing import trailing_action
from checktrader.strategies.exits import hard_take_profit_price


def _ng_specs() -> SymbolSpecs:
    # NATURALGAS-style 3/4 digit, point=0.001
    return SymbolSpecs("NATURALGAS", 3, 0.001, 0.001, 0.001, 0.01, 100.0, 0.01, 100.0, 0.0, 0.0)


def _eu_specs() -> SymbolSpecs:
    # EURUSD 5-digit
    return SymbolSpecs("EURUSD", 5, 0.00001, 0.00001, 0.0001, 0.01, 100.0, 0.01, 100000.0, 0.0, 0.0)


def test_hard_take_profit_disabled_returns_none() -> None:
    assert hard_take_profit_price(entry=2.90, stop=2.88, side=Side.BUY, rr=1.5, enabled=False) is None


def test_quote_mode_by_digits() -> None:
    assert uses_pip_quotation(_eu_specs()) is True
    assert uses_pip_quotation(_ng_specs()) is False
    # 3-digit NATURALGAS must stay on POINTS (not JPY pip mode)
    ng3 = SymbolSpecs("NATURALGAS", 3, 0.001, 0.001, 0.001, 0.01, 100.0, 0.01, 100.0, 0.0, 0.0)
    assert uses_pip_quotation(ng3) is False
    jpy = SymbolSpecs("USDJPY", 3, 0.001, 0.001, 0.01, 0.01, 100.0, 0.01, 100000.0, 0.0, 0.0)
    assert uses_pip_quotation(jpy) is True
    assert pip_size(_eu_specs()) == 0.0001
    assert pip_size(_ng_specs()) == 0.001


def test_naturalgas_100_points_not_confused_with_fx() -> None:
    cfg = load_config()
    specs = _ng_specs()
    atr = 0.04
    dist = stop_target_distance(specs, cfg.strategies, atr)
    assert abs(distance_points(dist, specs.point) - 100.0) < 1e-6
    # Must NOT be interpreted as 10 "pips" on gas
    assert uses_pip_quotation(specs) is False


def test_eurusd_10_pips_five_digit() -> None:
    cfg = load_config()
    specs = _eu_specs()
    atr = 0.0008
    dist = stop_target_distance(specs, cfg.strategies, atr)
    assert abs(distance_pips(dist, specs) - 10.0) < 1e-6
    # 10 pips = 100 broker points on 5-digit
    assert abs(distance_points(dist, specs.point) - 100.0) < 1e-6


def test_trail_lock_points_vs_pips() -> None:
    mcfg = ManagementConfig()
    ng = trail_lock_distance(_ng_specs(), mcfg, atr_value=0.04)
    eu = trail_lock_distance(_eu_specs(), mcfg, atr_value=0.0008)
    assert abs(distance_points(ng, 0.001) - 40.0) < 1e-6
    assert abs(distance_pips(eu, _eu_specs()) - 8.0) < 1e-6


def test_default_config_digit_targets() -> None:
    cfg = load_config()
    assert cfg.strategies.stop_target_points == 100.0
    assert cfg.strategies.stop_target_pips == 10.0
    assert cfg.management.trailing_lock_points == 40.0
    assert cfg.management.trailing_lock_pips == 8.0


def test_trailing_uses_specs() -> None:
    cfg = ManagementConfig()
    specs = _ng_specs()
    atr = 0.04
    lock = trail_lock_distance(specs, cfg, atr)
    entry = 2.90
    pos = Position(
        "p1",
        "NATURALGAS",
        Side.BUY,
        0.02,
        entry,
        entry - 0.10,
        None,
        datetime.now(UTC),
        StrategyType.BREAKOUT,
    )
    price = entry + lock
    action = trailing_action(pos, price, atr, MarketRegime.TREND_UP, cfg, specs)
    assert action.decision is Decision.MODIFY
    assert action.reason is ReasonCode.TRAILING_MOVE
    assert action.stop_loss is not None
    assert abs(action.stop_loss - (price - lock)) < 1e-9


def test_strategies_defaults() -> None:
    s = StrategiesConfig()
    assert s.stop_target_points == 100.0
    assert s.stop_target_pips == 10.0
