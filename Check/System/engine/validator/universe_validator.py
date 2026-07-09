from __future__ import annotations
from engine.protocol.constants import ValidationStatus
from engine.protocol.errors import ProtocolError
from engine.protocol.parser import parse_universe
from engine.validator.market_validator import ValidationResult

def validate_universe_json(raw_text: str) -> ValidationResult:
    if not isinstance(raw_text, str) or not raw_text.strip():
        return ValidationResult(status=ValidationStatus.INVALID.value, errors=('universe json is empty',), row_count=0)
    try:
        parse_universe(raw_text)
    except ProtocolError as exc:
        return ValidationResult(status=ValidationStatus.INVALID.value, errors=(exc.message,), row_count=0)
    return ValidationResult(status=ValidationStatus.VALID.value, errors=(), row_count=1)
