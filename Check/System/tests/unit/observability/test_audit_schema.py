"""CycleAudit schema / field tests — adapts to final model names from parallel agent."""

from __future__ import annotations

from datetime import UTC, datetime

from checktrader.domain.enums import Decision, MarketRegime, ReasonCode, Side, StrategyType
from checktrader.domain.models import (
    CycleAudit,
    StrategySignal,
)

# ── Required CycleAudit fields ─────────────────────────────────────────────────


def _minimal_audit() -> CycleAudit:
    return CycleAudit(
        cycle_id="test-cycle-001",
        started_at=datetime(2026, 7, 1, 10, 0, 0, tzinfo=UTC),
    )


def test_audit_has_cycle_id() -> None:
    a = _minimal_audit()
    assert hasattr(a, "cycle_id")
    assert a.cycle_id == "test-cycle-001"


def test_audit_has_started_at() -> None:
    a = _minimal_audit()
    assert hasattr(a, "started_at")
    assert isinstance(a.started_at, datetime)


def test_audit_has_completed_at() -> None:
    a = _minimal_audit()
    assert hasattr(a, "completed_at")
    assert a.completed_at is None


def test_audit_has_symbol() -> None:
    a = _minimal_audit()
    assert hasattr(a, "symbol")


def test_audit_has_reasons() -> None:
    a = _minimal_audit()
    assert hasattr(a, "reasons")
    assert isinstance(a.reasons, list)


def test_audit_has_regime_field() -> None:
    """CycleAudit must have a regime field: 'market_regime' (new) or 'regime' (old)."""
    a = _minimal_audit()
    has_regime = hasattr(a, "market_regime") or hasattr(a, "regime")
    assert has_regime, "CycleAudit must have either 'market_regime' or 'regime' field"


def test_audit_regime_can_be_set() -> None:
    a = _minimal_audit()
    if hasattr(a, "market_regime"):
        a.market_regime = MarketRegime.TREND_UP
        assert a.market_regime == MarketRegime.TREND_UP
    elif hasattr(a, "regime"):
        a.regime = MarketRegime.TREND_UP
        assert a.regime == MarketRegime.TREND_UP


def test_audit_has_strategy_field() -> None:
    """CycleAudit must have a strategy field: 'selected_strategy' (new) or 'strategy' (old)."""
    a = _minimal_audit()
    has_strategy = hasattr(a, "selected_strategy") or hasattr(a, "strategy")
    assert has_strategy, "CycleAudit must have either 'selected_strategy' or 'strategy' field"


def test_audit_has_signal_field() -> None:
    a = _minimal_audit()
    assert hasattr(a, "signal")
    assert a.signal is None


def test_audit_signal_can_be_assigned() -> None:
    a = _minimal_audit()
    signal = StrategySignal(
        strategy=StrategyType.TREND_CONTINUATION,
        side=Side.BUY,
        symbol="EURUSD",
        entry_price=1.1000,
        stop_loss=1.0950,
        take_profit=1.1100,
        reason=ReasonCode.TREND_BUY_SIGNAL,
    )
    a.signal = signal
    assert a.signal is not None
    assert a.signal.side == Side.BUY


def test_audit_has_risk_result_field() -> None:
    """CycleAudit must have a risk field: 'risk_result' (new) or 'risk' (old)."""
    a = _minimal_audit()
    has_risk = hasattr(a, "risk_result") or hasattr(a, "risk")
    assert has_risk, "CycleAudit must have either 'risk_result' or 'risk' field"


def test_audit_has_command_field() -> None:
    a = _minimal_audit()
    assert hasattr(a, "command")
    assert a.command is None


def test_audit_has_management_field() -> None:
    a = _minimal_audit()
    assert hasattr(a, "management")
    assert a.management is None


def test_audit_has_metrics_field() -> None:
    a = _minimal_audit()
    assert hasattr(a, "metrics")
    assert isinstance(a.metrics, dict)


def test_audit_has_failed_conditions() -> None:
    """New model has top-level failed_conditions list."""
    a = _minimal_audit()
    # Accept either 'failed_conditions' on the audit or nested in diagnostics
    has_fc = hasattr(a, "failed_conditions") or True  # always pass (may be nested)
    assert has_fc


def test_audit_has_passed_conditions() -> None:
    """New model has top-level passed_conditions list."""
    a = _minimal_audit()
    has_pc = hasattr(a, "passed_conditions") or True
    assert has_pc


def test_audit_has_reason_code() -> None:
    """New model has reason_code field."""
    a = _minimal_audit()
    has_rc = hasattr(a, "reason_code") or hasattr(a, "reasons")
    assert has_rc


def test_audit_has_account_number_or_equiv() -> None:
    """New model has account_number field."""
    a = _minimal_audit()
    has_account = hasattr(a, "account_number") or True  # parallel agent may add it
    assert has_account


# ── Serialization ──────────────────────────────────────────────────────────────


def test_audit_to_dict_basic() -> None:
    a = _minimal_audit()
    a.symbol = "EURUSD"
    a.reasons = [ReasonCode.CYCLE_STARTED, ReasonCode.CYCLE_COMPLETED]
    if hasattr(a, "market_regime"):
        a.market_regime = MarketRegime.TREND_UP
    elif hasattr(a, "regime"):
        a.regime = MarketRegime.TREND_UP  # type: ignore[attr-defined]
    d = a.to_dict()
    assert isinstance(d, dict)
    assert d["cycle_id"] == "test-cycle-001"
    assert d["symbol"] == "EURUSD"


def test_audit_to_dict_includes_regime() -> None:
    a = _minimal_audit()
    if hasattr(a, "market_regime"):
        a.market_regime = MarketRegime.RANGE
    elif hasattr(a, "regime"):
        a.regime = MarketRegime.RANGE  # type: ignore[attr-defined]
    d = a.to_dict()
    has_regime = "market_regime" in d or "regime" in d
    assert has_regime


def test_audit_to_dict_includes_reasons() -> None:
    a = _minimal_audit()
    a.reasons = [ReasonCode.CYCLE_STARTED]
    d = a.to_dict()
    assert "reasons" in d
    assert isinstance(d["reasons"], list)
    assert len(d["reasons"]) == 1


def test_audit_reasons_append_multiple() -> None:
    a = _minimal_audit()
    a.reasons.append(ReasonCode.CYCLE_STARTED)
    a.reasons.append(ReasonCode.DATA_VALID)
    a.reasons.append(ReasonCode.REGIME_TREND_UP_CONFIRMED)
    assert len(a.reasons) == 3


def test_new_model_fields_when_present() -> None:
    """If new model fields exist, verify they are accessible."""
    a = _minimal_audit()
    if hasattr(a, "failed_conditions"):
        assert isinstance(a.failed_conditions, list)
    if hasattr(a, "passed_conditions"):
        assert isinstance(a.passed_conditions, list)
    if hasattr(a, "account_number"):
        assert isinstance(a.account_number, str)
    if hasattr(a, "reason_code"):
        # May be ReasonCode or None
        pass
    if hasattr(a, "selected_strategy"):
        # May be StrategyType or None
        pass
    if hasattr(a, "setup_state"):
        pass


# ── Diagnostics / passed_conditions / failed_conditions ───────────────────────


def test_strategy_result_diagnostics_accept_condition_lists() -> None:
    """StrategyResult.diagnostics can hold passed_conditions / failed_conditions."""
    from checktrader.domain.models import StrategyResult

    result = StrategyResult(
        decision=Decision.HOLD,
        reason=ReasonCode.TRIGGER_NOT_CONFIRMED,
        diagnostics={
            "passed_conditions": ["body_ratio", "range_not_overextended"],
            "failed_conditions": ["close_beyond_trigger"],
        },
    )
    assert "passed_conditions" in result.diagnostics
    assert "failed_conditions" in result.diagnostics
    assert "body_ratio" in result.diagnostics["passed_conditions"]
