"""Engine paper / live command behaviour."""

from __future__ import annotations

import json
from pathlib import Path

from app import paths
from app.engine import Engine


def _write_bridge(bridge: Path, *, symbol: str = "EURUSD") -> None:
    bars = []
    price = 1.1000
    for _ in range(35):
        bars.append({"o": price, "h": price + 0.0008, "l": price - 0.0005, "c": price, "v": 1})
        price += 0.00005
    # breakout bar
    bars.append({"o": 1.1020, "h": 1.1040, "l": 1.1018, "c": 1.1035, "v": 1})
    market = {
        "symbol": symbol,
        "bid": 1.1034,
        "ask": 1.1035,
        "digits": 5,
        "bars_m1": bars,
        "account": "111",
    }
    status = {"account": "111", "positions": [], "equity": 10000, "connected": True}
    for name in ("market", "status", "commands", "acks"):
        (bridge / name).mkdir(parents=True, exist_ok=True)
    (bridge / "market" / "latest.json").write_text(json.dumps(market), encoding="utf-8")
    (bridge / "status" / "latest.json").write_text(json.dumps(status), encoding="utf-8")


def test_paper_does_not_write_commands(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(paths, "app_root", lambda: tmp_path)
    paths.ensure_layout(tmp_path)
    (tmp_path / "config" / "defaults.json").write_text(
        json.dumps(
            {
                "lot": 0.02,
                "sl_atr": 1.0,
                "breakout": True,
                "trend": False,
                "force_idle": False,
                "cycle_sec": 1,
                "magic": 40001,
                "symbol": "AUTO",
            }
        ),
        encoding="utf-8",
    )
    bridge = tmp_path / "clients" / "demo" / "bridge"
    _write_bridge(bridge)

    eng = Engine()
    eng.mode = "paper"
    eng.running = True
    eng._cycle()
    cmds = list((bridge / "commands").glob("cmd_*.json"))
    assert cmds == []
    assert eng.last_reason.startswith("PAPER_")


def test_live_writes_open_command(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(paths, "app_root", lambda: tmp_path)
    paths.ensure_layout(tmp_path)
    (tmp_path / "config" / "defaults.json").write_text(
        json.dumps(
            {
                "lot": 0.02,
                "sl_atr": 1.0,
                "breakout": True,
                "trend": False,
                "force_idle": False,
                "cycle_sec": 1,
                "magic": 40001,
                "symbol": "AUTO",
            }
        ),
        encoding="utf-8",
    )
    bridge = tmp_path / "clients" / "demo" / "bridge"
    _write_bridge(bridge)

    eng = Engine()
    eng.mode = "live"
    eng.running = True
    eng._cycle()
    cmds = list((bridge / "commands").glob("cmd_*.json"))
    assert len(cmds) == 1
    payload = json.loads(cmds[0].read_text(encoding="utf-8"))
    assert payload["action"] == "OPEN"
    assert payload["side"] == "BUY"
