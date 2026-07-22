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
    monkeypatch.setattr(core, "_last_equity_sample_at", 0.0)
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
    (bridge / "latest.json").write_text(
        json.dumps({"payload": {"symbol": "NATURALGAS", "bid": 2.1, "ask": 2.2, "spread": 0.1}}),
        encoding="utf-8",
    )
    (tmp_path / "runtime" / "bridge" / "status").mkdir(parents=True)
    (tmp_path / "runtime" / "bridge" / "status" / "latest.json").write_text(
        json.dumps(
            {
                "payload": {
                    "account_number": "231054",
                    "balance": 10000.0,
                    "equity": 10050.0,
                    "currency": "USD",
                    "connected": True,
                    "trading_allowed": True,
                    "positions": [
                        {
                            "ticket": "1",
                            "symbol": "NATURALGAS",
                            "side": "BUY",
                            "lot": 0.1,
                            "open_price": 2.0,
                            "stop_loss": 1.9,
                            "take_profit": 2.3,
                            "profit": 50.0,
                        }
                    ],
                }
            }
        ),
        encoding="utf-8",
    )
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
    snap = health.bridges[0]
    assert snap.account_id == "231054"
    assert snap.balance == 10000.0
    assert snap.equity == 10050.0
    assert snap.floating_pl == 50.0
    assert len(snap.positions) == 1
    assert health.last_audit is not None
    assert health.last_audit["decision"] == "BLOCK"
    assert (tmp_path / "runtime" / "dashboard_equity.jsonl").exists()

    rt = runtime_dir(cfg)
    stop = write_stop(rt)
    assert stop.exists()
    assert clear_stop(rt) is True
    assert clear_stop(rt) is False


def test_equity_series_and_day_stats(tmp_path: Path, monkeypatch) -> None:
    import dashboard_core as core

    monkeypatch.setattr(core, "ROOT", tmp_path)
    monkeypatch.setattr(core, "_last_equity_sample_at", 0.0)
    rt = tmp_path / "runtime"
    rt.mkdir()
    bridges = [
        core.BridgeSnapshot(
            path=tmp_path,
            market_age_s=1.0,
            status_age_s=1.0,
            commands=0,
            acks=0,
            market_file="latest.json",
            status_file="latest.json",
            account_id="231054",
            balance=100.0,
            equity=110.0,
        )
    ]
    core.record_equity_samples(bridges, rt, force=True)
    series = core.load_equity_series("231054", limit=10, rt=rt)
    assert len(series) == 1
    assert series[0][1] == 110.0

    today = __import__("datetime").datetime.now(__import__("datetime").UTC).strftime("%Y-%m-%d")
    audit = rt / "audit.jsonl"
    audit.write_text(
        "\n".join(
            [
                json.dumps({"completed_at": f"{today}T10:00:00Z", "decision": "OPEN"}),
                json.dumps({"completed_at": f"{today}T11:00:00Z", "decision": "CLOSE"}),
                json.dumps({"completed_at": f"{today}T12:00:00Z", "decision": "BLOCK"}),
                json.dumps({"completed_at": "2020-01-01T12:00:00Z", "decision": "OPEN"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    stats = core.audit_day_stats(audit)
    assert stats["opens"] == 1
    assert stats["closes"] == 1
    assert stats["blocks"] == 1
    assert stats["acted"] == 2
    assert len(core.audit_activity(audit, limit=2)) == 2
