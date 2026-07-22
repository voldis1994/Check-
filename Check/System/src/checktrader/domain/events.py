from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4

from checktrader.domain.enums import MarketRegime, ReasonCode
from checktrader.domain.models import Acknowledgement, Candle, Command, Position, StrategySignal, utc_now


@dataclass(slots=True)
class Event:
    event_type: str
    reason: ReasonCode
    timestamp: datetime = field(default_factory=utc_now)
    event_id: str = field(default_factory=lambda: uuid4().hex)
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class CandleClosedEvent(Event):
    candle: Candle | None = None


@dataclass(slots=True)
class RegimeChangedEvent(Event):
    previous: MarketRegime | None = None
    current: MarketRegime | None = None


@dataclass(slots=True)
class SignalEvent(Event):
    signal: StrategySignal | None = None


@dataclass(slots=True)
class OrderCommandEvent(Event):
    command: Command | None = None


@dataclass(slots=True)
class AckEvent(Event):
    acknowledgement: Acknowledgement | None = None


@dataclass(slots=True)
class PositionChangedEvent(Event):
    position: Position | None = None


@dataclass(slots=True)
class HealthEvent(Event):
    healthy: bool = True
