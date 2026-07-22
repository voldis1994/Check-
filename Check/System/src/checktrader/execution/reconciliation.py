"""Reconciliation helpers."""

from __future__ import annotations

from checktrader.domain.enums import ConfirmationSource, PositionState
from checktrader.domain.orders import BrokerPosition
from checktrader.domain.positions import ManagedPosition
from checktrader.domain.trailing import TrailingState
from checktrader.market_data.freshness import age_ms
from checktrader.observability.reason_codes import ReasonCode


def is_ack_timeout(*, pending_created_at: str | None, now_utc: str, ack_timeout_ms: int) -> bool:
    if not pending_created_at or ack_timeout_ms <= 0:
        return False
    return age_ms(pending_created_at, now_utc) > ack_timeout_ms


def reconcile_position_from_broker(
    managed: ManagedPosition,
    broker: BrokerPosition | None,
) -> tuple[ManagedPosition, ReasonCode]:
    if broker is None:
        if managed.state in {
            PositionState.OPEN_PENDING,
            PositionState.MODIFY_PENDING,
            PositionState.CLOSE_PENDING,
        }:
            # Keep command-pending states until ACK / timeout handling.
            return managed, ReasonCode.COMMAND_ALREADY_PENDING
        if managed.state is PositionState.OPEN:
            managed.state = PositionState.RECONCILING
            return managed, ReasonCode.RECONCILIATION_REQUIRED
        managed.state = PositionState.FLAT
        managed.ticket = None
        return managed, ReasonCode.RECONCILIATION_CONFIRMED
    managed.state = PositionState.OPEN
    managed.ticket = broker.ticket
    managed.side = broker.side
    managed.volume = broker.volume
    managed.open_price = broker.open_price
    managed.stop_loss = broker.stop_loss
    managed.take_profit = broker.take_profit
    managed.open_time_utc = broker.open_time_utc
    return managed, ReasonCode.RECONCILIATION_CONFIRMED


def confirm_pending_from_status(
    trailing: TrailingState,
    broker: BrokerPosition,
    *,
    tolerance: float,
) -> tuple[TrailingState, bool]:
    if trailing.pending_stop_loss is None:
        return trailing, False
    if abs(broker.stop_loss - trailing.pending_stop_loss) > tolerance:
        return trailing, False
    trailing.confirmed_stop_loss = broker.stop_loss
    trailing.broker_stop_loss = broker.stop_loss
    if not trailing.be_confirmed:
        trailing.be_confirmed = True
        trailing.confirmed_be_sl = broker.stop_loss
        trailing.confirmation_source = ConfirmationSource.STATUS
        trailing.last_reason = ReasonCode.BE_CONFIRMED.value
    else:
        trailing.confirmation_source = ConfirmationSource.STATUS
        trailing.last_reason = ReasonCode.TRAILING_GRID_CONFIRMED.value
    trailing.pending_stop_loss = None
    trailing.pending_command_id = None
    return trailing, True
