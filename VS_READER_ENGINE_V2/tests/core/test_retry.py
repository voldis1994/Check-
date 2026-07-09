from __future__ import annotations

from pathlib import Path

import pytest

from engine.core.retry import (
    RetryAlertContext,
    RetryPolicy,
    build_retry_policy,
    max_retry_attempts,
    run_with_retry,
    validate_control_command_retry,
)
from engine.protocol.errors import ExecutionError
from engine.protocol.models import RuntimeConfig


def _runtime_config(*, retry_max: int = 3, retry_delay_ms: int = 200) -> RuntimeConfig:
    return RuntimeConfig(
        cycle_interval_ms=1000,
        ack_timeout_ms=5000,
        retry_max=retry_max,
        retry_delay_ms=retry_delay_ms,
        data_stale_threshold_ms=15000,
        cycle_max_duration_ms=30000,
        metrics_interval_ms=60000,
        auto_discover_instances=True,
    )


def test_build_retry_policy_uses_runtime_values() -> None:
    policy = build_retry_policy(_runtime_config(retry_max=4, retry_delay_ms=150))

    assert policy.retry_max == 4
    assert policy.retry_delay_ms == 150
    assert max_retry_attempts(policy) == 5


def test_run_with_retry_respects_retry_max_limit() -> None:
    policy = RetryPolicy(retry_max=2, retry_delay_ms=0)
    attempts = {"count": 0}

    def _failing_operation() -> None:
        attempts["count"] += 1
        raise ValueError("io failed")

    with pytest.raises(ValueError, match="io failed"):
        run_with_retry(policy, _failing_operation, sleep_fn=lambda _: None)

    assert attempts["count"] == 3


def test_run_with_retry_waits_retry_delay_between_attempts() -> None:
    policy = RetryPolicy(retry_max=2, retry_delay_ms=250)
    attempts = {"count": 0}
    delays: list[float] = []

    def _failing_operation() -> None:
        attempts["count"] += 1
        raise RuntimeError("temporary io failure")

    with pytest.raises(RuntimeError, match="temporary io failure"):
        run_with_retry(
            policy,
            _failing_operation,
            sleep_fn=delays.append,
        )

    assert attempts["count"] == 3
    assert delays == [0.25, 0.25]


def test_run_with_retry_returns_result_on_success() -> None:
    policy = RetryPolicy(retry_max=2, retry_delay_ms=0)
    attempts = {"count": 0}

    def _flaky_operation() -> str:
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise OSError("temporary failure")
        return "ok"

    result = run_with_retry(policy, _flaky_operation, sleep_fn=lambda _: None)

    assert result == "ok"
    assert attempts["count"] == 3


def test_validate_control_command_retry_rejects_same_command_id() -> None:
    with pytest.raises(ExecutionError, match="must not be retried with the same command_id"):
        validate_control_command_retry(
            previous_command_id="cmd-1",
            command_id="cmd-1",
        )


def test_validate_control_command_retry_allows_new_command_id() -> None:
    validate_control_command_retry(
        previous_command_id="cmd-1",
        command_id="cmd-2",
    )


def test_run_with_retry_emits_retry_alert_before_final_failure(tmp_path: Path) -> None:
    from engine.core.logging_setup import setup_system_logger
    from engine.core.paths import SystemPaths

    policy = RetryPolicy(retry_max=1, retry_delay_ms=0)
    paths = SystemPaths(tmp_path)
    paths.ensure_directories()
    logger = setup_system_logger(paths, level="INFO", format_name="standard")
    log_path = paths.logs_dir / sorted(paths.logs_dir.glob("system_*.log"))[0]

    def _failing_operation() -> None:
        raise OSError("temporary failure")

    with pytest.raises(OSError, match="temporary failure"):
        run_with_retry(
            policy,
            _failing_operation,
            sleep_fn=lambda _: None,
            alert_context=RetryAlertContext(
                logger=logger,
                operation="atomic read",
            ),
        )

    log_text = log_path.read_text(encoding="utf-8")
    assert "alert code=RETRY" in log_text
