from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping
from engine.core.instance import Instance
from engine.core.logging_setup import log_event
from engine.protocol.constants import REASON_ACCOUNT_NOT_TRADEABLE, REASON_ACK_TIMEOUT, AlertLevel, Decision, LogLevel
MODULE_NAME = 'core.alerts'
ALERT_CODE_DATA_STALE = 'DATA_STALE'
ALERT_CODE_ACK_TIMEOUT = 'ACK_TIMEOUT'
ALERT_CODE_VALIDATION_FAILURE = 'VALIDATION_FAILURE'
ALERT_CODE_ACCOUNT_NOT_TRADEABLE = 'ACCOUNT_NOT_TRADEABLE'
ALERT_CODE_RETRY = 'RETRY'

@dataclass(frozen=True)
class Alert:
    level: str
    code: str
    message: str
    instance: Instance | None = None
    context: Mapping[str, object] | None = None

def alerts_affect_trading() -> bool:
    return False

def alert_level_to_log_level(level: str) -> str:
    if level == AlertLevel.INFO.value:
        return LogLevel.INFO.value
    if level == AlertLevel.WARNING.value:
        return LogLevel.WARNING.value
    if level == AlertLevel.ERROR.value:
        return LogLevel.ERROR.value
    if level == AlertLevel.CRITICAL.value:
        return LogLevel.CRITICAL.value
    return LogLevel.INFO.value

def build_data_stale_alert(instance: Instance, *, freshness_ms: int, threshold_ms: int) -> Alert:
    return Alert(level=AlertLevel.WARNING.value, code=ALERT_CODE_DATA_STALE, message=f'market data stale freshness_ms={freshness_ms} threshold_ms={threshold_ms}', instance=instance, context={'freshness_ms': freshness_ms, 'threshold_ms': threshold_ms})

def build_ack_timeout_alert(instance: Instance, *, command_id: str | None=None) -> Alert:
    context: dict[str, object] = {}
    if command_id is not None:
        context['command_id'] = command_id
    return Alert(level=AlertLevel.ERROR.value, code=ALERT_CODE_ACK_TIMEOUT, message=REASON_ACK_TIMEOUT, instance=instance, context=context or None)

def build_validation_failure_alert(instance: Instance, *, message: str) -> Alert:
    return Alert(level=AlertLevel.ERROR.value, code=ALERT_CODE_VALIDATION_FAILURE, message=message, instance=instance)

def build_account_not_tradeable_alert(instance: Instance) -> Alert:
    return Alert(level=AlertLevel.CRITICAL.value, code=ALERT_CODE_ACCOUNT_NOT_TRADEABLE, message=REASON_ACCOUNT_NOT_TRADEABLE, instance=instance)

def build_retry_alert(instance: Instance | None, *, message: str, context: Mapping[str, object] | None=None) -> Alert:
    return Alert(level=AlertLevel.WARNING.value, code=ALERT_CODE_RETRY, message=message, instance=instance, context=context)

def format_alert_message(alert: Alert) -> str:
    if alert.instance is None:
        return f'alert code={alert.code} {alert.message}'
    instance = alert.instance
    return f'alert code={alert.code} account={instance.account_id} symbol={instance.symbol} magic={instance.magic} {alert.message}'

def emit_alert(logger, alert: Alert) -> None:
    instance = alert.instance
    log_event(logger, level=alert_level_to_log_level(alert.level), module=MODULE_NAME, message=format_alert_message(alert), account_id=instance.account_id if instance is not None else None, symbol=instance.symbol if instance is not None else None, magic=instance.magic if instance is not None else None)

def dispatch_cycle_alerts(logger, instance: Instance, *, data_stale: bool, freshness_ms: int | None, stale_threshold_ms: int, ack_timed_out: bool, command_id: str | None, validation_failed: bool, validation_message: str | None, account_not_tradeable: bool) -> tuple[Alert, ...]:
    alerts: list[Alert] = []
    if data_stale and freshness_ms is not None:
        alerts.append(build_data_stale_alert(instance, freshness_ms=freshness_ms, threshold_ms=stale_threshold_ms))
    if ack_timed_out:
        alerts.append(build_ack_timeout_alert(instance, command_id=command_id))
    if validation_failed:
        alerts.append(build_validation_failure_alert(instance, message=validation_message or 'validation failure'))
    if account_not_tradeable:
        alerts.append(build_account_not_tradeable_alert(instance))
    for alert in alerts:
        emit_alert(logger, alert)
    return tuple(alerts)

def should_emit_account_not_tradeable_alert(decision: str | None, reason: str | None) -> bool:
    if decision != Decision.BLOCK.value:
        return False
    if reason is None:
        return False
    return REASON_ACCOUNT_NOT_TRADEABLE in reason
