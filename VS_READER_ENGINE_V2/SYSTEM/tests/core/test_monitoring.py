from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from engine.core.cycle import InstanceCycleResult
from engine.core.instance import Instance
from engine.core.lifecycle import startup
from engine.core.monitoring import (
    MonitoringState,
    build_instance_metrics,
    compute_elapsed_ms,
    is_data_stale,
    log_runtime_monitoring_summary,
    observe_instance_cycle,
    resolve_instance_health,
)
from engine.core.orchestrator import run_runtime_cycles
from engine.core.paths import SystemPaths
from engine.execution.engine import ExecutionResult
from engine.execution.command import OrderCommand
from engine.execution.ack_reader import build_ack_timeout_interpretation
from engine.protocol.constants import Decision, OrderAction, RiskResult
from tests.core.config_payload import FIXTURE_CYCLE_UTC, valid_system_config_payload


FIXTURES_DIR = Path(__file__).parent.parent / "loader" / "fixtures"


def _write_config(root: Path) -> Path:
    payload = valid_system_config_payload()
    payload["system"]["root_path"] = str(root)
    payload["analysis"] = {**payload["analysis"], "lookback_bars": 3}
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


def test_observe_instance_cycle_logs_metrics(tmp_path: Path) -> None:
    runtime, instance = _startup_runtime(tmp_path)
    state = observe_instance_cycle(
        runtime,
        instance,
        InstanceCycleResult(
            instance=instance,
            timestamp_utc="2026-07-07T06:00:10.000Z",
            completed=True,
            error_logged=False,
        ),
        state=MonitoringState(),
    )
    assert isinstance(state, MonitoringState)
    for handler in runtime.system_logger.handlers:
        handler.flush()
    assert "metrics account=12345" in _read_system_log(runtime.paths)


def test_observe_instance_cycle_increments_error_count_on_failure(tmp_path: Path) -> None:
    runtime, instance = _startup_runtime(tmp_path)
    state = observe_instance_cycle(
        runtime,
        instance,
        InstanceCycleResult(
            instance=instance,
            timestamp_utc="2026-07-07T06:00:00.000Z",
            completed=False,
            error_logged=True,
        ),
    )
    assert state.error_counts[instance.instance_key] == 1


def test_build_instance_metrics_sets_blocked_health_for_block_decision() -> None:
    from engine.decision.engine import DecisionResult
    from engine.decision.buy import BuyCandidate
    from engine.decision.sell import SellCandidate
    from engine.analysis.context import AnalysisContext

    instance = _instance()
    decision = DecisionResult(
        decision_id="decision-1",
        decision=Decision.BLOCK.value,
        reason=f"BLOCK: ACCOUNT_NOT_TRADEABLE",
        preferred_side="NONE",
        buy_candidate=BuyCandidate(
            valid=False,
            invalid_reason="blocked",
            entry_price=0.0,
            stop_loss=0.0,
            take_profit=0.0,
            component_scores={},
            buy_score=0.0,
        ),
        sell_candidate=SellCandidate(
            valid=False,
            invalid_reason="blocked",
            entry_price=0.0,
            stop_loss=0.0,
            take_profit=0.0,
            component_scores={},
            sell_score=0.0,
        ),
        buy_score=0.0,
        sell_score=0.0,
        analysis_context=AnalysisContext(
            session="LONDON",
            regime="trending",
            news_active=False,
            context_quality=0.9,
            trade_environment="FAVORABLE",
            spread_filter_passed=True,
        ),
    )
    metrics = build_instance_metrics(
        instance,
        InstanceCycleResult(
            instance=instance,
            timestamp_utc="2026-07-07T06:00:10.000Z",
            completed=True,
            error_logged=False,
            decision_result=decision,
        ),
        market_timestamp_utc="2026-07-07T06:00:00.000Z",
        measured_ack_latency_ms=None,
        ack_timeout_ms=5000,
        current_utc="2026-07-07T06:00:10.000Z",
        error_count=0,
        error_rate_per_min=0.0,
    )
    assert resolve_instance_health(
        InstanceCycleResult(
            instance=instance,
            timestamp_utc="2026-07-07T06:00:10.000Z",
            completed=True,
            error_logged=False,
            decision_result=decision,
        )
    ) == "BLOCKED"
    assert metrics.instance_health == "BLOCKED"


def test_log_runtime_monitoring_summary_writes_summary_line(tmp_path: Path) -> None:
    runtime, _ = _startup_runtime(tmp_path)
    log_runtime_monitoring_summary(
        runtime,
        instance_count=2,
        completed_count=1,
        failed_count=1,
        total_errors=1,
    )
    for handler in runtime.system_logger.handlers:
        handler.flush()
    assert "runtime monitoring summary" in _read_system_log(runtime.paths)


def test_run_runtime_cycles_writes_monitoring_metrics_to_log(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime, instance = _startup_runtime(tmp_path)

    def _mock_run_execution_engine(**kwargs: object) -> ExecutionResult:
        from engine.execution.command import build_order_command

        decision_result = kwargs["decision_result"]
        risk_engine_result = kwargs["risk_engine_result"]
        order_command = build_order_command(decision_result, risk_engine_result)
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
    assert "metrics account=12345" in log_text
    assert "runtime monitoring summary" in log_text


def test_compute_elapsed_ms_is_non_negative() -> None:
    assert compute_elapsed_ms("2026-07-07T06:00:10.000Z", "2026-07-07T06:00:00.000Z") == 0


def test_is_data_stale_respects_zero_threshold() -> None:
    assert is_data_stale(100000, 0) is False
