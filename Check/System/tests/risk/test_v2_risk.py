"""Risk package tests (v2) — sizing already covered in unit; keep package entry."""

from __future__ import annotations

from checktrader.config.models import RiskConfig
from checktrader.domain.enums import RiskDecision, Side
from checktrader.risk.engine import approve_order
from tests.fixtures.helpers import EURUSD_SPECS


def test_sell_invalid_sl_below_entry() -> None:
    risk = RiskConfig(sizing_mode="fixed_lot", fixed_lot=0.01, maximum_stop_loss_pips=50)
    result = approve_order(
        side=Side.SELL,
        entry=1.10000,
        stop_loss=1.09900,
        specs=EURUSD_SPECS,
        risk=risk,
        equity=10_000,
        free_margin=5_000,
    )
    assert result.decision is RiskDecision.INVALID_STOP


def test_max_stop_loss_pips_enforced() -> None:
    risk = RiskConfig(sizing_mode="fixed_lot", fixed_lot=0.01, maximum_stop_loss_pips=10)
    result = approve_order(
        side=Side.BUY,
        entry=1.10000,
        stop_loss=1.09800,  # 20 pips
        specs=EURUSD_SPECS,
        risk=risk,
        equity=10_000,
        free_margin=5_000,
    )
    assert result.decision is RiskDecision.INVALID_STOP
