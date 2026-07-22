from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from checktrader.domain.enums import Decision, MarketRegime, OrderAction, ReasonCode, SetupState, Side, StrategyType


def utc_now() -> datetime:
    return datetime.now(UTC)


def _clean(v: Any) -> Any:
    if isinstance(v, datetime):
        return v.isoformat()
    if hasattr(v, "value"):
        return v.value
    if isinstance(v, list):
        return [_clean(x) for x in v]
    if isinstance(v, dict):
        return {str(k): _clean(x) for k, x in v.items()}
    return v


@dataclass(slots=True)
class Serializable:
    def to_dict(self) -> dict[str, Any]:
        cleaned = _clean(asdict(self))
        assert isinstance(cleaned, dict)
        return cleaned


@dataclass(slots=True)
class Candle(Serializable):
    time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    timeframe: str = "M1"
    closed: bool = True

    @classmethod
    def from_dict(cls, d: dict[str, Any], timeframe: str | None = None) -> Candle:
        raw = (
            d.get("time")
            or d.get("timestamp")
            or d.get("t")
            or d.get("datetime")
            or d.get("bar_time")
            or d.get("Time")
        )
        if isinstance(raw, datetime):
            t = raw
        elif isinstance(raw, (int, float)):
            ts = float(raw)
            if ts > 1_000_000_000_000:  # ms
                ts /= 1000.0
            t = datetime.fromtimestamp(ts, UTC)
        elif isinstance(raw, str) and raw.strip():
            cleaned = raw.strip()
            if cleaned.endswith("Z"):
                cleaned = cleaned[:-1] + "+00:00"
            # Legacy MT4 TimeToString: 2026.07.22 16:00:00
            if len(cleaned) >= 19 and cleaned[4] == "." and cleaned[7] == ".":
                cleaned = f"{cleaned[0:4]}-{cleaned[5:7]}-{cleaned[8:10]}T{cleaned[11:19]}"
                if len(cleaned) == 19:
                    cleaned += "+00:00"
            t = datetime.fromisoformat(cleaned)
        else:
            raise ValueError("candle time is required")
        if t.tzinfo is None:
            t = t.replace(tzinfo=UTC)
        return cls(
            t,
            float(d["open"]),
            float(d["high"]),
            float(d["low"]),
            float(d["close"]),
            float(d.get("volume", d.get("tick_volume", 0.0))),
            str(timeframe or d.get("timeframe", "M1")),
            bool(d.get("closed", True)),
        )


@dataclass(slots=True)
class SymbolSpecs(Serializable):
    symbol: str
    digits: int
    point: float
    tick_size: float
    pip_size: float
    min_lot: float
    max_lot: float
    lot_step: float
    contract_size: float
    stop_level_points: float = 0.0
    freeze_level_points: float = 0.0


@dataclass(slots=True)
class AccountStatus(Serializable):
    account_id: str
    balance: float
    equity: float
    margin_free: float
    currency: str
    trading_allowed: bool = True
    connected: bool = True
    timestamp: datetime = field(default_factory=utc_now)


@dataclass(slots=True)
class Position(Serializable):
    position_id: str
    symbol: str
    side: Side
    lot: float
    entry_price: float
    stop_loss: float | None
    take_profit: float | None
    opened_at: datetime
    strategy: StrategyType
    current_price: float | None = None
    profit: float = 0.0
    magic_number: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Setup(Serializable):
    # Required positional fields
    setup_id: str
    symbol: str
    strategy: StrategyType
    side: Side
    state: SetupState
    created_at_bar: datetime
    created_at_utc: datetime
    trigger_level: float
    stop_loss: float
    # Optional / defaulted fields
    account_number: str = ""
    regime: MarketRegime | None = None
    expires_at_bar: datetime | None = None
    take_profit: float | None = None
    invalidation_level: float | None = None
    stop_loss_candidate: float | None = None
    indicator_snapshot: dict[str, Any] | None = None
    status_history: list[dict[str, Any]] = field(default_factory=list)
    cancellation_reason: str | None = None
    command_id: str | None = None
    ticket: str | None = None
    reason: ReasonCode = ReasonCode.SETUP_CREATED
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        symbol: str,
        strategy: StrategyType,
        side: Side,
        state: SetupState,
        created_at_bar: datetime,
        trigger_level: float,
        stop_loss: float,
        *,
        # legacy alias kept for callers that still pass trigger_price
        trigger_price: float | None = None,
        account_number: str = "",
        regime: MarketRegime | None = None,
        expires_at_bar: datetime | None = None,
        take_profit: float | None = None,
        invalidation_level: float | None = None,
        stop_loss_candidate: float | None = None,
        indicator_snapshot: dict[str, Any] | None = None,
        cancellation_reason: str | None = None,
        command_id: str | None = None,
        ticket: str | None = None,
        reason: ReasonCode = ReasonCode.SETUP_CREATED,
        metadata: dict[str, Any] | None = None,
        created_at_utc: datetime | None = None,
    ) -> Setup:
        if trigger_price is not None and trigger_level == 0.0:
            trigger_level = trigger_price
        now = utc_now()
        setup = cls(
            f"{strategy.value}-{side.value}-{uuid4().hex[:12]}",
            symbol,
            strategy,
            side,
            state,
            created_at_bar,
            created_at_utc or now,
            trigger_level,
            stop_loss,
            account_number,
            regime,
            expires_at_bar,
            take_profit,
            invalidation_level,
            stop_loss_candidate,
            indicator_snapshot,
            [],  # status_history starts empty
            cancellation_reason,
            command_id,
            ticket,
            reason,
            metadata or {},
        )
        # Record initial state in history
        setup.status_history.append({"state": state.value, "reason": reason.value, "at": now.isoformat()})
        return setup


@dataclass(slots=True)
class SwingPoint(Serializable):
    time: datetime
    price: float
    side: Side
    index: int
    confirmed_at: datetime


@dataclass(slots=True)
class IndicatorSnapshot(Serializable):
    time: datetime
    ema_fast: float | None = None
    ema_slow: float | None = None
    ema200: float | None = None
    ema_signal: float | None = None
    atr: float | None = None
    adx: float | None = None
    plus_di: float | None = None
    minus_di: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RegimeSnapshot(Serializable):
    regime: MarketRegime
    time: datetime
    reason: ReasonCode
    confidence: float
    indicators: IndicatorSnapshot
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class MarketSnapshot(Serializable):
    symbol: str
    bid: float
    ask: float
    timestamp: datetime
    m1: list[Candle] = field(default_factory=list)
    m5: list[Candle] = field(default_factory=list)
    m15: list[Candle] = field(default_factory=list)
    account: AccountStatus | None = None
    positions: list[Position] = field(default_factory=list)
    heartbeat_at: datetime | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2.0


@dataclass(slots=True)
class StrategySignal(Serializable):
    strategy: StrategyType
    side: Side
    symbol: str
    entry_price: float
    stop_loss: float
    take_profit: float | None
    reason: ReasonCode
    setup_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class StrategyResult(Serializable):
    decision: Decision
    reason: ReasonCode
    signal: StrategySignal | None = None
    setup: Setup | None = None
    diagnostics: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RiskResult(Serializable):
    decision: Decision
    reason: ReasonCode
    lot: float = 0.0
    messages: list[ReasonCode] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def allowed(self) -> bool:
        return self.decision == Decision.ALLOW


@dataclass(slots=True)
class Command(Serializable):
    command_id: str
    action: OrderAction
    symbol: str
    protocol_version: str
    created_at: datetime
    payload: dict[str, Any]


@dataclass(slots=True)
class Acknowledgement(Serializable):
    command_id: str
    accepted: bool
    reason: ReasonCode
    broker_order_id: str | None = None
    message: str = ""
    timestamp: datetime = field(default_factory=utc_now)
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ManagementAction(Serializable):
    decision: Decision
    reason: ReasonCode
    action: OrderAction = OrderAction.NONE
    stop_loss: float | None = None
    take_profit: float | None = None
    close_fraction: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class LimitState(Serializable):
    trade_date: str
    daily_trades: int = 0
    consecutive_losses: int = 0
    cooldown_until: datetime | None = None
    last_trade_at: datetime | None = None
    daily_loss_r: float = 0.0


@dataclass(slots=True)
class CycleAudit(Serializable):
    # Required fields
    cycle_id: str
    started_at: datetime
    # Section 4 core fields
    completed_at: datetime | None = None
    symbol: str = ""
    account_number: str = ""
    market_regime: MarketRegime | None = None
    selected_strategy: StrategyType | None = None
    setup_state: SetupState | None = None
    decision: Decision | None = None
    reason_code: ReasonCode | None = None
    human_readable_reason: str = ""
    failed_conditions: list[str] = field(default_factory=list)
    passed_conditions: list[str] = field(default_factory=list)
    indicator_snapshot: dict[str, Any] | None = None
    risk_result: RiskResult | None = None
    execution_result: dict[str, Any] = field(default_factory=dict)
    # Extended / useful extras
    signal: StrategySignal | None = None
    command: Command | None = None
    management: ManagementAction | None = None
    reasons: list[ReasonCode] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)

    def set_reason(self, code: ReasonCode, failed: list[str] | None = None) -> None:
        """Set reason_code and derive human_readable_reason."""
        self.reason_code = code
        parts = [code.value]
        if failed:
            self.failed_conditions = list(failed)
            parts.append("failed: " + ", ".join(failed))
        self.human_readable_reason = "; ".join(parts)
