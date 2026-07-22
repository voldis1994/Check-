"""Bridge discovery tests."""

from __future__ import annotations

from pathlib import Path

from checktrader.execution.bridge_discover import resolve_bridge_directory


def test_resolve_prefers_configured_when_populated(tmp_path: Path, monkeypatch) -> None:
    configured = tmp_path / "system" / "runtime" / "bridge"
    (configured / "market").mkdir(parents=True)
    (configured / "status").mkdir(parents=True)
    (configured / "market" / "m.json").write_text(
        '{"sequence":1,"generated_at_utc":"2026-01-01T00:00:00Z"}', encoding="utf-8"
    )
    (configured / "status" / "s.json").write_text(
        '{"sequence":1,"generated_at_utc":"2026-01-01T00:00:00Z"}', encoding="utf-8"
    )
    monkeypatch.delenv("APPDATA", raising=False)
    loc = resolve_bridge_directory(configured_bridge=configured)
    assert loc.source == "config"
    assert loc.bridge_root == configured


def test_resolve_uses_mt4_files_when_config_empty(tmp_path: Path, monkeypatch) -> None:
    appdata = tmp_path / "appdata"
    term = appdata / "MetaQuotes" / "Terminal" / "ABCDEF"
    mt4_bridge = term / "MQL4" / "Files" / "CHECK_SYSTEM" / "runtime" / "bridge"
    (mt4_bridge / "market").mkdir(parents=True)
    (mt4_bridge / "status").mkdir(parents=True)
    (mt4_bridge / "market" / "m.json").write_text(
        '{"sequence":2,"generated_at_utc":"2026-01-01T00:00:01Z"}', encoding="utf-8"
    )
    (mt4_bridge / "status" / "s.json").write_text(
        '{"sequence":2,"generated_at_utc":"2026-01-01T00:00:01Z"}', encoding="utf-8"
    )
    monkeypatch.setenv("APPDATA", str(appdata))
    configured = tmp_path / "system" / "runtime" / "bridge"
    configured.mkdir(parents=True)
    loc = resolve_bridge_directory(configured_bridge=configured)
    assert "mt4" in loc.source
    assert loc.bridge_root == mt4_bridge
