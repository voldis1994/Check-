from __future__ import annotations
from typing import Any
from engine.protocol.constants import ErrorType

class SystemError(Exception):
    error_type: ErrorType = ErrorType.PROTOCOL

    def __init__(self, message: str, *, module: str | None=None, context: dict[str, Any] | None=None) -> None:
        if not message:
            raise ValueError('error message must not be empty')
        self.message = message
        self.module = module
        self.context = dict(context) if context is not None else {}
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        return {'error_type': self.error_type.value, 'message': self.message, 'module': self.module, 'context': self.context}

    def __str__(self) -> str:
        parts = [f'[{self.error_type.value}]']
        if self.module:
            parts.append(f'{self.module}:')
        parts.append(self.message)
        return ' '.join(parts)

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}(message={self.message!r}, module={self.module!r}, context={self.context!r})'

class ProtocolError(SystemError):
    error_type = ErrorType.PROTOCOL

class ValidationError(SystemError):
    error_type = ErrorType.VALIDATION

class DataIOError(SystemError):
    error_type = ErrorType.IO

class ExecutionError(SystemError):
    error_type = ErrorType.EXECUTION

class RiskError(SystemError):
    error_type = ErrorType.RISK

class ConfigurationError(ValidationError):
    error_type = ErrorType.VALIDATION
ERROR_TYPE_BY_CLASS: dict[type[SystemError], ErrorType] = {SystemError: ErrorType.PROTOCOL, ProtocolError: ErrorType.PROTOCOL, ValidationError: ErrorType.VALIDATION, DataIOError: ErrorType.IO, ExecutionError: ErrorType.EXECUTION, RiskError: ErrorType.RISK, ConfigurationError: ErrorType.VALIDATION}

def get_error_type(error: SystemError) -> ErrorType:
    return ERROR_TYPE_BY_CLASS.get(type(error), error.error_type)

def wrap_exception(exc: Exception, *, error_class: type[SystemError], module: str | None=None, context: dict[str, Any] | None=None) -> SystemError:
    if isinstance(exc, SystemError):
        return exc
    message = str(exc) if str(exc) else exc.__class__.__name__
    merged_context = dict(context) if context is not None else {}
    merged_context['original_type'] = exc.__class__.__name__
    return error_class(message, module=module, context=merged_context)
