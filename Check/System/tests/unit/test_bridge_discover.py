"""Bridge discovery tests."""

from __future__ import annotations

from pathlib import Path

from checktrader.execution.bridge_discover import (
    BridgeLocation,
    list_active_bridges,
    resolve_bridge_directory,
    stick_or_resolve_bridge,
)
from checktrader.state.store import account_state_path


def _write_pair(bridge: Path, tag: str) -> None:
    (bridge / "market").mkdir(parents=True, exist_ok=True)
    (bridge / "status").mkdir(parents=True, exist_ok=True)
    (bridge / "market" / f"{tag}.json").write_text(
        f'{{"sequence":1,"generated_at_utc":"2026-01-01T00:00:00Z","tag":"{tag}"}}',
        encoding="utf-8",
    )
    (bridge / "status" / f"{tag}.json").write_text(
        f'{{"sequence":1,"generated_at_utc":"2026-01-01T00:00:00Z","tag":"{tag}"}}',
        encoding="utf-8",
    )


def test_resolve_prefers_configured_when_populated(tmp_path: Path, monkeypatch) -> None:
    configured = tmp_path / "system" / "runtime" / "bridge"
    _write_pair(configured, "cfg")
    monkeypatch.delenv("APPDATA", raising=False)
    loc = resolve_bridge_directory(configured_bridge=configured)
    assert loc.source == "config"
    assert loc.bridge_root == configured


def test_resolve_uses_mt4_files_when_config_empty(tmp_path: Path, monkeypatch) -> None:
    appdata = tmp_path / "appdata"
    term = appdata / "MetaQuotes" / "Terminal" / "ABCDEF"
    mt4_bridge = term / "MQL4" / "Files" / "CHECK_SYSTEM" / "runtime" / "bridge"
    _write_pair(mt4_bridge, "mt4")
    monkeypatch.setenv("APPDATA", str(appdata))
    configured = tmp_path / "system" / "runtime" / "bridge"
    configured.mkdir(parents=True)
    loc = resolve_bridge_directory(configured_bridge=configured)
    assert "mt4" in loc.source
    assert loc.bridge_root == mt4_bridge


def test_list_active_bridges_returns_all_terminals(tmp_path: Path, monkeypatch) -> None:
    appdata = tmp_path / "appdata"
    a = appdata / "MetaQuotes" / "Terminal" / "AAAA" / "MQL4" / "Files" / "CHECK_SYSTEM" / "runtime" / "bridge"
    b = appdata / "MetaQuotes" / "Terminal" / "BBBB" / "MQL4" / "Files" / "CHECK_SYSTEM" / "runtime" / "bridge"
    _write_pair(a, "a")
    _write_pair(b, "b")
    monkeypatch.setenv("APPDATA", str(appdata))
    configured = tmp_path / "system" / "runtime" / "bridge"
    configured.mkdir(parents=True)
    active = list_active_bridges(configured_bridge=configured)
    roots = {item.bridge_root for item in active}
    assert a in roots
    assert b in roots
    assert len(active) == 2


def test_sticky_keeps_locked_bridge_when_other_is_newer(tmp_path: Path, monkeypatch) -> None:
    appdata = tmp_path / "appdata"
    a = appdata / "MetaQuotes" / "Terminal" / "AAAA" / "MQL4" / "Files" / "CHECK_SYSTEM" / "runtime" / "bridge"
    b = appdata / "MetaQuotes" / "Terminal" / "BBBB" / "MQL4" / "Files" / "CHECK_SYSTEM" / "runtime" / "bridge"
    _write_pair(a, "a")
    _write_pair(b, "b")
    newer = b / "market" / "b.json"
    newer.write_text('{"sequence":9,"generated_at_utc":"2026-01-01T00:00:09Z"}', encoding="utf-8")
    monkeypatch.setenv("APPDATA", str(appdata))
    configured = tmp_path / "system" / "runtime" / "bridge"
    configured.mkdir(parents=True)
    locked = BridgeLocation(a, "mt4-files:AAAA")
    loc, missing, relocked = stick_or_resolve_bridge(
        configured_bridge=configured,
        locked=locked,
        missing_cycles=0,
    )
    assert not relocked
    assert missing == 0
    assert loc.bridge_root == a


def test_account_state_path_isolated() -> None:
    root = Path("/tmp/system")
    p1 = account_state_path(root, "runtime/state", "231054")
    p2 = account_state_path(root, "runtime/state", "231443")
    assert p1 != p2
    assert p1.name == "231054.json"
    assert "accounts" in str(p1)
