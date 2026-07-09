from __future__ import annotations

import json

import pytest

from engine.core.instance import Instance
from engine.core.paths import SystemPaths
from engine.execution.command import OrderCommand
from engine.execution.control_writer import publish_control
from engine.protocol.constants import OrderAction, PROTOCOL_SCHEMA_VERSION, Side
from engine.protocol.parser import parse_control
from engine.protocol.writer import CONTROL_REQUIRED_FIELDS
from tests.mql4 import control_reference, mql_source
from tests.protocol.test_parser import CONTROL_JSON_VALID


@pytest.fixture
def control_source() -> str:
    return mql_source.load_mqh("SYSTEM_Control.mqh")


CONTROL_JSON_NONE = """{
  "schema_version": "1.0.0",
  "timestamp_utc": "2026-07-07T06:00:00.000Z",
  "command_id": "cmd-none-1",
  "account_id": "12345",
  "symbol": "EURUSD",
  "magic": 100001,
  "action": "NONE",
  "reason": "WAIT: equal scores",
  "decision_id": "decision-wait"
}"""


def test_system_control_public_functions_are_defined(control_source: str) -> None:
    expected = {
        "SYSTEM_ResetControlCommand",
        "SYSTEM_BuildControlFilePath",
        "SYSTEM_IsControlTmpPresent",
        "SYSTEM_IsControlReady",
        "SYSTEM_ExtractJsonStringField",
        "SYSTEM_ExtractJsonToken",
        "SYSTEM_ExtractJsonIntField",
        "SYSTEM_ExtractJsonDoubleField",
        "SYSTEM_IsSupportedOrderAction",
        "SYSTEM_ControlRequiresOrderExecution",
        "SYSTEM_ParseControlCommand",
        "SYSTEM_ValidateControlInstance",
        "SYSTEM_ReadControlCommand",
        "SYSTEM_ControlPerformsAnalysis",
    }
    assert expected.issubset(set(mql_source.public_function_names(control_source)))


def test_system_build_control_file_path_uses_instance_template() -> None:
    path = control_reference.build_control_file_path(r"C:\SYSTEM", "12345", "EURUSD", 100001)
    assert path == r"C:\SYSTEM\data\clients\12345\control_EURUSD_100001.json"


def test_system_build_control_file_path_function_uses_template(control_source: str) -> None:
    body = mql_source.function_body(control_source, "SYSTEM_BuildControlFilePath")
    assert "SYSTEM_CONTROL_FILENAME_TEMPLATE" in body
    assert "SYSTEM_BuildAccountDir" in body


def test_system_is_control_tmp_present_detects_tmp_file(control_source: str) -> None:
    body = mql_source.function_body(control_source, "SYSTEM_IsControlTmpPresent")
    assert "SYSTEM_TmpPathFor" in body


def test_system_is_control_ready_requires_final_file_without_tmp() -> None:
    assert control_reference.is_control_ready(
        "path",
        tmp_exists=False,
        file_exists=True,
    )
    assert not control_reference.is_control_ready(
        "path",
        tmp_exists=True,
        file_exists=True,
    )
    assert not control_reference.is_control_ready(
        "path",
        tmp_exists=False,
        file_exists=False,
    )


def test_system_is_control_ready_function_checks_tmp_and_file(control_source: str) -> None:
    body = mql_source.function_body(control_source, "SYSTEM_IsControlReady")
    assert "SYSTEM_IsControlTmpPresent" in body
    assert "SYSTEM_FileExists" in body


def test_system_extract_json_string_field_reads_quoted_values() -> None:
    assert control_reference.extract_json_string_field(CONTROL_JSON_VALID, "symbol") == "EURUSD"
    assert control_reference.extract_json_string_field(CONTROL_JSON_VALID, "action") == "OPEN"


def test_system_extract_json_string_field_function_searches_field_name(control_source: str) -> None:
    body = mql_source.function_body(control_source, "SYSTEM_ExtractJsonStringField")
    assert "StringFind" in body


def test_system_extract_json_token_reads_unquoted_values() -> None:
    assert control_reference.extract_json_token(CONTROL_JSON_VALID, "magic") == "100001"


def test_system_extract_json_int_field_parses_integer() -> None:
    assert control_reference.extract_json_int_field(CONTROL_JSON_VALID, "magic") == 100001


def test_system_extract_json_double_field_parses_numeric_values() -> None:
    assert control_reference.extract_json_double_field(CONTROL_JSON_VALID, "volume") == pytest.approx(0.1)


def test_system_is_supported_order_action_accepts_protocol_actions() -> None:
    for action in ("OPEN", "MODIFY", "CLOSE", "NONE"):
        assert control_reference.is_supported_order_action(action)
    assert not control_reference.is_supported_order_action("BUY")


def test_system_is_supported_order_action_function_checks_all_actions(control_source: str) -> None:
    body = mql_source.function_body(control_source, "SYSTEM_IsSupportedOrderAction")
    assert "SYSTEM_ACTION_OPEN" in body
    assert "SYSTEM_ACTION_NONE" in body


def test_system_control_requires_order_execution_is_false_for_none() -> None:
    assert not control_reference.control_requires_order_execution(OrderAction.NONE.value)
    assert control_reference.control_requires_order_execution(OrderAction.OPEN.value)
    assert control_reference.control_requires_order_execution(OrderAction.MODIFY.value)
    assert control_reference.control_requires_order_execution(OrderAction.CLOSE.value)


def test_system_control_requires_order_execution_function_excludes_none(control_source: str) -> None:
    body = mql_source.function_body(control_source, "SYSTEM_ControlRequiresOrderExecution")
    assert "SYSTEM_ACTION_NONE" not in body or "SYSTEM_ACTION_OPEN" in body
    assert "SYSTEM_ACTION_OPEN" in body
    assert "SYSTEM_ACTION_MODIFY" in body
    assert "SYSTEM_ACTION_CLOSE" in body


def test_valid_control_is_parsed_and_matches_protocol_parser() -> None:
    command, error = control_reference.parse_control_command(CONTROL_JSON_VALID)
    assert error == ""
    assert command is not None
    protocol_command = parse_control(CONTROL_JSON_VALID)
    assert command.command_id == protocol_command.command_id
    assert command.symbol == protocol_command.symbol
    assert command.magic == protocol_command.magic
    assert command.action == protocol_command.action
    assert command.side == protocol_command.side
    assert command.volume == pytest.approx(protocol_command.volume)


def test_system_parse_control_command_function_validates_required_fields(control_source: str) -> None:
    body = mql_source.function_body(control_source, "SYSTEM_ParseControlCommand")
    for field in CONTROL_REQUIRED_FIELDS:
        assert field in body


def test_wrong_magic_is_rejected() -> None:
    command, error = control_reference.read_control_command(
        CONTROL_JSON_VALID,
        account_id="12345",
        symbol="EURUSD",
        magic=999999,
    )
    assert command is None
    assert "magic" in error


def test_wrong_symbol_is_rejected() -> None:
    command, error = control_reference.read_control_command(
        CONTROL_JSON_VALID,
        account_id="12345",
        symbol="GBPUSD",
        magic=100001,
    )
    assert command is None
    assert "symbol" in error


def test_system_validate_control_instance_function_checks_symbol_and_magic(control_source: str) -> None:
    body = mql_source.function_body(control_source, "SYSTEM_ValidateControlInstance")
    assert "symbol" in body
    assert "magic" in body
    assert "account_id" in body


def test_none_action_is_parsed_without_order_execution() -> None:
    command, error = control_reference.read_control_command(
        CONTROL_JSON_NONE,
        account_id="12345",
        symbol="EURUSD",
        magic=100001,
    )
    assert error == ""
    assert command is not None
    assert command.action == OrderAction.NONE.value
    assert not control_reference.control_requires_order_execution(command.action)


def test_system_read_control_command_reads_validates_and_parses(control_source: str) -> None:
    body = mql_source.function_body(control_source, "SYSTEM_ReadControlCommand")
    assert "SYSTEM_IsControlReady" in body
    assert "SYSTEM_ReadTextFile" in body
    assert "SYSTEM_ParseControlCommand" in body
    assert "SYSTEM_ValidateControlInstance" in body


def test_system_read_control_command_rejects_tmp_file() -> None:
    command, error = control_reference.read_control_command(
        CONTROL_JSON_VALID,
        account_id="12345",
        symbol="EURUSD",
        magic=100001,
        tmp_exists=True,
    )
    assert command is None
    assert error == "control file is not ready"


def test_valid_control_read_from_published_python_control_file(tmp_path) -> None:
    paths = SystemPaths(root_path=tmp_path)
    instance = Instance(account_id="12345", symbol="EURUSD", magic=100001)
    publish_control(
        paths,
        instance,
        OrderCommand(
            command_id="cmd-open-1",
            action=OrderAction.OPEN.value,
            reason="BUY selected",
            decision_id="dec-1",
            side=Side.BUY.value,
            volume=0.1,
            stop_loss=1.08,
            take_profit=1.09,
        ),
        timestamp_utc="2026-07-07T06:00:00.000Z",
    )
    raw_text = (paths.account_dir("12345") / instance.control_filename()).read_text(encoding="utf-8")
    command, error = control_reference.read_control_command(
        raw_text,
        account_id="12345",
        symbol="EURUSD",
        magic=100001,
    )
    assert error == ""
    assert command is not None
    assert command.action == OrderAction.OPEN.value
    assert parse_control(raw_text).command_id == "cmd-open-1"


def test_system_control_performs_analysis_returns_false(control_source: str) -> None:
    body = mql_source.function_body(control_source, "SYSTEM_ControlPerformsAnalysis")
    assert "false" in body.lower()


def test_parsed_control_contains_schema_version() -> None:
    command, _ = control_reference.parse_control_command(CONTROL_JSON_VALID)
    assert command is not None
    assert command.schema_version == PROTOCOL_SCHEMA_VERSION
    payload = json.loads(CONTROL_JSON_VALID)
    assert payload["schema_version"] == PROTOCOL_SCHEMA_VERSION
