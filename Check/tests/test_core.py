"""Boot + core for Nexus 1:1 desk."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app import automation, clients, copier, paths
from app.risk import block_new_entries
from app.strategy import evaluate, manage_sl

tk = pytest.importorskip("tkinter")


def test_app_builds_all_pages() -> None:
    from app.main import App, NAV

    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"no Tk: {exc}")
    root.withdraw()
    try:
        app = App(root)
        assert hasattr(app, "live_var")
        assert hasattr(app, "chart")
        for key, _ in NAV:
            app._show(key)
        app.refresh()
    finally:
        root.destroy()


def _bars_breakout() -> list[dict]:
    bars = []
    for _ in range(35):
        bars.append({"o": 1.1000, "h": 1.1008, "l": 1.0992, "c": 1.1000, "v": 1})
    bars.append({"o": 1.1000, "h": 1.1025, "l": 1.1000, "c": 1.1022, "v": 1})
    return bars


def test_strategies_and_toggles() -> None:
    market = {"bars_m1": _bars_breakout(), "bid": 1.1021, "ask": 1.1022, "point": 0.00001}
    assert evaluate(market, {"sl_points": 100}, {"breakout": True, "trend": False}) is not None
    assert manage_sl("BUY", 1.0, 1.001, 0.999, 0.00001, {"be_enabled": False, "trail_enabled": False}) is None


def test_block_and_hours() -> None:
    assert block_new_entries(
        account={"sl_points": 100, "daily_loss_limit_enabled": True, "daily_loss_limit": 50, "max_open_trades_enabled": False, "spread_filter_enabled": False},
        global_cfg={},
        positions=[],
        spread_points=1,
        equity=1000,
        daily_pl=-80,
        consecutive_losses=0,
        total_open=0,
    ) == "DAILY_LOSS"
    cfg = automation.load()
    cfg["trading_hours_enabled"] = True
    cfg["hours"] = {"0": {"on": False, "start": 0, "end": 23}}
    assert automation.within_trading_hours(cfg, 0, 12) is False


def test_copier_save(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(paths, "app_root", lambda: tmp_path)
    paths.ensure_layout(tmp_path)
    copier.save({"enabled": True, "master_id": "a", "followers": [{"id": "b", "lot": 0.03, "enabled": True}]})
    got = copier.load()
    assert got["enabled"] is True
    assert got["followers"][0]["lot"] == 0.03


def test_add_client(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(paths, "app_root", lambda: tmp_path)
    paths.ensure_layout(tmp_path)
    master = tmp_path / "instances" / "_master"
    (master / "MQL4" / "Experts").mkdir(parents=True)
    (master / "terminal.exe").write_bytes(b"mz")
    (tmp_path / "mt4").mkdir(exist_ok=True)
    (tmp_path / "mt4" / "CHECK.mq4").write_text("//ea\n", encoding="utf-8")
    (tmp_path / "runtime" / "master_mt4.txt").write_text(str(master), encoding="utf-8")
    c = clients.add(login="1", password="x", server="S", label="n1")
    assert c["id"] == "n1"


def test_engine_tracks_loss_streak(tmp_path: Path, monkeypatch) -> None:
    from app.engine import Engine

    monkeypatch.setattr(paths, "app_root", lambda: tmp_path)
    paths.ensure_layout(tmp_path)
    (tmp_path / "clients" / "demo").mkdir(parents=True)
    (tmp_path / "clients" / "demo" / "client.json").write_text(
        json.dumps({"id": "demo", "login": "111", "lot": 0.02, "sl_points": 100, "consecutive_losses": 0}),
        encoding="utf-8",
    )
    eng = Engine()
    acc = clients.read("demo")
    eng._seen_pos["k"] = {7: {"ticket": 7, "profit": -12.5, "symbol": "EURUSD", "side": "BUY"}}
    eng._track_closes("k", acc, [])
    assert clients.read("demo")["consecutive_losses"] == 1
