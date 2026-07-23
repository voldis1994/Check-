from __future__ import annotations

from pathlib import Path

from checktrader.config.account_lot import (
    account_lot_path,
    apply_account_lot_override,
    clear_account_lot,
    read_account_lot,
    write_account_lot,
)
from checktrader.config.models import SystemConfig


def test_account_lot_roundtrip(tmp_path: Path) -> None:
    path = account_lot_path(tmp_path, "231054")
    assert read_account_lot(path) is None
    write_account_lot(path, 0.05, source="test")
    assert read_account_lot(path) == 0.05
    assert clear_account_lot(path) is True
    assert read_account_lot(path) is None


def test_apply_account_lot_override(tmp_path: Path) -> None:
    cfg = SystemConfig()
    cfg = cfg.model_copy(
        update={
            "paths": cfg.paths.model_copy(update={"runtime_dir": tmp_path}),
            "account": cfg.account.model_copy(update={"account_id": "231443"}),
            "position": cfg.position.model_copy(update={"default_lot": 0.02}),
            "position_sizing": cfg.position_sizing.model_copy(update={"fixed_lot": 0.02}),
        }
    )
    assert apply_account_lot_override(cfg) is cfg

    write_account_lot(account_lot_path(tmp_path, "231443"), 0.07)
    patched = apply_account_lot_override(cfg)
    assert patched is not cfg
    assert patched.position.default_lot == 0.07
    assert patched.position_sizing.fixed_lot == 0.07
