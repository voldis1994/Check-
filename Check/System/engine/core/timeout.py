from __future__ import annotations
from dataclasses import dataclass
from engine.core.instance import Instance
from engine.core.paths import SystemPaths
from engine.journal.error_journal import log_error
from engine.protocol.constants import REASON_ACK_TIMEOUT, AckStatus, ErrorType
from engine.protocol.models import RuntimeConfig
from engine.reason import build_reason
MODULE_NAME = 'core.timeout'

@dataclass(frozen=True)
class AckTimeoutConfig:
    ack_timeout_ms: int

@dataclass(frozen=True)
class AckTimeoutResult:
    command_id: str
    status: str
    reason: str

def build_ack_timeout_config(runtime: RuntimeConfig) -> AckTimeoutConfig:
    return AckTimeoutConfig(ack_timeout_ms=runtime.ack_timeout_ms)

def is_ack_timeout_elapsed(*, started_monotonic: float, current_monotonic: float, ack_timeout_ms: int) -> bool:
    if ack_timeout_ms <= 0:
        return True
    elapsed_ms = (current_monotonic - started_monotonic) * 1000.0
    return elapsed_ms >= ack_timeout_ms

def build_ack_timeout_reason(*, command_id: str) -> str:
    return build_reason(REASON_ACK_TIMEOUT, 'ack not received within timeout', command_id=command_id)

def log_ack_timeout(paths: SystemPaths, instance: Instance, *, command_id: str) -> AckTimeoutResult:
    reason = build_ack_timeout_reason(command_id=command_id)
    log_error(paths, instance, module=MODULE_NAME, error_type=ErrorType.EXECUTION.value, message=reason, context={'command_id': command_id})
    return AckTimeoutResult(command_id=command_id, status=AckStatus.TIMEOUT.value, reason=reason)
