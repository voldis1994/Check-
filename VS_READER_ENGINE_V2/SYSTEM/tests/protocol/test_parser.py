from __future__ import annotations

import pytest

from engine.protocol.constants import PROTOCOL_SCHEMA_VERSION
from engine.protocol.errors import ProtocolError
from engine.protocol.parser import (
    parse_ack,
    parse_control,
    parse_json,
    parse_market_csv,
    parse_sensor_csv,
    parse_status,
    parse_universe,
)


MARKET_CSV_VALID = """time_utc,open,high,low,close,volume,symbol,timeframe,digits,point
2026-07-07T06:00:00.000Z,1.08500,1.08600,1.08400,1.08550,120,EURUSD,M1,5,0.00001
2026-07-07T06:01:00.000Z,1.08550,1.08650,1.08500,1.08600,98,EURUSD,M1,5,0.00001
"""

SENSOR_CSV_VALID = """time_utc,bid,ask,spread,spread_points,symbol,digits,point
2026-07-07T06:00:00.000Z,1.08500,1.08520,0.00020,2,EURUSD,5,0.00001
"""

STATUS_JSON_VALID = """{
  "schema_version": "1.0.0",
  "timestamp_utc": "2026-07-07T06:00:00.000Z",
  "account_id": "12345",
  "connected": true,
  "trade_allowed": true,
  "balance": 10000.0,
  "equity": 10000.0,
  "margin_free": 9000.0,
  "ea_version": "1.0.0"
}"""

UNIVERSE_JSON_VALID = """{
  "schema_version": "1.0.0",
  "timestamp_utc": "2026-07-07T06:00:00.000Z",
  "session": "london",
  "market_regime": "trending",
  "news_window_active": false
}"""

CONTROL_JSON_VALID = """{
  "schema_version": "1.0.0",
  "timestamp_utc": "2026-07-07T06:00:00.000Z",
  "command_id": "cmd-1",
  "account_id": "12345",
  "symbol": "EURUSD",
  "magic": 100001,
  "action": "OPEN",
  "side": "BUY",
  "volume": 0.1,
  "stop_loss": 1.08000,
  "take_profit": 1.09000,
  "reason": "BUY selected",
  "decision_id": "dec-1"
}"""

ACK_JSON_VALID = """{
  "schema_version": "1.0.0",
  "timestamp_utc": "2026-07-07T06:00:00.000Z",
  "command_id": "cmd-1",
  "account_id": "12345",
  "symbol": "EURUSD",
  "magic": 100001,
  "status": "SUCCESS",
  "ticket": 555
}"""


def test_parse_market_csv() -> None:
    bars = parse_market_csv(MARKET_CSV_VALID)
    assert len(bars) == 2
    assert bars[0].symbol == "EURUSD"
    assert bars[0].timeframe == "M1"
    assert bars[0].close == 1.08550
    assert bars[1].open == 1.08550


def test_parse_sensor_csv() -> None:
    readings = parse_sensor_csv(SENSOR_CSV_VALID)
    assert len(readings) == 1
    assert readings[0].symbol == "EURUSD"
    assert readings[0].spread_points == 2.0
    assert readings[0].ask >= readings[0].bid


def test_parse_status_json() -> None:
    record = parse_status(STATUS_JSON_VALID)
    assert record.schema_version == PROTOCOL_SCHEMA_VERSION
    assert record.account_id == "12345"
    assert record.connected is True
    assert record.trade_allowed is True


def test_parse_status_from_dict() -> None:
    record = parse_status(parse_json(STATUS_JSON_VALID))
    assert record.ea_version == "1.0.0"


def test_parse_universe_json() -> None:
    record = parse_universe(UNIVERSE_JSON_VALID)
    assert record.market_regime == "trending"
    assert record.news_window_active is False


def test_parse_control_json() -> None:
    command = parse_control(CONTROL_JSON_VALID)
    assert command.action == "OPEN"
    assert command.side == "BUY"
    assert command.instance_key.magic == 100001


def test_parse_ack_json() -> None:
    record = parse_ack(ACK_JSON_VALID)
    assert record.status == "SUCCESS"
    assert record.ticket == 555
    assert record.command_id == "cmd-1"


def test_broken_json_raises_protocol_error() -> None:
    with pytest.raises(ProtocolError, match="invalid JSON"):
        parse_json("{not-json")


def test_empty_json_raises_protocol_error() -> None:
    with pytest.raises(ProtocolError, match="empty"):
        parse_json("   ")


def test_broken_market_csv_raises_protocol_error() -> None:
    broken = "time_utc,open,high,low,close,volume,symbol,timeframe,digits\n"
    with pytest.raises(ProtocolError, match="column header mismatch"):
        parse_market_csv(broken)


def test_market_csv_invalid_timeframe_raises_protocol_error() -> None:
    broken = """time_utc,open,high,low,close,volume,symbol,timeframe,digits,point
2026-07-07T06:00:00.000Z,1.08500,1.08600,1.08400,1.08550,120,EURUSD,H1,5,0.00001
"""
    with pytest.raises(ProtocolError):
        parse_market_csv(broken)


def test_broken_sensor_csv_raises_protocol_error() -> None:
    with pytest.raises(ProtocolError, match="empty"):
        parse_sensor_csv("")


def test_unsupported_schema_version_status() -> None:
    payload = parse_json(STATUS_JSON_VALID)
    payload["schema_version"] = "9.9.9"
    with pytest.raises(ProtocolError, match="unsupported schema_version"):
        parse_status(payload)


def test_unsupported_schema_version_control() -> None:
    payload = parse_json(CONTROL_JSON_VALID)
    payload["schema_version"] = "0.0.1"
    with pytest.raises(ProtocolError, match="unsupported schema_version"):
        parse_control(payload)


def test_unsupported_schema_version_ack() -> None:
    payload = parse_json(ACK_JSON_VALID)
    payload["schema_version"] = "bad"
    with pytest.raises(ProtocolError, match="unsupported schema_version"):
        parse_ack(payload)


def test_unsupported_schema_version_universe() -> None:
    payload = parse_json(UNIVERSE_JSON_VALID)
    payload["schema_version"] = "2.0.0"
    with pytest.raises(ProtocolError, match="unsupported schema_version"):
        parse_universe(payload)


def test_universe_forbidden_field_raises_protocol_error() -> None:
    payload = parse_json(UNIVERSE_JSON_VALID)
    payload["signal"] = "buy"
    with pytest.raises(ProtocolError, match="forbidden field"):
        parse_universe(payload)


def test_missing_required_field_raises_protocol_error() -> None:
    payload = parse_json(STATUS_JSON_VALID)
    del payload["account_id"]
    with pytest.raises(ProtocolError, match="missing required field"):
        parse_status(payload)


def test_protocol_error_is_not_silent() -> None:
    try:
        parse_ack("{")
    except ProtocolError as exc:
        assert exc.module == "protocol.parser"
        assert exc.message
        assert exc.error_type.value == "PROTOCOL"
    else:
        raise AssertionError("ProtocolError expected")
