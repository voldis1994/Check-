"""Order and position domain models."""

from __future__ import annotations

from dataclasses import dataclass

from checktrader.domain.enums import OrderAction, Side


@dataclass(frozen=True, slots=True)
class OrderCommand:
    command_id: str
    action: OrderAction
    symbol: str
    magic: int
    created_at_utc: str
    side: Side | None = None
    volume: float | None = None
    ticket: int | None = None
    requested_price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    requested_stop_loss: float | None = None
    requested_take_profit: float | None = None
    previous_broker_stop_loss: float | None = None
    slippage_points: int = 3
    setup_id: str | None = None
    setup_fingerprint: str | None = None
    trailing_reason: str | None = None
    trailing_step: float | None = None
    close_reason: str | None = None


@dataclass(frozen=True, slots=True)
class BrokerPosition:
    ticket: int
    symbol: str
    magic: int
    side: Side
    volume: float
    open_time_utc: str
    open_price: float
    stop_loss: float
    take_profit: float
    current_price: float
    profit: float
    swap: float
    commission: float
    net_profit: float
    comment: str = ""
