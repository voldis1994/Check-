from __future__ import annotations

from engine.core.instance import Instance
from engine.protocol.models import StatusRecord
from engine.risk.metrics import (
    build_risk_context,
    compute_daily_loss_percent,
    compute_drawdown_percent,
)
from engine.state.instance_state import InstanceState


def _status(*, balance: float = 10000.0, equity: float = 10000.0) -> StatusRecord:
    return StatusRecord(
        schema_version="1.0.0",
        timestamp_utc="2026-07-07T06:00:00.000Z",
        account_id="12345",
        connected=True,
        trade_allowed=True,
        balance=balance,
        equity=equity,
        margin_free=9000.0,
        ea_version="1.0.0",
    )


def _instance_state(
    *,
    day_start_balance: float | None = None,
    peak_equity: float | None = None,
) -> InstanceState:
    state = InstanceState(instance=Instance(account_id="12345", symbol="EURUSD", magic=100001))
    if day_start_balance is not None:
        state.update_risk_metrics(day_start_balance=day_start_balance)
    if peak_equity is not None:
        state.update_risk_metrics(peak_equity=peak_equity)
    return state


def test_compute_drawdown_percent_uses_peak_equity_when_available() -> None:
    assert compute_drawdown_percent(balance=10000.0, equity=9000.0, peak_equity=10000.0) == 10.0


def test_compute_daily_loss_percent_uses_day_start_balance() -> None:
    assert compute_daily_loss_percent(equity=9700.0, day_start_balance=10000.0) == 3.0


def test_build_risk_context_reads_persisted_instance_state_metrics() -> None:
    context = build_risk_context(
        status=_status(balance=10000.0, equity=9500.0),
        instance_state=_instance_state(day_start_balance=10000.0, peak_equity=10000.0),
    )

    assert context.daily_loss_percent == 5.0
    assert context.drawdown_percent == 5.0


def test_build_risk_context_defaults_to_zero_without_persisted_metrics() -> None:
    context = build_risk_context(
        status=_status(balance=10000.0, equity=9000.0),
        instance_state=_instance_state(),
    )

    assert context.daily_loss_percent == 0.0
    assert context.drawdown_percent == 10.0
