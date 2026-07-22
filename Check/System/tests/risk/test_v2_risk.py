"""Risk engine ATR stop bounds."""

from __future__ import annotations

from checktrader.config.models import PositionSizingConfig
from checktrader.domain.enums import RiskDecision, Side
from checktrader.risk.engine import approve_order
from tests.fixtures.helpers import EURUSD_SPECS


def test_buy_sl_above_entry_rejected() -> None:
    result = approve_order(
        side=Side.BUY,
        entry=1.10000,
        stop_loss=1.10100,
        specs=EURUSD_SPECS,
        sizing=PositionSizingConfig(),
        atr=0.001,
        maximum_stop_atr=2.5,
        free_margin=5_000,
    )
    assert result.decision is RiskDecision.INVALID_STOP


def test_sl_beyond_maximum_stop_atr_rejected() -> None:
    # distance 0.002, max = 1.0 * 0.001 = 0.001
    result = approve_order(
        side=Side.BUY,
        entry=1.10000,
        stop_loss=1.09800,
        specs=EURUSD_SPECS,
        sizing=PositionSizingConfig(),
        atr=0.001,
        maximum_stop_atr=1.0,
        free_margin=5_000,
    )
    assert result.decision is RiskDecision.INVALID_STOP
