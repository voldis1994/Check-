from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine.ai_decision_layer import AIDecision
from engine.core.cycle import run_instance_cycle
from engine.protocol.constants import Decision, RiskResult
from tests.integration.test_decision_pipeline import (
    _parse_journal_lines,
    _startup_runtime,
    run_instance_decision_pipeline,
)


def test_integration_pipeline_logs_ai_fields(tmp_path: Path) -> None:
    runtime, instance = _startup_runtime(tmp_path)
    result = run_instance_decision_pipeline(runtime, instance, use_global_universe=False)

    assert result.completed
    entries = _parse_journal_lines(tmp_path, instance)
    assert len(entries) == 1
    entry = entries[0]
    assert entry["ai_mode"] == "advisory"
    assert entry["ai_available"] is True
    assert entry["system_decision_before_ai"] in {
        Decision.BUY.value,
        Decision.SELL.value,
        Decision.WAIT.value,
        Decision.BLOCK.value,
    }
    assert entry["decision_after_ai"] == entry["system_decision_before_ai"] or entry[
        "decision_after_ai"
    ] in {Decision.BUY.value, Decision.SELL.value, Decision.WAIT.value, Decision.BLOCK.value}


@pytest.mark.no_ai_mock
def test_advisory_missing_api_key_falls_back_in_full_cycle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    import engine.ai_decision_layer as mdl

    def _should_not_call(*_args, **_kwargs):
        raise AssertionError("OpenAI must not be called when API key is missing")

    monkeypatch.setattr(mdl, "_call_openai", _should_not_call)

    runtime, instance = _startup_runtime(tmp_path)
    result = run_instance_cycle(
        runtime,
        instance,
        use_global_universe=False,
        timestamp_utc="2026-07-07T06:02:00.000Z",
    )

    assert result.decision_result is not None
    entries = _parse_journal_lines(tmp_path, instance)
    assert entries
    entry = entries[-1]
    assert entry["ai_mode"] == "advisory"
    assert entry["ai_available"] is False
    assert entry["ai_error_type"] == "missing_key"
    assert entry["ai_fallback_used"] is True
    assert entry["decision"] != Decision.BLOCK.value or entry["system_decision_before_ai"] == Decision.BLOCK.value


def test_ai_veto_before_risk_skips_allow_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import engine.ai_decision_layer as mdl

    def _reject_all(*_args, **_kwargs) -> str:
        ai = AIDecision(
            bias="AVOID",
            confidence=0.9,
            allow_buy=False,
            allow_sell=False,
            allow_close=True,
            reason="mock avoid",
        )
        return json.dumps(
            {
                "bias": ai.bias,
                "confidence": ai.confidence,
                "allow_buy": ai.allow_buy,
                "allow_sell": ai.allow_sell,
                "allow_close": ai.allow_close,
                "reason": ai.reason,
            }
        )

    monkeypatch.setattr(mdl, "_call_openai", _reject_all)

    runtime, instance = _startup_runtime(tmp_path)
    result = run_instance_decision_pipeline(runtime, instance, use_global_universe=False)

    assert result.completed
    assert result.decision_result is not None
    assert result.decision_result.decision == Decision.BLOCK.value
    assert result.risk_engine_result is not None
    assert result.risk_engine_result.result == RiskResult.BLOCK.value
    assert "ai_veto_avoid" in result.decision_result.reason


def test_risk_runs_after_ai_veto_aligns_journal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import engine.ai_decision_layer as mdl

    def _reject_all(*_args, **_kwargs) -> str:
        return json.dumps(
            {
                "bias": "AVOID",
                "confidence": 0.9,
                "allow_buy": False,
                "allow_sell": False,
                "allow_close": True,
                "reason": "integration risk order check",
            }
        )

    monkeypatch.setattr(mdl, "_call_openai", _reject_all)

    runtime, instance = _startup_runtime(tmp_path)
    result = run_instance_decision_pipeline(runtime, instance, use_global_universe=False)

    assert result.completed
    assert result.decision_result is not None
    assert result.decision_result.decision == Decision.BLOCK.value
    assert result.risk_engine_result is not None
    assert result.risk_engine_result.result == RiskResult.BLOCK.value
    entry = _parse_journal_lines(tmp_path, instance)[-1]
    assert entry["decision"] == Decision.BLOCK.value
    assert entry["risk_result"] == RiskResult.BLOCK.value
    assert entry["decision_after_ai"] == Decision.BLOCK.value


@pytest.mark.no_ai_mock
def test_required_mode_blocks_without_api_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from engine.core.lifecycle import startup
    from tests.core.config_payload import valid_system_config_payload
    from tests.integration.test_data_pipeline import _install_integration_fixtures, _instance

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    payload = valid_system_config_payload()
    payload["system"]["root_path"] = str(tmp_path)
    payload["analysis"]["lookback_bars"] = 3
    payload["ai"] = {
        "mode": "required",
        "fail_closed": True,
        "reject_action": "BLOCK",
        "timeout_ms": 10000,
        "retry_max": 2,
        "retry_delay_ms": 500,
    }
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "system.json"
    config_path.write_text(json.dumps(payload), encoding="utf-8")

    instance = _instance()
    from engine.core.paths import SystemPaths

    _install_integration_fixtures(SystemPaths(tmp_path), instance)
    runtime = startup(root_path=tmp_path, config_path=config_path)

    result = run_instance_decision_pipeline(runtime, instance, use_global_universe=False)

    assert result.completed
    assert result.decision_result is not None
    assert result.decision_result.decision == Decision.BLOCK.value
    assert result.decision_result.reason == "ai_required_missing_block"
