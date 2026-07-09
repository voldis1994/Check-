from __future__ import annotations
from datetime import datetime, timezone
from typing import Callable
from engine.protocol.errors import ValidationError
CLOCK_MODULE = 'core.clock'

def _validation_error(message: str, **context: object) -> ValidationError:
    return ValidationError(message, module=CLOCK_MODULE, context=dict(context))

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

def format_utc_timestamp(timestamp: datetime) -> str:
    if not isinstance(timestamp, datetime):
        raise _validation_error('timestamp must be a datetime', field='timestamp', value_type=type(timestamp).__name__)
    if timestamp.tzinfo is None:
        raise _validation_error('timestamp must be timezone-aware', field='timestamp')
    utc_timestamp = timestamp.astimezone(timezone.utc)
    return utc_timestamp.isoformat(timespec='milliseconds').replace('+00:00', 'Z')

def now_utc(now_provider: Callable[[], datetime] | None=None) -> str:
    current_time = now_provider() if now_provider is not None else utc_now()
    return format_utc_timestamp(current_time)
