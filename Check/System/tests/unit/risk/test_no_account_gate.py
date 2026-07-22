from __future__ import annotations

from datetime import UTC, datetime

from checktrader.config.loader import load_config
from checktrader.domain.enums import Decision, ReasonCode, Side, StrategyType
from checktrader.domain.models import AccountStatus, LimitState, StrategySignal, SymbolSpecs
from checktrader.risk.validator import validate_order


def test_account_not_ok_does_not_block_by_default() -> None:
    cfg = load_config()
    assert cfg.risk.enforce_account_status is False
    specs = SymbolSpecs("NATURALGAS", 3, 0.001, 0.001, 0.01, 0.01, 100.0, 0.01, 100.0, 0.0, 0.0)
    signal = StrategySignal(
        StrategyType.BREAKOUT,
        Side.BUY,
        "NATURALGAS",
        2.90,
        2.85,
        3.00,
        ReasonCode.FORCE_MOMENTUM_BUY,
    )
    # Broker says disconnected / trading not allowed — must still ALLOW
    account = AccountStatus("231054", 1000.0, 50.0, 50.0, "USD", trading_allowed=False, connected=False)
    result = validate_order(
        signal,
        config=cfg,
        specs=specs,
        account=account,
        positions=[],
        limit_state=LimitState(trade_date=""),
        bid=2.899,
        ask=2.901,
        atr_value=0.02,
        now=datetime.now(UTC),
    )
    assert result.decision is Decision.ALLOW
    assert ReasonCode.RISK_ACCOUNT_NOT_OK not in result.messages


def test_daily_limits_disabled_by_default() -> None:
    cfg = load_config()
    assert cfg.limits.max_daily_trades == 0
    assert cfg.limits.max_consecutive_losses == 0
    assert cfg.risk.daily_loss_limit_r == 0.0
    assert cfg.risk.min_reward_risk == 0.0
