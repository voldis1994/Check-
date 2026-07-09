from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

import pytest

from engine.core.instance import Instance
from engine.core.lifecycle import startup
from engine.core.logging_setup import setup_system_logger
from engine.core.orchestrator import run_runtime_cycles
from engine.core.paths import SystemPaths
from engine.core.performance import (
    CycleTimingSnapshot,
    PerformanceState,
    build_instance_performance_metrics,
    flush_runtime_performance,
    format_performance_message,
    monotonic_elapsed_ms,
    observe_instance_performance,
    performance_affects_decisions,
    read_memory_rss_mb,
    record_instance_performance,
    should_emit_performance_log,
)
from engine.protocol.constants import LogLevel
from tests.core.config_payload import FIXTURE_CYCLE_UTC, valid_system_config_payload


FIXTURES_DIR = Path(__file__).parent.parent / "loader" / "fixtures"


def _write_config(root: Path) -> Path:
    payload = valid_system_config_payload()
    payload["system"]["root_path"] = str(root)
    payload["analysis"] = {**payload["analysis"], "lookback_bars": 3}
    payload["runtime"] = {**payload["runtime"], "metrics_interval_ms": 1}
    config_dir = root / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "system.json"
    config_path.write_text(json.dumps(payload), encoding="utf-8")
    return config_path


def _instance() -> Instance:
    return Instance(account_id="12345", symbol="EURUSD", magic=100001)


def _install_fixtures(paths: SystemPaths, instance: Instance) -> None:
    paths.ensure_account_directories(instance.account_id)
    account_dir = paths.account_dir(instance.account_id)
    market_csv = """time_utc,open,high,low,close,volume,symbol,timeframe,digits,point
2026-07-07T06:00:00.000Z,1.10000,1.10200,1.09900,1.10150,120,EURUSD,M1,5,0.00001
2026-07-07T06:01:00.000Z,1.10150,1.10300,1.10050,1.10220,110,EURUSD,M1,5,0.00001
2026-07-07T06:02:00.000Z,1.10220,1.10400,1.10100,1.10310,105,EURUSD,M1,5,0.00001
"""
    (account_dir / instance.market_filename()).write_text(market_csv, encoding="utf-8")
    shutil.copyfile(FIXTURES_DIR / "sensor_valid.csv", account_dir / instance.sensor_filename())
    shutil.copyfile(FIXTURES_DIR / "status_valid.json", account_dir / instance.status_filename())
    shutil.copyfile(FIXTURES_DIR / "universe_valid.json", account_dir / "universe.json")


def _startup_runtime(tmp_path: Path):
    config_path = _write_config(tmp_path)
    instance = _instance()
    _install_fixtures(SystemPaths(tmp_path), instance)
    return startup(root_path=tmp_path, config_path=config_path), instance


def _read_system_log(paths: SystemPaths) -> str:
    log_files = sorted(paths.logs_dir.glob("system_*.log"))
    assert log_files
    return log_files[-1].read_text(encoding="utf-8")


def test_performance_affects_decisions_returns_false() -> None:
    assert performance_affects_decisions() is False


def test_monotonic_elapsed_ms_is_non_negative() -> None:
    started = time.monotonic()
    time.sleep(0.01)
    assert monotonic_elapsed_ms(started) >= 10


def test_read_memory_rss_mb_returns_positive_value() -> None:
    value = read_memory_rss_mb()
    if value is None:
        pytest.skip("memory measurement unavailable on this platform")
    assert value > 0


def test_build_instance_performance_metrics_maps_timing_fields() -> None:
    metrics = build_instance_performance_metrics(
        _instance(),
        CycleTimingSnapshot(
            cycle_duration_ms=120,
            load_duration_ms=30,
            analysis_duration_ms=40,
            decision_duration_ms=20,
            io_wait_ms=30,
        ),
        memory_rss_mb=128.5,
    )
    assert metrics.cycle_duration_ms == 120
    assert metrics.load_duration_ms == 30
    assert metrics.analysis_duration_ms == 40
    assert metrics.decision_duration_ms == 20
    assert metrics.io_wait_ms == 30
    assert metrics.memory_rss_mb == pytest.approx(128.5)


def test_format_performance_message_includes_metric_names() -> None:
    metrics = build_instance_performance_metrics(
        _instance(),
        CycleTimingSnapshot(
            cycle_duration_ms=100,
            load_duration_ms=10,
            analysis_duration_ms=20,
            decision_duration_ms=30,
            io_wait_ms=10,
        ),
        memory_rss_mb=64.0,
    )
    rendered = format_performance_message(metrics)
    assert "cycle_duration_ms=100" in rendered
    assert "memory_rss_mb=64.00" in rendered


def test_should_emit_performance_log_respects_interval() -> None:
    state = PerformanceState(last_logged_monotonic=100.0)
    assert should_emit_performance_log(
        state,
        metrics_interval_ms=5000,
        current_monotonic=101.0,
    ) is False
    assert should_emit_performance_log(
        state,
        metrics_interval_ms=5000,
        current_monotonic=106.0,
    ) is True


def test_flush_runtime_performance_writes_metrics_to_system_log(tmp_path: Path) -> None:
    paths = SystemPaths(tmp_path)
    paths.ensure_directories()
    logger = setup_system_logger(paths, level=LogLevel.INFO.value, format_name="standard")
    runtime, instance = _startup_runtime(tmp_path)
    runtime.system_logger = logger

    state = PerformanceState()
    metrics = build_instance_performance_metrics(
        instance,
        CycleTimingSnapshot(
            cycle_duration_ms=50,
            load_duration_ms=10,
            analysis_duration_ms=20,
            decision_duration_ms=15,
            io_wait_ms=10,
        ),
    )
    record_instance_performance(state, metrics)
    flush_runtime_performance(runtime, state, force=True)
    for handler in logger.handlers:
        handler.flush()
    assert "performance account=12345" in _read_system_log(paths)
    assert "cycle_duration_ms=50" in _read_system_log(paths)


def test_observe_instance_performance_records_pending_metrics(tmp_path: Path) -> None:
    runtime, instance = _startup_runtime(tmp_path)
    state = PerformanceState()
    metrics, updated = observe_instance_performance(
        runtime,
        instance,
        CycleTimingSnapshot(
            cycle_duration_ms=80,
            load_duration_ms=12,
            analysis_duration_ms=25,
            decision_duration_ms=18,
            io_wait_ms=12,
        ),
        state=state,
    )
    assert metrics.cycle_duration_ms == 80
    assert len(updated.pending_metrics) == 1


def test_run_instance_cycle_measures_cycle_duration_ms(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime, instance = _startup_runtime(tmp_path)

    def _mock_run_execution_engine(**kwargs: object):
        from engine.execution.command import build_order_command
        from engine.execution.engine import ExecutionResult

        order_command = build_order_command(kwargs["decision_result"], kwargs["risk_engine_result"])
        return ExecutionResult(
            order_command=order_command,
            control_published=False,
            trade_intent_logged=False,
            ack_interpretation=None,
            trade_journal_entry=None,
            state_updated=False,
        )

    monkeypatch.setattr("engine.core.cycle.run_execution_engine", _mock_run_execution_engine)

    from engine.core.cycle import run_instance_cycle

    result = run_instance_cycle(
        runtime,
        instance,
        use_global_universe=False,
        timestamp_utc=FIXTURE_CYCLE_UTC,
    )
    assert result.performance_timings is not None
    assert result.performance_timings.cycle_duration_ms >= 0
    assert result.performance_timings.load_duration_ms >= 0


def test_run_runtime_cycles_logs_performance_metrics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime, instance = _startup_runtime(tmp_path)

    def _mock_run_execution_engine(**kwargs: object):
        from engine.execution.command import build_order_command
        from engine.execution.engine import ExecutionResult

        order_command = build_order_command(kwargs["decision_result"], kwargs["risk_engine_result"])
        return ExecutionResult(
            order_command=order_command,
            control_published=False,
            trade_intent_logged=False,
            ack_interpretation=None,
            trade_journal_entry=None,
            state_updated=False,
        )

    monkeypatch.setattr("engine.core.cycle.run_execution_engine", _mock_run_execution_engine)

    run_runtime_cycles(
        runtime,
        use_global_universe=False,
        timestamp_utc=FIXTURE_CYCLE_UTC,
    )
    for handler in runtime.system_logger.handlers:
        handler.flush()
    log_text = _read_system_log(runtime.paths)
    assert "performance account=12345" in log_text
    assert "memory_rss_mb=" in log_text


def test_performance_metrics_do_not_change_trading_flags(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime, instance = _startup_runtime(tmp_path)
    runtime.allow_control_writes = True

    def _mock_run_execution_engine(**kwargs: object):
        from engine.execution.command import build_order_command
        from engine.execution.engine import ExecutionResult

        order_command = build_order_command(kwargs["decision_result"], kwargs["risk_engine_result"])
        return ExecutionResult(
            order_command=order_command,
            control_published=False,
            trade_intent_logged=False,
            ack_interpretation=None,
            trade_journal_entry=None,
            state_updated=False,
        )

    monkeypatch.setattr("engine.core.cycle.run_execution_engine", _mock_run_execution_engine)

    before = runtime.allow_control_writes
    run_runtime_cycles(
        runtime,
        use_global_universe=False,
        timestamp_utc=FIXTURE_CYCLE_UTC,
    )
    assert runtime.allow_control_writes == before
    assert performance_affects_decisions() is False
