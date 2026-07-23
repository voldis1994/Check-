"""Core v5 tests — no ATR, points risk."""

from __future__ import annotations

import json
from pathlib import Path

from app import clients, paths
from app.strategy import evaluate, manage_sl, points_to_price


def _bars_breakout() -> list[dict]:
    bars = []
    for _ in range(35):
        bars.append({"o": 1.1000, "h": 1.1008, "l": 1.0992, "c": 1.1000, "v": 1})
    bars.append({"o": 1.1000, "h": 1.1025, "l": 1.1000, "c": 1.1022, "v": 1})
    return bars


def test_points_to_price() -> None:
    assert abs(points_to_price(150, 0.00001) - 0.0015) < 1e-12


def test_breakout_uses_account_sl_points() -> None:
    market = {"bars_m1": _bars_breakout(), "bid": 1.1021, "ask": 1.1022, "point": 0.00001, "symbol": "EURUSD"}
    account = {"sl_points": 100}
    sig = evaluate(market, account, {"breakout": True, "trend": False})
    assert sig is not None
    assert sig.side == "BUY"
    assert abs(sig.sl - (1.1022 - 0.001)) < 1e-9


def test_no_signal_without_sl_points() -> None:
    market = {"bars_m1": _bars_breakout(), "bid": 1.1021, "ask": 1.1022, "point": 0.00001}
    assert evaluate(market, {"sl_points": 0}, {"breakout": True, "trend": True}) is None


def test_trail_points() -> None:
    account = {"be_start_points": 1000, "be_offset_points": 5, "trail_start_points": 50, "trail_lock_points": 30}
    # profit 60 points * 0.00001 = 0.0006
    new_sl = manage_sl("BUY", entry=1.0, price=1.0006, current_sl=0.999, point=0.00001, account=account)
    assert new_sl is not None
    assert abs(new_sl - (1.0006 - 0.0003)) < 1e-12


def test_add_clones_from_master(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(paths, "app_root", lambda: tmp_path)
    paths.ensure_layout(tmp_path)
    master = tmp_path / "instances" / "_master"
    (master / "MQL4" / "Experts").mkdir(parents=True)
    (master / "terminal.exe").write_bytes(b"mz")
    (tmp_path / "mt4").mkdir(exist_ok=True)
    (tmp_path / "mt4" / "CHECK.mq4").write_text("//ea\n", encoding="utf-8")
    (tmp_path / "runtime" / "master_mt4.txt").write_text(str(master), encoding="utf-8")

    c = clients.add(
        login="111",
        password="x",
        server="Demo",
        label="boss",
        sl_points=200,
        trail_lock_points=25,
    )
    assert c["id"] == "boss"
    assert c["sl_points"] == 200
    assert (tmp_path / "instances" / "boss" / "terminal.exe").exists()
    assert (tmp_path / "instances" / "boss" / "MQL4" / "Experts" / "CHECK.mq4").exists()
    assert (tmp_path / "instances" / "boss" / "MQL4" / "Files" / "CHECK" / "market").is_dir()

    clients.update_risk("boss", sl_points=333)
    assert clients.read("boss")["sl_points"] == 333


def test_paper_engine_uses_points(tmp_path: Path, monkeypatch) -> None:
    from app.engine import Engine

    monkeypatch.setattr(paths, "app_root", lambda: tmp_path)
    paths.ensure_layout(tmp_path)
    (tmp_path / "config" / "defaults.json").write_text(
        json.dumps({"breakout": True, "trend": False, "magic": 50001, "cycle_sec": 1, "symbol": "AUTO"}),
        encoding="utf-8",
    )
    # fake client + bridge
    bridge = tmp_path / "instances" / "demo" / "MQL4" / "Files" / "CHECK"
    for name in ("market", "status", "commands", "acks"):
        (bridge / name).mkdir(parents=True)
    bars = _bars_breakout()
    (bridge / "market" / "latest.json").write_text(
        json.dumps({"symbol": "EURUSD", "bid": 1.1021, "ask": 1.1022, "point": 0.00001, "digits": 5, "bars_m1": bars, "account": "111"}),
        encoding="utf-8",
    )
    (bridge / "status" / "latest.json").write_text(
        json.dumps({"account": "111", "positions": [], "equity": 1000}),
        encoding="utf-8",
    )
    (tmp_path / "clients" / "demo").mkdir(parents=True)
    (tmp_path / "clients" / "demo" / "client.json").write_text(
        json.dumps(
            {
                "id": "demo",
                "login": "111",
                "lot": 0.02,
                "sl_points": 100,
                "be_start_points": 50,
                "be_offset_points": 5,
                "trail_start_points": 80,
                "trail_lock_points": 40,
                "bridge": str(bridge),
                "mt4_dir": str(tmp_path / "instances" / "demo"),
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "clients" / "registry.json").write_text(
        json.dumps({"clients": [{"id": "demo", "login": "111"}]}),
        encoding="utf-8",
    )

    eng = Engine()
    eng.mode = "paper"
    eng.running = True
    eng._cycle()
    assert list((bridge / "commands").glob("cmd_*.json")) == []
    assert eng.last_reason.startswith("PAPER_")
