from __future__ import annotations
from datetime import datetime
from checktrader.config.models import SystemConfig
from checktrader.domain.enums import Decision, ReasonCode
from checktrader.domain.models import AccountStatus, LimitState, Position, RiskResult, StrategySignal, SymbolSpecs
from checktrader.risk.limits import validate_limits
from checktrader.risk.sizing import fixed_lot
from checktrader.risk.spread import validate_spread
from checktrader.risk.stops import validate_reward_risk, validate_stop_distance

def validate_order(signal: StrategySignal, *, config: SystemConfig, specs: SymbolSpecs, account: AccountStatus|None, positions: list[Position], limit_state: LimitState, bid: float, ask: float, atr_value: float|None, now: datetime) -> RiskResult:
    failures=[]; lot,lot_reason=fixed_lot(config.position_sizing)
    if config.runtime.mode=='live' and not config.runtime.trading_enabled: failures.append(ReasonCode.RISK_LIVE_NOT_ENABLED)
    if account is not None and (not account.connected or not account.trading_allowed or account.equity<config.account.min_equity): failures.append(ReasonCode.RISK_ACCOUNT_NOT_OK)
    if len(positions)>=config.position.max_open_positions: failures.append(ReasonCode.RISK_POSITION_EXISTS)
    if lot_reason!=ReasonCode.RISK_ACCEPTED: failures.append(lot_reason)
    for reason in (validate_spread(bid,ask,atr_value,specs,config.spread), validate_stop_distance(signal,specs,config.risk), validate_reward_risk(signal,config.risk), validate_limits(limit_state,config.limits,now)):
        if reason!=ReasonCode.RISK_ACCEPTED: failures.append(reason)
    return RiskResult(Decision.BLOCK,failures[0],lot,failures) if failures else RiskResult(Decision.ALLOW,ReasonCode.RISK_ACCEPTED,lot,[ReasonCode.RISK_ACCEPTED])
