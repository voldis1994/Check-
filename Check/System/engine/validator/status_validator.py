from __future__ import annotations
import math
from dataclasses import dataclass
from engine.protocol.constants import ValidationStatus
from engine.protocol.models import StatusRecord
from engine.protocol.parser import parse_status
from engine.protocol.errors import ProtocolError

@dataclass(frozen=True)
class StatusValidationResult:
    status: str
    errors: tuple[str, ...]
    is_tradeable: bool
    record: StatusRecord | None

    @property
    def is_valid(self) -> bool:
        return self.status == ValidationStatus.VALID.value

def validate_status_json(raw_text: str) -> StatusValidationResult:
    if not isinstance(raw_text, str) or not raw_text.strip():
        return StatusValidationResult(status=ValidationStatus.INVALID.value, errors=('status json is empty',), is_tradeable=False, record=None)
    try:
        record = parse_status(raw_text)
    except ProtocolError as exc:
        return StatusValidationResult(status=ValidationStatus.INVALID.value, errors=(exc.message,), is_tradeable=False, record=None)
    errors: list[str] = []
    if math.isnan(record.balance):
        errors.append('balance must not be NaN')
    if math.isnan(record.equity):
        errors.append('equity must not be NaN')
    if errors:
        return StatusValidationResult(status=ValidationStatus.INVALID.value, errors=tuple(errors), is_tradeable=False, record=record)
    return StatusValidationResult(status=ValidationStatus.VALID.value, errors=(), is_tradeable=record.connected and record.trade_allowed, record=record)
