from __future__ import annotations

import pytest

from engine.core.instance import Instance, ensure_unique_instance_keys
from engine.protocol.errors import ValidationError


def test_instance_key_identity() -> None:
    instance = Instance(account_id="12345", symbol="EURUSD", magic=100001)
    assert instance.instance_key == ("12345", "EURUSD", 100001)


def test_instance_matches_true_for_same_triplet() -> None:
    instance = Instance(account_id="12345", symbol="EURUSD", magic=100001)
    assert instance.matches("12345", "EURUSD", 100001)


def test_instance_matches_false_for_different_triplet() -> None:
    instance = Instance(account_id="12345", symbol="EURUSD", magic=100001)
    assert not instance.matches("12345", "GBPUSD", 100001)


def test_instance_is_hashable_and_comparable_by_key() -> None:
    first = Instance(account_id="12345", symbol="EURUSD", magic=100001)
    same = Instance(account_id="12345", symbol="EURUSD", magic=100001)
    different = Instance(account_id="12345", symbol="EURUSD", magic=100002)
    assert first == same
    assert first != different
    assert len({first, same, different}) == 2


def test_instance_rejects_empty_account_id() -> None:
    with pytest.raises(ValidationError, match="account_id"):
        Instance(account_id=" ", symbol="EURUSD", magic=1)


def test_instance_rejects_empty_symbol() -> None:
    with pytest.raises(ValidationError, match="symbol"):
        Instance(account_id="12345", symbol="", magic=1)


def test_instance_rejects_negative_magic() -> None:
    with pytest.raises(ValidationError, match="magic"):
        Instance(account_id="12345", symbol="EURUSD", magic=-1)


def test_instance_rejects_boolean_magic() -> None:
    with pytest.raises(ValidationError, match="magic"):
        Instance(account_id="12345", symbol="EURUSD", magic=True)  # type: ignore[arg-type]


def test_instance_generates_market_filename() -> None:
    instance = Instance(account_id="12345", symbol="EURUSD", magic=100001)
    assert instance.market_filename() == "market_EURUSD_100001.csv"


def test_instance_generates_sensor_filename() -> None:
    instance = Instance(account_id="12345", symbol="EURUSD", magic=100001)
    assert instance.sensor_filename() == "sensor_EURUSD_100001.csv"


def test_instance_generates_control_filename() -> None:
    instance = Instance(account_id="12345", symbol="EURUSD", magic=100001)
    assert instance.control_filename() == "control_EURUSD_100001.json"


def test_instance_generates_ack_filename() -> None:
    instance = Instance(account_id="12345", symbol="EURUSD", magic=100001)
    assert instance.ack_filename() == "ack_EURUSD_100001.json"


def test_instance_generates_decision_journal_filename() -> None:
    instance = Instance(account_id="12345", symbol="EURUSD", magic=100001)
    assert instance.decision_journal_filename() == "decision_EURUSD_100001.jsonl"


def test_instance_generates_trade_journal_filename() -> None:
    instance = Instance(account_id="12345", symbol="EURUSD", magic=100001)
    assert instance.trade_journal_filename() == "trade_EURUSD_100001.jsonl"


def test_instance_generates_error_journal_filename() -> None:
    instance = Instance(account_id="12345", symbol="EURUSD", magic=100001)
    assert instance.error_journal_filename() == "error_EURUSD_100001.jsonl"


def test_instance_generates_instance_state_filename() -> None:
    instance = Instance(account_id="12345", symbol="EURUSD", magic=100001)
    assert instance.instance_state_filename() == "instance_EURUSD_100001.json"


def test_instance_generates_spread_state_filename() -> None:
    instance = Instance(account_id="12345", symbol="EURUSD", magic=100001)
    assert instance.spread_state_filename() == "spread_EURUSD_100001.json"


def test_instance_generates_status_filename() -> None:
    instance = Instance(account_id="12345", symbol="EURUSD", magic=100001)
    assert instance.status_filename() == "status_12345.json"


def test_ensure_unique_instance_keys_accepts_unique_instances() -> None:
    ensure_unique_instance_keys(
        [
            Instance(account_id="12345", symbol="EURUSD", magic=100001),
            Instance(account_id="12345", symbol="GBPUSD", magic=100001),
            Instance(account_id="88888", symbol="EURUSD", magic=100001),
        ]
    )


def test_ensure_unique_instance_keys_detects_duplicates() -> None:
    with pytest.raises(ValidationError, match="duplicate instance keys detected"):
        ensure_unique_instance_keys(
            [
                Instance(account_id="12345", symbol="EURUSD", magic=100001),
                Instance(account_id="12345", symbol="EURUSD", magic=100001),
            ]
        )
