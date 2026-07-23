from __future__ import annotations

from datetime import datetime

from checktrader.config.models import SystemConfig
from checktrader.domain.enums import Decision, ReasonCode
from checktrader.domain.models import AccountStatus, LimitState, Position, RiskResult, StrategySignal, SymbolSpecs
from checktrader.market_data.symbols import symbols_match
from checktrader.risk.limits import validate_limits
from checktrader.risk.sizing import fixed_lot
from checktrader.risk.spread import validate_spread
from checktrader.risk.stops import validate_reward_risk, validate_stop_distance


def validate_order(
    signal: StrategySignal,
    *,
    config: SystemConfig,
    specs: SymbolSpecs,
    account: AccountStatus | None,
    positions: list[Position],
    limit_state: LimitState,
    bid: float,
    ask: float,
    atr_value: float | None,
    now: datetime,
) -> RiskResult:
    failures: list[ReasonCode] = []
    lot, lot_reason = fixed_lot(config.position_sizing)

    if config.runtime.mode == "live" and not config.runtime.trading_enabled:
        failures.append(ReasonCode.RISK_LIVE_NOT_ENABLED)

    # Account connected / trade_allowed / min_equity are OFF by default.
    # Broker status flags were blocking live NATURALGAS entries (RISK_ACCOUNT_NOT_OK).
    if config.risk.enforce_account_status and account is not None:
        min_eq = config.account.min_equity
        if (not account.connected) or (not account.trading_allowed) or (min_eq > 0 and account.equity < min_eq):
            failures.append(ReasonCode.RISK_ACCOUNT_NOT_OK)

    # Only same-symbol positions count toward max_open (chart/symbol changes must not freeze forever).
    same_symbol = [p for p in positions if symbols_match(p.symbol, signal.symbol)]
    if len(same_symbol) >= config.position.max_open_positions:
        failures.append(ReasonCode.RISK_POSITION_EXISTS)
    if lot_reason != ReasonCode.RISK_ACCEPTED:
        failures.append(lot_reason)

    for reason in (
        validate_spread(bid, ask, atr_value, specs, config.spread),
        validate_stop_distance(signal, specs, config.risk, atr_value),
        validate_reward_risk(signal, config.risk),
        validate_limits(limit_state, config.limits, now, config.risk),
    ):
        if reason != ReasonCode.RISK_ACCEPTED:
            failures.append(reason)

    if failures:
        return RiskResult(Decision.BLOCK, failures[0], lot, failures)
    return RiskResult(Decision.ALLOW, ReasonCode.RISK_ACCEPTED, lot, [ReasonCode.RISK_ACCEPTED])
