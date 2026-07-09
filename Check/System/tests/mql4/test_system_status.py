from __future__ import annotations
import json
import pytest
from engine.protocol.constants import PROTOCOL_SCHEMA_VERSION
from engine.protocol.writer import STATUS_REQUIRED_FIELDS
from engine.validator.status_validator import validate_status_json
from tests.mql4 import mql_source, status_reference, universe_reference

@pytest.fixture
def status_source() -> str:
    return mql_source.load_mqh('SYSTEM_Status.mqh')

def test_system_status_public_functions_are_defined(status_source: str) -> None:
    expected = {'SYSTEM_GetProtocolSchemaVersion', 'SYSTEM_GetEaVersion', 'SYSTEM_FormatJsonBoolean', 'SYSTEM_FormatJsonNumber', 'SYSTEM_EscapeJsonString', 'SYSTEM_BuildStatusFilePath', 'SYSTEM_BuildStatusJson', 'SYSTEM_BuildStatusJsonFromAccount', 'SYSTEM_ExportStatus', 'SYSTEM_ExportStatusWithLastError', 'SYSTEM_StatusPerformsAnalysis'}
    assert expected.issubset(set(mql_source.public_function_names(status_source)))

def test_system_get_protocol_schema_version_matches_protocol(status_source: str) -> None:
    assert mql_source.parse_define(status_source, 'SYSTEM_PROTOCOL_SCHEMA_VERSION') == PROTOCOL_SCHEMA_VERSION
    body = mql_source.function_body(status_source, 'SYSTEM_GetProtocolSchemaVersion')
    assert 'SYSTEM_PROTOCOL_SCHEMA_VERSION' in body

def test_system_get_ea_version_returns_non_empty_value(status_source: str) -> None:
    version = mql_source.parse_define(status_source, 'SYSTEM_EA_VERSION')
    assert version
    body = mql_source.function_body(status_source, 'SYSTEM_GetEaVersion')
    assert 'SYSTEM_EA_VERSION' in body

def test_system_format_json_boolean_returns_lowercase_literals() -> None:
    assert status_reference.format_json_boolean(True) == 'true'
    assert status_reference.format_json_boolean(False) == 'false'

def test_system_format_json_boolean_function_returns_true_false_strings(status_source: str) -> None:
    body = mql_source.function_body(status_source, 'SYSTEM_FormatJsonBoolean')
    assert '"true"' in body
    assert '"false"' in body

def test_system_format_json_number_formats_numeric_values() -> None:
    assert status_reference.format_json_number(10020.5, 2) == '10020.50'

def test_system_format_json_number_function_uses_double_to_string(status_source: str) -> None:
    body = mql_source.function_body(status_source, 'SYSTEM_FormatJsonNumber')
    assert 'DoubleToString' in body

def test_system_escape_json_string_escapes_quotes_and_backslashes() -> None:
    assert status_reference.escape_json_string('path\\error "disk"') == 'path\\\\error \\"disk\\"'

def test_system_escape_json_string_function_replaces_special_characters(status_source: str) -> None:
    body = mql_source.function_body(status_source, 'SYSTEM_EscapeJsonString')
    assert 'StringReplace' in body

def test_system_build_status_file_path_uses_account_template() -> None:
    path = status_reference.build_status_file_path('C:\\Check\\System', '12345')
    assert path == 'C:\\Check\\System\\data\\clients\\12345\\status_12345.json'

def test_system_build_status_file_path_function_uses_status_template(status_source: str) -> None:
    body = mql_source.function_body(status_source, 'SYSTEM_BuildStatusFilePath')
    assert 'SYSTEM_STATUS_FILENAME_TEMPLATE' in body
    assert 'SYSTEM_BuildAccountDir' in body

def test_system_status_exports_all_account_open_positions(status_source: str) -> None:
    body = mql_source.function_body(status_source, 'SYSTEM_BuildOpenPositionsJson')
    assert 'OrdersTotal' in body
    assert 'OrderSymbol()' in body
    assert 'OrderMagicNumber()' in body
    assert 'open_positions' in body

def test_system_status_exports_open_positions_field(status_source: str) -> None:
    body = mql_source.function_body(status_source, 'SYSTEM_FindOpenPositionForInstance')
    assert 'OrderSelect' in body
    build_body = mql_source.function_body(status_source, 'SYSTEM_BuildOpenPositionsJson')
    assert 'open_positions' in build_body

def test_system_export_status_accepts_symbol_and_magic(status_source: str) -> None:
    body = mql_source.function_body(status_source, 'SYSTEM_ExportStatus')
    assert 'symbol' in body
    assert 'magic' in body

def test_system_build_status_json_contains_required_status_fields() -> None:
    payload_text = status_reference.build_status_json(account_id='12345', connected=True, trade_allowed=True, balance=10000.0, equity=10020.5, margin_free=9800.0, timestamp_utc='2026-07-07T06:00:00.000Z', symbol='EURUSD', magic=100001)
    payload = json.loads(payload_text)
    for field in STATUS_REQUIRED_FIELDS:
        assert field in payload
    assert payload['balance'] == 10000.0
    assert payload['equity'] == 10020.5
    assert payload['connected'] is True
    assert payload['trade_allowed'] is True
    assert validate_status_json(payload_text).is_valid

def test_system_build_status_json_function_includes_balance_equity_connected_trade_allowed(status_source: str) -> None:
    body = mql_source.function_body(status_source, 'SYSTEM_BuildStatusJson')
    assert 'balance' in body
    assert 'equity' in body
    assert 'connected' in body
    assert 'trade_allowed' in body
    assert 'schema_version' in body

def test_system_build_status_json_from_account_reads_mt4_account_state(status_source: str) -> None:
    body = mql_source.function_body(status_source, 'SYSTEM_BuildStatusJsonFromAccount')
    assert 'IsConnected' in body
    assert 'IsTradeAllowed' in body
    assert 'AccountBalance' in body
    assert 'AccountEquity' in body
    assert 'AccountFreeMargin' in body

def test_system_export_status_uses_atomic_write(status_source: str) -> None:
    body = mql_source.function_body(status_source, 'SYSTEM_ExportStatus')
    assert 'SYSTEM_AtomicWriteText' in body
    assert 'SYSTEM_BuildStatusJsonFromAccount' in body

def test_system_export_status_with_last_error_supports_optional_error_field(status_source: str) -> None:
    body = mql_source.function_body(status_source, 'SYSTEM_ExportStatusWithLastError')
    assert 'last_error' in body
    assert 'SYSTEM_AtomicWriteText' in body

def test_system_status_performs_analysis_returns_false(status_source: str) -> None:
    body = mql_source.function_body(status_source, 'SYSTEM_StatusPerformsAnalysis')
    assert 'false' in body.lower()

def test_status_json_schema_version_is_present() -> None:
    payload_text = status_reference.build_status_json(account_id='12345', connected=True, trade_allowed=True, balance=10000.0, equity=10020.5, margin_free=9800.0, timestamp_utc='2026-07-07T06:00:00.000Z')
    payload = json.loads(payload_text)
    assert payload['schema_version'] == PROTOCOL_SCHEMA_VERSION
