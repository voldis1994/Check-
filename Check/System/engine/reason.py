from __future__ import annotations
from engine.protocol.constants import is_valid_reason_code
from engine.protocol.errors import ValidationError

def build_reason(reason_code: str, detail: str, **params: object) -> str:
    if not isinstance(reason_code, str) or not reason_code.strip():
        raise ValidationError('reason_code must be a non-empty string', module='engine.reason', context={'value_type': type(reason_code).__name__})
    if not is_valid_reason_code(reason_code):
        raise ValidationError('reason_code is invalid', module='engine.reason', context={'reason_code': reason_code})
    if not isinstance(detail, str) or not detail.strip():
        raise ValidationError('detail must be a non-empty string', module='engine.reason', context={'value_type': type(detail).__name__})
    normalized_detail = detail.strip()
    if not params:
        return f'{reason_code}: {normalized_detail}'
    details = ', '.join((f'{key}={value}' for key, value in sorted(params.items())))
    return f'{reason_code}: {normalized_detail} ({details})'
