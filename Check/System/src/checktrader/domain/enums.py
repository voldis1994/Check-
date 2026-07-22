"""Domain enums for SYSTEM v2."""

from __future__ import annotations

from enum import Enum


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class StrategyResult(str, Enum):
    ENTRY_BUY = "ENTRY_BUY"
    ENTRY_SELL = "ENTRY_SELL"
    NO_SIGNAL = "NO_SIGNAL"
    DATA_INVALID = "DATA_INVALID"


class ExecutionStatus(str, Enum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"
    UNKNOWN = "UNKNOWN"


class PositionState(str, Enum):
    FLAT = "FLAT"
    OPEN_PENDING = "OPEN_PENDING"
    OPEN = "OPEN"
    MODIFY_PENDING = "MODIFY_PENDING"
    CLOSE_PENDING = "CLOSE_PENDING"
    RECONCILING = "RECONCILING"
    ERROR = "ERROR"


class SetupState(str, Enum):
    SEARCHING = "SEARCHING"
    CANDIDATE = "CANDIDATE"
    ARMED = "ARMED"
    TRIGGERED = "TRIGGERED"
    SENT = "SENT"
    OPENED = "OPENED"
    INVALIDATED = "INVALIDATED"
    EXPIRED = "EXPIRED"
    COMPLETED = "COMPLETED"


class OrderAction(str, Enum):
    OPEN = "OPEN"
    MODIFY = "MODIFY"
    CLOSE = "CLOSE"
    NONE = "NONE"


class RiskDecision(str, Enum):
    APPROVED = "APPROVED"
    INVALID_STOP = "INVALID_STOP"
    INVALID_VOLUME = "INVALID_VOLUME"
    MARGIN_INSUFFICIENT = "MARGIN_INSUFFICIENT"
    SYMBOL_SPEC_MISSING = "SYMBOL_SPEC_MISSING"
    PRICE_INVALID = "PRICE_INVALID"
    RISK_CONFIG_INVALID = "RISK_CONFIG_INVALID"


class ConfirmationSource(str, Enum):
    ACK = "ACK"
    STATUS = "STATUS"
    NONE = "NONE"


class MessageType(str, Enum):
    MARKET_SNAPSHOT = "market_snapshot"
    STATUS_SNAPSHOT = "status_snapshot"
    COMMAND = "command"
    ACKNOWLEDGEMENT = "acknowledgement"
