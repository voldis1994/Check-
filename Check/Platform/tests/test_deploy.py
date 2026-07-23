"""Deploy MT4 helper."""

from __future__ import annotations

from pathlib import Path

from app import clients


def test_deploy_mt4_copies_ea(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(clients, "ROOT", tmp_path)
    ea = tmp_path / "mt4" / "CHECK.mq4"
    ea.parent.mkdir(parents=True)
    ea.write_text("// check ea\n", encoding="utf-8")

    appdata = tmp_path / "AppData"
    term = appdata / "MetaQuotes" / "Terminal" / "ABC123" / "MQL4"
    (term / "Experts").mkdir(parents=True)
    (term / "Files").mkdir(parents=True)
    monkeypatch.setenv("APPDATA", str(appdata))

    n, msg = clients.deploy_mt4()
    assert n == 1
    assert (term / "Experts" / "CHECK.mq4").exists()
    assert (term / "Files" / "CHECK" / "market").is_dir()
    assert (term / "Files" / "CHECK" / "commands").is_dir()
    assert "deployed" in msg.lower()
