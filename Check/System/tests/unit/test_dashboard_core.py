from __future__ import annotations

import json
import sys
import time
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[2] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from dashboard_core import (  # noqa: E402
    clear_stop,
    collect_health,
    format_age,
    format_audit_line,
    resolve_config,
    runtime_dir,
    write_stop,
)


def test_resolve_config_prefers_system_json(tmp_path: Path, monkeypatch) -> None:
    root = Path(__file__).resolve().parents[2]
    monkeypatch.chdir(root)
    path = resolve_config()
    assert path.name in {"system.json", "system.example.json"}
    assert path.exists()


def test_format_audit_line_and_age() -> None:
    line = format_audit_line(
        {
            "completed_at": "2026-07-22T16:00:00+00:00",
            "symbol": "NATURALGAS",
            "account_number": "231054",
            "decision": "WAIT",
            "reason_code": "NO_SETUP",
            "market_regime": "RANGE",
            "selected_strategy": "RANGE_REVERSION",
        }
    )
    assert "NATURALGAS" in line
    assert "decision=WAIT" in line
    assert format_age(None) == "missing"
    assert format_age(0.5) == "fresh"
    assert format_age(45).startswith("STALE")


def test_preferred_json_ignores_legacy_when_v3_present(tmp_path: Path) -> None:
    import dashboard_core as core

    folder = tmp_path / "market"
    folder.mkdir()
    legacy = folder / "market_NATURALGAS_19942026.json"
    legacy.write_text("{}", encoding="utf-8")
    time.sleep(0.05)
    v3 = folder / "231054_NATURALGAS_market.json"
    v3.write_text("{}", encoding="utf-8")
    # Make legacy appear newer on mtime
    legacy.write_text('{"old":true}', encoding="utf-8")
    chosen = core._preferred_json(folder, role="market")
    assert chosen is not None
    assert chosen.name.endswith("_market.json")

    latest = folder / "latest.json"
    latest.write_text("{}", encoding="utf-8")
    assert core._preferred_json(folder, role="market") == latest


def test_collect_health_and_stop(tmp_path: Path, monkeypatch) -> None:
    import dashboard_core as core

    monkeypatch.setattr(core, "ROOT", tmp_path)
    cfg = {
        "runtime": {"mode": "paper", "trading_enabled": False},
        "instrument": {"symbol": "AUTO"},
        "paths": {"runtime_dir": "runtime", "audit_file": "runtime/audit.jsonl", "bridge_dir": "runtime/bridge"},
    }
    config_path = tmp_path / "config" / "system.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(json.dumps(cfg), encoding="utf-8")

    bridge = tmp_path / "runtime" / "bridge" / "market"
    bridge.mkdir(parents=True)
    (bridge / "latest.json").write_text("{}", encoding="utf-8")
    (tmp_path / "runtime" / "bridge" / "status").mkdir(parents=True)
    (tmp_path / "runtime" / "bridge" / "status" / "latest.json").write_text("{}", encoding="utf-8")
    audit = tmp_path / "runtime" / "audit.jsonl"
    audit.parent.mkdir(parents=True, exist_ok=True)
    audit.write_text(
        json.dumps(
            {
                "completed_at": "2026-07-22T16:00:00Z",
                "decision": "BLOCK",
                "reason_code": "RISK",
                "symbol": "AUTO",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    health = collect_health(config_path)
    assert health.mode == "paper"
    assert health.symbol == "AUTO"
    assert health.stop_present is False
    assert len(health.bridges) >= 1
    assert health.last_audit is not None
    assert health.last_audit["decision"] == "BLOCK"

    rt = runtime_dir(cfg)
    stop = write_stop(rt)
    assert stop.exists()
    assert clear_stop(rt) is True
    assert clear_stop(rt) is False
