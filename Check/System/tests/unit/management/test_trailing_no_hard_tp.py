"""ATR-adaptive SL/trail — same multipliers on NG and EURUSD; points/pips are display only."""

from __future__ import annotations

from datetime import UTC, datetime

from checktrader.config.loader import load_config
from checktrader.config.models import ManagementConfig
from checktrader.domain.enums import Decision, MarketRegime, ReasonCode, Side, StrategyType
from checktrader.domain.models import Position, SymbolSpecs
from checktrader.management.atr_stops import (
    distance_pips,
    distance_points,
    stop_target_distance,
    trail_lock_distance,
    uses_pip_quotation,
)
from checktrader.management.trailing import trailing_action
from checktrader.strategies.exits import hard_take_profit_price


def _ng_specs() -> SymbolSpecs:
    return SymbolSpecs("NATURALGAS", 3, 0.001, 0.001, 0.001, 0.01, 100.0, 0.01, 100.0, 0.0, 0.0)


def _eu_specs() -> SymbolSpecs:
    return SymbolSpecs("EURUSD", 5, 0.00001, 0.00001, 0.0001, 0.01, 100.0, 0.01, 100000.0, 0.0, 0.0)


def test_hard_take_profit_disabled_returns_none() -> None:
    assert hard_take_profit_price(entry=2.90, stop=2.88, side=Side.BUY, rr=1.5, enabled=False) is None


def test_same_atr_mult_adapts_across_symbols() -> None:
    """Sizing is ATR·mult; resulting points/pips differ because price scale differs."""
    cfg = load_config()
    ng_atr, eu_atr = 0.04, 0.0008
    ng = stop_target_distance(_ng_specs(), cfg.strategies, ng_atr)
    eu = stop_target_distance(_eu_specs(), cfg.strategies, eu_atr)
    assert abs(ng - ng_atr * cfg.strategies.force_stop_atr) < 1e-12
    assert abs(eu - eu_atr * cfg.strategies.force_stop_atr) < 1e-12
    # Display only
    assert distance_points(ng, 0.001) > 0
    assert distance_pips(eu, _eu_specs()) > 0
    assert uses_pip_quotation(_eu_specs()) is True
    assert uses_pip_quotation(_ng_specs()) is False


def test_trail_lock_is_atr_not_hard_points() -> None:
    cfg = ManagementConfig()
    atr = 0.04
    lock = trail_lock_distance(_ng_specs(), cfg, atr)
    assert abs(lock - atr * cfg.trailing_lock_atr) < 1e-12


def test_default_config_atr_only() -> None:
    cfg = load_config()
    assert cfg.strategies.force_stop_atr == 1.5
    assert cfg.strategies.min_stop_atr == 0.75
    assert "stop_target_points" not in type(cfg.strategies).model_fields
    assert cfg.management.trailing_lock_atr == 0.75
    assert cfg.management.trailing_start_atr == 0.50
    assert cfg.management.breakeven_trigger_atr == 0.75
    assert "trailing_lock_points" not in type(cfg.management).model_fields


def test_trailing_ratchets_on_atr() -> None:
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
        entry - atr * 1.5,
        None,
        datetime.now(UTC),
        StrategyType.BREAKOUT,
    )
    price = entry + lock * 1.05
    action = trailing_action(pos, price, atr, MarketRegime.TREND_UP, cfg, specs)
    assert action.decision is Decision.MODIFY
    assert action.reason is ReasonCode.TRAILING_MOVE
    assert abs((action.stop_loss or 0) - (price - lock)) < 1e-9
