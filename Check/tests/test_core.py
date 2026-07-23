"""Risk toggles + hard numbers + strategy."""

from __future__ import annotations

import json
from pathlib import Path

from app import clients, paths
from app.risk import block_new_entries
from app.strategy import evaluate, manage_sl


def _bars_breakout() -> list[dict]:
    bars = []
    for _ in range(35):
        bars.append({"o": 1.1000, "h": 1.1008, "l": 1.0992, "c": 1.1000, "v": 1})
    bars.append({"o": 1.1000, "h": 1.1025, "l": 1.1000, "c": 1.1022, "v": 1})
    return bars


def test_block_daily_loss_hard_dollars() -> None:
    acc = {
        "sl_points": 100,
        "daily_loss_limit_enabled": True,
        "daily_loss_limit": 200,
        "max_open_trades_enabled": False,
        "spread_filter_enabled": False,
    }
    assert block_new_entries(
        account=acc,
        global_cfg={},
        positions=[],
        spread_points=10,
        equity=9800,
        daily_pl=-250,
        consecutive_losses=0,
        total_open=0,
    ) == "DAILY_LOSS"


def test_block_when_toggle_off_allows() -> None:
    acc = {
        "sl_points": 100,
        "daily_loss_limit_enabled": False,
        "daily_loss_limit": 200,
        "max_open_trades_enabled": False,
        "spread_filter_enabled": False,
    }
    assert (
        block_new_entries(
            account=acc,
            global_cfg={},
            positions=[],
            spread_points=10,
            equity=9800,
            daily_pl=-250,
            consecutive_losses=0,
            total_open=0,
        )
        is None
    )


def test_trail_respects_toggle_off() -> None:
    account = {
        "be_enabled": False,
        "trail_enabled": False,
        "be_start_points": 10,
        "trail_start_points": 10,
        "trail_lock_points": 5,
        "sl_points": 100,
    }
    assert manage_sl("BUY", 1.0, 1.001, 0.999, 0.00001, account) is None


def test_breakout_hard_sl_points() -> None:
    market = {"bars_m1": _bars_breakout(), "bid": 1.1021, "ask": 1.1022, "point": 0.00001}
    sig = evaluate(market, {"sl_points": 100}, {"breakout": True, "trend": False})
    assert sig is not None
    assert abs(sig.sl - (1.1022 - 0.001)) < 1e-9


def test_add_and_update_toggles(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(paths, "app_root", lambda: tmp_path)
    paths.ensure_layout(tmp_path)
    master = tmp_path / "instances" / "_master"
    (master / "MQL4" / "Experts").mkdir(parents=True)
    (master / "terminal.exe").write_bytes(b"mz")
    (tmp_path / "mt4").mkdir(exist_ok=True)
    (tmp_path / "mt4" / "CHECK.mq4").write_text("//ea\n", encoding="utf-8")
    (tmp_path / "runtime" / "master_mt4.txt").write_text(str(master), encoding="utf-8")

    c = clients.add(login="1", password="x", server="S", label="a1", sl_points=180)
    assert c["sl_points"] == 180
    assert c["be_enabled"] is True
    clients.update_risk("a1", be_enabled=False, daily_loss_limit_enabled=True, daily_loss_limit=150)
    got = clients.read("a1")
    assert got["be_enabled"] is False
    assert got["daily_loss_limit"] == 150


def test_paper_engine(tmp_path: Path, monkeypatch) -> None:
    from app.engine import Engine

    monkeypatch.setattr(paths, "app_root", lambda: tmp_path)
    paths.ensure_layout(tmp_path)
    (tmp_path / "config" / "defaults.json").write_text(
        json.dumps({"breakout": True, "trend": False, "magic": 50001, "symbol": "AUTO"}),
        encoding="utf-8",
    )
    bridge = tmp_path / "instances" / "demo" / "MQL4" / "Files" / "CHECK"
    for name in ("market", "status", "commands", "acks"):
        (bridge / name).mkdir(parents=True)
    (bridge / "market" / "latest.json").write_text(
        json.dumps(
            {
                "symbol": "EURUSD",
                "bid": 1.1021,
                "ask": 1.1022,
                "point": 0.00001,
                "digits": 5,
                "spread": 12,
                "bars_m1": _bars_breakout(),
                "account": "111",
            }
        ),
        encoding="utf-8",
    )
    (bridge / "status" / "latest.json").write_text(
        json.dumps({"account": "111", "positions": [], "equity": 10000, "balance": 10000}),
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
                "be_enabled": True,
                "trail_enabled": True,
                "spread_filter_enabled": True,
                "max_spread_points": 40,
                "max_open_trades_enabled": True,
                "max_open_trades": 1,
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
    assert eng.last_reason.startswith("PAPER_")
