from __future__ import annotations

import pytest

from engine.protocol.constants import ErrorType
from engine.protocol.errors import (
    ConfigurationError,
    DataIOError,
    ERROR_TYPE_BY_CLASS,
    ExecutionError,
    ProtocolError,
    RiskError,
    SystemError,
    ValidationError,
    get_error_type,
    wrap_exception,
)


def test_system_error_base() -> None:
    error = SystemError("base failure", module="test.module", context={"key": "value"})
    assert isinstance(error, Exception)
    assert error.message == "base failure"
    assert error.module == "test.module"
    assert error.context == {"key": "value"}
    assert error.error_type == ErrorType.PROTOCOL
    assert str(error) == "[PROTOCOL] test.module: base failure"
    assert error.to_dict() == {
        "error_type": "PROTOCOL",
        "message": "base failure",
        "module": "test.module",
        "context": {"key": "value"},
    }


def test_system_error_requires_message() -> None:
    with pytest.raises(ValueError, match="message must not be empty"):
        SystemError("")


def test_protocol_error_inheritance() -> None:
    error = ProtocolError("protocol failure", module="protocol.parser")
    assert isinstance(error, SystemError)
    assert error.error_type == ErrorType.PROTOCOL
    assert get_error_type(error) == ErrorType.PROTOCOL


def test_validation_error_inheritance() -> None:
    error = ValidationError("validation failure")
    assert isinstance(error, SystemError)
    assert error.error_type == ErrorType.VALIDATION
    assert get_error_type(error) == ErrorType.VALIDATION


def test_data_io_error_inheritance() -> None:
    error = DataIOError("io failure")
    assert isinstance(error, SystemError)
    assert error.error_type == ErrorType.IO
    assert get_error_type(error) == ErrorType.IO


def test_execution_error_inheritance() -> None:
    error = ExecutionError("execution failure")
    assert isinstance(error, SystemError)
    assert error.error_type == ErrorType.EXECUTION
    assert get_error_type(error) == ErrorType.EXECUTION


def test_risk_error_inheritance() -> None:
    error = RiskError("risk failure")
    assert isinstance(error, SystemError)
    assert error.error_type == ErrorType.RISK
    assert get_error_type(error) == ErrorType.RISK


def test_configuration_error_inheritance() -> None:
    error = ConfigurationError("config failure")
    assert isinstance(error, SystemError)
    assert isinstance(error, ValidationError)
    assert error.error_type == ErrorType.VALIDATION
    assert get_error_type(error) == ErrorType.VALIDATION


def test_error_type_mapping_complete() -> None:
    assert ERROR_TYPE_BY_CLASS[SystemError] == ErrorType.PROTOCOL
    assert ERROR_TYPE_BY_CLASS[ProtocolError] == ErrorType.PROTOCOL
    assert ERROR_TYPE_BY_CLASS[ValidationError] == ErrorType.VALIDATION
    assert ERROR_TYPE_BY_CLASS[DataIOError] == ErrorType.IO
    assert ERROR_TYPE_BY_CLASS[ExecutionError] == ErrorType.EXECUTION
    assert ERROR_TYPE_BY_CLASS[RiskError] == ErrorType.RISK
    assert ERROR_TYPE_BY_CLASS[ConfigurationError] == ErrorType.VALIDATION


def test_wrap_exception_from_builtin() -> None:
    original = FileNotFoundError("missing file")
    wrapped = wrap_exception(
        original,
        error_class=DataIOError,
        module="loader.market_loader",
        context={"path": "/tmp/x.csv"},
    )
    assert isinstance(wrapped, DataIOError)
    assert wrapped.message == "missing file"
    assert wrapped.module == "loader.market_loader"
    assert wrapped.context["path"] == "/tmp/x.csv"
    assert wrapped.context["original_type"] == "FileNotFoundError"


def test_wrap_exception_preserves_system_error() -> None:
    original = ProtocolError("already wrapped")
    wrapped = wrap_exception(original, error_class=DataIOError)
    assert wrapped is original


def test_all_exception_types_are_subclasses_of_system_error() -> None:
    exception_types = [
        ProtocolError,
        ValidationError,
        DataIOError,
        ExecutionError,
        RiskError,
        ConfigurationError,
    ]
    for exc_type in exception_types:
        assert issubclass(exc_type, SystemError)
        instance = exc_type("sample")
        assert isinstance(instance, SystemError)
