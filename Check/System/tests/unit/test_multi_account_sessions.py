from __future__ import annotations

import json
from pathlib import Path

from checktrader.app.bootstrap import bootstrap, spawn_account_context
from checktrader.app.live_loop import AccountSessionBook, resolve_account_id, safe_account_id


def test_safe_account_id() -> None:
    assert safe_account_id("231054") == "231054"
    assert safe_account_id(" 231 054 ") == "231_054"


def test_resolve_account_id_from_status(tmp_path: Path) -> None:
    bridge = tmp_path / "bridge"
    status = bridge / "status"
    status.mkdir(parents=True)
    (status / "latest.json").write_text(
        json.dumps({"account_number": "231443", "balance": 1000}),
        encoding="utf-8",
    )
    (bridge / "market").mkdir(parents=True)
    (bridge / "market" / "latest.json").write_text("{}", encoding="utf-8")
    assert resolve_account_id(bridge) == "231443"


def test_account_session_book_isolates_two_bridges(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    example = Path("/workspace/Check/System/config/system.example.json")
    cfg = tmp_path / "config" / "system.json"
    cfg.parent.mkdir(parents=True)
    raw = json.loads(example.read_text(encoding="utf-8"))
    raw["paths"]["runtime_dir"] = str(tmp_path / "runtime")
    raw["paths"]["history_file"] = str(tmp_path / "runtime" / "history.json")
    raw["paths"]["state_file"] = str(tmp_path / "runtime" / "state.json")
    raw["paths"]["audit_file"] = str(tmp_path / "runtime" / "audit.jsonl")
    raw["paths"]["metrics_file"] = str(tmp_path / "runtime" / "metrics.json")
    cfg.write_text(json.dumps(raw), encoding="utf-8")
    (tmp_path / "config" / "system.schema.json").write_text(
        Path("/workspace/Check/System/config/system.schema.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    base = bootstrap(cfg, mode_override="paper")
    book = AccountSessionBook(base)

    a = tmp_path / "termA" / "bridge"
    b = tmp_path / "termB" / "bridge"
    for bridge, acct in ((a, "231054"), (b, "231443")):
        (bridge / "market").mkdir(parents=True)
        (bridge / "status").mkdir(parents=True)
        (bridge / "market" / "latest.json").write_text("{}", encoding="utf-8")
        (bridge / "status" / "latest.json").write_text(
            json.dumps({"account_number": acct, "balance": 1}),
            encoding="utf-8",
        )

    sa = book.get(a)
    sb = book.get(b)
    assert sa.account_id == "231054"
    assert sb.account_id == "231443"
    assert sa.context.history is not sb.context.history
    assert sa.context.state is not sb.context.state
    assert sa.context.execution.bridge_dir == a
    assert sb.context.execution.bridge_dir == b
    assert (tmp_path / "runtime" / "accounts" / "231054").exists()
    assert (tmp_path / "runtime" / "accounts" / "231443").exists()

    # spawn helper direct
    again = spawn_account_context(base, account_id="999", bridge_dir=a)
    assert again.config.account.account_id == "999"
    assert again.execution.bridge_dir == a
