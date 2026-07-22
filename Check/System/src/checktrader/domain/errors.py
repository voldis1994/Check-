"""Domain errors."""

from __future__ import annotations

from checktrader.observability.reason_codes import ReasonCode


class CheckTraderError(Exception):
    """Base error with a concrete reason code."""

    def __init__(self, message: str, *, reason: ReasonCode, context: dict[str, object] | None = None) -> None:
        super().__init__(message)
        self.reason = reason
        self.context = context or {}


class ValidationError(CheckTraderError):
    pass


class DataError(CheckTraderError):
    pass


class ExecutionError(CheckTraderError):
    pass


class ConfigurationError(CheckTraderError):
    pass
