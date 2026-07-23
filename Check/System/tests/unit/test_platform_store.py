"""Platform store — clients + EXE settings."""

from __future__ import annotations

import json
from pathlib import Path

import platform_store as store


def test_add_update_delete_client(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(store, "ROOT", tmp_path)
    monkeypatch.setattr(store, "CLIENTS_ROOT", tmp_path / "clients")
    monkeypatch.setattr(store, "PLATFORM_FILE", tmp_path / "config" / "platform.json")
    monkeypatch.setattr(store, "REGISTRY_FILE", tmp_path / "clients" / "registry.json")

    client = store.add_client(login="231054", password="secret", server="Demo-Server", label="A1", lot=0.03)
    assert client["id"]
    assert (tmp_path / "clients" / client["id"] / "client.json").exists()
    bridge = tmp_path / "clients" / client["id"] / "bridge" / "runtime" / "bridge"
    assert (bridge / "market").is_dir()
    assert (bridge / "commands").is_dir()
    assert (tmp_path / "clients" / client["id"] / "launch_mt4.bat").exists()
    assert store.read_client(client["id"])["login"] == "231054"

    store.update_client(client["id"], lot=0.05)
    assert store.read_client(client["id"])["lot"] == 0.05
    lot_file = json.loads((tmp_path / "runtime" / "accounts" / "231054" / "lot.json").read_text(encoding="utf-8"))
    assert lot_file["fixed_lot"] == 0.05

    assert store.delete_client(client["id"]) is True
    assert not (tmp_path / "clients" / client["id"]).exists()
    assert store.list_clients() == []


def test_apply_platform_to_system_json(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(store, "ROOT", tmp_path)
    monkeypatch.setattr(store, "CLIENTS_ROOT", tmp_path / "clients")
    monkeypatch.setattr(store, "PLATFORM_FILE", tmp_path / "config" / "platform.json")
    monkeypatch.setattr(store, "REGISTRY_FILE", tmp_path / "clients" / "registry.json")
    (tmp_path / "config").mkdir(parents=True)
    system = tmp_path / "config" / "system.json"
    system.write_text(
        json.dumps(
            {
                "runtime": {"mode": "paper", "trading_enabled": False},
                "instrument": {"symbol": "EURUSD"},
                "position": {"default_lot": 0.01, "max_open_positions": 1, "allow_hedging": False},
                "position_sizing": {
                    "method": "fixed_lot",
                    "fixed_lot": 0.01,
                    "min_lot": 0.01,
                    "max_lot": 1.0,
                    "lot_step": 0.01,
                },
                "strategies": {
                    "force_stop_atr": 0.5,
                    "min_stop_atr": 0.4,
                    "force_entry_when_idle": False,
                    "trend_continuation": {"enabled": True},
                    "breakout": {"enabled": True},
                    "range_reversion": {"enabled": True},
                },
                "management": {
                    "breakeven_trigger_atr": 1.0,
                    "breakeven_offset_atr": 0.1,
                    "trailing_start_atr": 1.0,
                    "trailing_lock_atr": 1.0,
                },
                "paths": {},
            }
        ),
        encoding="utf-8",
    )
    store.save_platform(
        {
            "fixed_lot": 0.04,
            "force_stop_atr": 1.2,
            "trailing_lock_atr": 0.8,
            "trailing_start_atr": 0.4,
            "breakeven_trigger_atr": 0.6,
            "breakeven_offset_atr": 0.02,
            "trend_enabled": True,
            "breakout_enabled": True,
            "force_entry_when_idle": True,
            "symbol": "NATURALGAS",
        }
    )
    assert store.apply_platform_to_system_json(system) is True
    data = json.loads(system.read_text(encoding="utf-8"))
    assert data["runtime"]["platform_managed"] is True
    assert data["position_sizing"]["fixed_lot"] == 0.04
    assert data["strategies"]["force_stop_atr"] == 1.2
    assert data["strategies"]["range_reversion"]["enabled"] is False
    assert data["management"]["trailing_lock_atr"] == 0.8
    assert data["instrument"]["symbol"] == "NATURALGAS"
    assert data["instrument"]["timeframe_execution"] == "M1"
