from __future__ import annotations

from engine.core.instance import Instance
from engine.core.paths import SystemPaths
from engine.core.timeout import (
    AckTimeoutResult,
    build_ack_timeout_config,
    build_ack_timeout_reason,
    is_ack_timeout_elapsed,
    log_ack_timeout,
)
from engine.journal.error_journal import build_error_journal_path
from engine.protocol.constants import REASON_ACK_TIMEOUT, AckStatus
from engine.protocol.models import RuntimeConfig
from engine.protocol.parser import parse_error_journal_line


def _runtime_config(*, ack_timeout_ms: int = 5000) -> RuntimeConfig:
    return RuntimeConfig(
        cycle_interval_ms=1000,
        ack_timeout_ms=ack_timeout_ms,
        retry_max=3,
        retry_delay_ms=200,
        data_stale_threshold_ms=15000,
        cycle_max_duration_ms=30000,
        metrics_interval_ms=60000,
        auto_discover_instances=True,
    )


def test_build_ack_timeout_config_uses_runtime_value() -> None:
    config = build_ack_timeout_config(_runtime_config(ack_timeout_ms=7500))

    assert config.ack_timeout_ms == 7500


def test_is_ack_timeout_elapsed_detects_expired_wait() -> None:
    assert is_ack_timeout_elapsed(
        started_monotonic=100.0,
        current_monotonic=105.5,
        ack_timeout_ms=5000,
    )
    assert not is_ack_timeout_elapsed(
        started_monotonic=100.0,
        current_monotonic=104.0,
        ack_timeout_ms=5000,
    )


def test_build_ack_timeout_reason_uses_ack_timeout_code() -> None:
    reason = build_ack_timeout_reason(command_id="cmd-1")

    assert REASON_ACK_TIMEOUT in reason
    assert "command_id=cmd-1" in reason


def test_log_ack_timeout_writes_error_journal_entry(tmp_path) -> None:
    paths = SystemPaths(root_path=tmp_path)
    instance = Instance(account_id="12345", symbol="EURUSD", magic=100001)

    result = log_ack_timeout(paths, instance, command_id="cmd-timeout-1")

    assert isinstance(result, AckTimeoutResult)
    assert result.status == AckStatus.TIMEOUT.value
    assert result.command_id == "cmd-timeout-1"
    assert REASON_ACK_TIMEOUT in result.reason

    journal_text = build_error_journal_path(paths, instance).read_text(encoding="utf-8")
    entry = parse_error_journal_line(journal_text.strip())
    assert entry.module == "core.timeout"
    assert entry.error_type == "EXECUTION"
    assert REASON_ACK_TIMEOUT in entry.message
    assert entry.context["command_id"] == "cmd-timeout-1"
