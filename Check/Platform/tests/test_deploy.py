"""Deploy + paths smoke tests."""

from __future__ import annotations

from pathlib import Path

from app import clients, paths


def test_app_root_points_at_platform() -> None:
    root = paths.app_root()
    assert (root / "app").is_dir() or (root / "mt4").exists() or (root / "config").exists()


def test_deploy_mt4_copies_ea(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(paths, "app_root", lambda: tmp_path)
    ea = tmp_path / "mt4" / "CHECK.mq4"
    ea.parent.mkdir(parents=True)
    ea.write_text("// check ea\n", encoding="utf-8")
    (tmp_path / "config").mkdir(parents=True)
    (tmp_path / "clients").mkdir(parents=True)

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
    assert "Deployed" in msg


def test_add_client_creates_workspace(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(paths, "app_root", lambda: tmp_path)
    (tmp_path / "mt4").mkdir(parents=True)
    (tmp_path / "mt4" / "CHECK.mq4").write_text("//ea\n", encoding="utf-8")
    (tmp_path / "config").mkdir(parents=True)
    monkeypatch.setenv("APPDATA", str(tmp_path / "no_appdata"))

    paths.ensure_layout(tmp_path)
    c = clients.add(login="111", password="x", server="Demo", label="t1", lot=0.03)
    assert c["id"] == "t1"
    assert (tmp_path / "clients" / "t1" / "client.json").exists()
    assert (tmp_path / "clients" / "t1" / "bridge" / "market").is_dir()
    assert (tmp_path / "clients" / "t1" / "launch_mt4.bat").exists()
    bat = (tmp_path / "clients" / "t1" / "launch_mt4.bat").read_text(encoding="ascii")
    assert "Missing terminal.exe" in bat
    assert "—" not in bat  # no unicode dash (breaks Windows cmd)
    clients.delete(c["id"])
    assert not (tmp_path / "clients" / "t1").exists()


def test_find_terminal_exe_detects_install(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ProgramFiles", str(tmp_path / "pf"))
    monkeypatch.setenv("ProgramFiles(x86)", str(tmp_path / "pf86"))
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    term = tmp_path / "pf" / "MyBroker MT4" / "terminal.exe"
    term.parent.mkdir(parents=True)
    term.write_bytes(b"mz")
    found = clients.find_terminal_exe()
    assert found is not None
    assert found.name == "terminal.exe"
