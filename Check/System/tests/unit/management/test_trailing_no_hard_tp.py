"""Trailing exit without hard take-profit."""

from __future__ import annotations

from checktrader.config.loader import load_config
from checktrader.config.models import ManagementConfig
from checktrader.domain.enums import Decision, MarketRegime, ReasonCode, Side, StrategyType
from checktrader.domain.models import Position
from checktrader.management.trailing import trailing_action
from checktrader.strategies.exits import hard_take_profit_price


def test_hard_take_profit_disabled_returns_none() -> None:
    assert hard_take_profit_price(entry=2.90, stop=2.88, side=Side.BUY, rr=1.5, enabled=False) is None


def test_hard_tp_enabled_computes_rr() -> None:
    tp = hard_take_profit_price(entry=2.90, stop=2.88, side=Side.BUY, rr=1.5, enabled=True)
    assert tp is not None
    assert abs(tp - 2.93) < 1e-9
    tp_sell = hard_take_profit_price(entry=2.90, stop=2.92, side=Side.SELL, rr=1.5, enabled=True)
    assert tp_sell is not None
    assert abs(tp_sell - 2.87) < 1e-9


def test_default_config_has_no_hard_tp() -> None:
    cfg = load_config()
    assert cfg.management.hard_take_profit is False
    assert cfg.management.trailing_start_rr < 1.0


def test_trailing_moves_stop_before_old_hard_tp_rr() -> None:
    """Trail must activate well before the old 1.5R hard-TP choke point."""
    from datetime import UTC, datetime

    cfg = ManagementConfig()
    pos = Position(
        "p1",
        "NATURALGAS",
        Side.BUY,
        0.02,
        2.90,
        2.88,
        None,
        datetime.now(UTC),
        StrategyType.BREAKOUT,
    )
    # 0.4R move with tight ATR trail
    price = 2.90 + 0.4 * (2.90 - 2.88)
    action = trailing_action(pos, price, atr_value=0.01, regime=MarketRegime.TREND_UP, config=cfg)
    assert action.decision is Decision.MODIFY
    assert action.reason is ReasonCode.TRAILING_MOVE
    assert action.stop_loss is not None
    assert action.stop_loss > 2.88
