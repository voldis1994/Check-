"""Boot smoke for CHECK v5 desk."""

from __future__ import annotations

import pytest

tk = pytest.importorskip("tkinter")


def test_app_builds() -> None:
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
        app.refresh()
        app._show("accounts")
        app._show("global")
        app._show("live")
        app.refresh()
    finally:
        root.destroy()
