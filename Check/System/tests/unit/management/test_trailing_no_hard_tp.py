"""ATR stops — sanitize corrupt FX ATR (294-pip EURUSD SL bug)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from checktrader.config.loader import load_config
from checktrader.config.models import ManagementConfig
from checktrader.domain.enums import Decision, MarketRegime, Side, StrategyType
from checktrader.domain.models import Candle, Position, SymbolSpecs
from checktrader.management.atr_stops import (
    distance_pips,
    sanitize_atr,
    stop_target_distance,
)
from checktrader.management.exits import regime_flip_action
from checktrader.management.trailing import trailing_action
from checktrader.strategies.exits import hard_take_profit_price


def _eu_specs() -> SymbolSpecs:
    return SymbolSpecs("EURUSD", 5, 0.00001, 0.00001, 0.0001, 0.01, 100.0, 0.01, 100000.0, 0.0, 0.0)


def _ng_specs() -> SymbolSpecs:
    return SymbolSpecs("NATURALGAS", 3, 0.001, 0.001, 0.001, 0.01, 100.0, 0.01, 100.0, 0.0, 0.0)


def _bar(i: int, *, tr: float = 0.04) -> Candle:
    t = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=i)
    o = 3.0
    return Candle(t, o, o + tr, o - 0.001, o + tr * 0.2, 1.0, True)


def test_hard_take_profit_disabled_returns_none() -> None:
    assert hard_take_profit_price(entry=2.90, stop=2.88, side=Side.BUY, rr=1.5, enabled=False) is None


def test_eurusd_294_pip_atr_is_sanitized_to_about_10_pips() -> None:
    """Live bug: entry 1.13714 SL 1.16654 = 0.0294 = 294 pips."""
    cfg = load_config()
    specs = _eu_specs()
    mid = 1.13714
    garbage_atr = 0.0294  # what produced the 294-pip SL at 1.0×ATR
    dist = stop_target_distance(specs, cfg.strategies, garbage_atr, mid=mid)
    pips = distance_pips(dist, specs)
    assert pips < 20.0
    assert abs(pips - 10.0) < 2.0  # ~10 pips (0.1% of price × 1.0 ATR mult)


def test_sane_eurusd_atr_passes_through() -> None:
    cfg = load_config()
    specs = _eu_specs()
    mid = 1.13714
    atr = 0.0008  # ~8 pips ATR
    cleaned = sanitize_atr(atr, mid=mid, specs=specs)
    assert cleaned is not None
    assert abs(cleaned - 0.0008) < 1e-12
    dist = stop_target_distance(specs, cfg.strategies, atr, mid=mid)
    assert abs(distance_pips(dist, specs) - 8.0) < 0.5


def test_default_config_no_instant_regime_flip() -> None:
    cfg = load_config()
    assert cfg.management.exit_on_regime_flip is False
    assert cfg.strategies.force_stop_atr == 1.0


def test_regime_flip_disabled_keeps_fresh_trade() -> None:
    cfg = ManagementConfig(exit_on_regime_flip=False)
    pos = Position(
        "p1",
        "EURUSD",
        Side.SELL,
        0.02,
        1.13714,
        1.138,
        None,
        datetime.now(UTC),
        StrategyType.BREAKOUT,
    )
    assert regime_flip_action(pos, MarketRegime.TREND_UP, cfg).decision is Decision.HOLD


def test_trailing_still_works() -> None:
    cfg = ManagementConfig()
    specs = _ng_specs()
    atr = 0.04
    from checktrader.management.atr_stops import trail_lock_distance

    lock = trail_lock_distance(specs, cfg, atr, mid=3.0)
    entry = 2.90
    pos = Position(
        "p1",
        "NATURALGAS",
        Side.BUY,
        0.02,
        entry,
        entry - atr,
        None,
        datetime.now(UTC),
        StrategyType.BREAKOUT,
    )
    action = trailing_action(pos, entry + lock * 1.05, atr, MarketRegime.TREND_UP, cfg, specs)
    assert action.decision is Decision.MODIFY


def test_robust_atr_caps_spike() -> None:
    from checktrader.management.atr_stops import robust_atr

    bars = [_bar(i, tr=0.04) for i in range(40)]
    bars.append(_bar(40, tr=0.40))
    value = robust_atr(bars, 14)
    assert value is not None
    assert value < 0.12
