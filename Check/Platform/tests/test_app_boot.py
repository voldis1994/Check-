"""Smoke-test App UI builds without AttributeError on startup."""

from __future__ import annotations

import pytest

tk = pytest.importorskip("tkinter")


def test_app_builds_and_refresh_without_crash() -> None:
    from app.main import App

    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"no Tk display: {exc}")
    root.withdraw()
    try:
        app = App(root)
        assert hasattr(app, "foot")
        assert hasattr(app, "tree")
        assert hasattr(app, "kpi")
        app.refresh()
        app._show("accounts")
        app._show("settings")
        app._show("floor")
        app.refresh()
    finally:
        root.destroy()
