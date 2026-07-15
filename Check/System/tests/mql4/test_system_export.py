from __future__ import annotations
import csv
from io import StringIO
import pytest
from engine.protocol.constants import MARKET_CSV_COLUMNS, SENSOR_CSV_COLUMNS, TIMEFRAME_M1
from engine.validator.market_validator import validate_market_csv
from engine.validator.sensor_validator import validate_sensor_csv
from tests.mql4 import export_reference, mql_source

@pytest.fixture
def export_source() -> str:
    return mql_source.load_mqh('SYSTEM_Export.mqh')

def test_system_export_public_functions_are_defined(export_source: str) -> None:
    expected = {'SYSTEM_GetTimeframeM1', 'SYSTEM_MarketCsvHeader', 'SYSTEM_SensorCsvHeader', 'SYSTEM_BuildMarketFilePath', 'SYSTEM_BuildSensorFilePath', 'SYSTEM_ToUtcTime', 'SYSTEM_FormatTimeUtc', 'SYSTEM_FormatCsvNumber', 'SYSTEM_CalculateSpread', 'SYSTEM_CalculateSpreadPoints', 'SYSTEM_BuildMarketCsvRow', 'SYSTEM_BuildSensorCsvRow', 'SYSTEM_FileExists', 'SYSTEM_ReadTextFile', 'SYSTEM_CsvContainsTimeUtc', 'SYSTEM_AppendCsvRow', 'SYSTEM_IsNewM1Bar', 'SYSTEM_ExportMarketBar', 'SYSTEM_ExportSensorReading', 'SYSTEM_ExportMarketAndSensor', 'SYSTEM_ExportPerformsAnalysis'}
    assert expected.issubset(set(mql_source.public_function_names(export_source)))

def test_system_get_timeframe_m1_returns_m1_constant(export_source: str) -> None:
    assert mql_source.parse_define(export_source, 'SYSTEM_TIMEFRAME_M1') == TIMEFRAME_M1
    body = mql_source.function_body(export_source, 'SYSTEM_GetTimeframeM1')
    assert 'SYSTEM_TIMEFRAME_M1' in body

def test_system_market_csv_header_matches_protocol_columns(export_source: str) -> None:
    body = mql_source.function_body(export_source, 'SYSTEM_MarketCsvHeader')
    assert export_reference.market_csv_header() in body.replace(' ', '')

def test_system_sensor_csv_header_matches_protocol_columns(export_source: str) -> None:
    body = mql_source.function_body(export_source, 'SYSTEM_SensorCsvHeader')
    assert export_reference.sensor_csv_header() in body.replace(' ', '')

def test_system_build_market_file_path_uses_account_and_instance_template() -> None:
    path = export_reference.build_market_file_path('C:\\Check\\System', '12345', 'EURUSD', 100001)
    assert path == 'C:\\Check\\System\\data\\clients\\12345\\market_EURUSD_100001.csv'

def test_system_build_market_file_path_function_uses_template(export_source: str) -> None:
    body = mql_source.function_body(export_source, 'SYSTEM_BuildMarketFilePath')
    assert 'SYSTEM_MARKET_FILENAME_TEMPLATE' in body
    assert 'SYSTEM_BuildAccountDir' in body

def test_system_build_sensor_file_path_uses_account_and_instance_template() -> None:
    path = export_reference.build_sensor_file_path('C:\\Check\\System', '12345', 'EURUSD', 100001)
    assert path == 'C:\\Check\\System\\data\\clients\\12345\\sensor_EURUSD_100001.csv'

def test_system_build_sensor_file_path_function_uses_template(export_source: str) -> None:
    body = mql_source.function_body(export_source, 'SYSTEM_BuildSensorFilePath')
    assert 'SYSTEM_SENSOR_FILENAME_TEMPLATE' in body
    assert 'SYSTEM_BuildAccountDir' in body

def test_system_to_utc_time_adjusts_server_offset(export_source: str) -> None:
    body = mql_source.function_body(export_source, 'SYSTEM_ToUtcTime')
    assert 'TimeGMT' in body
    assert 'TimeCurrent' in body

def test_system_format_time_utc_uses_iso8601_pattern(export_source: str) -> None:
    body = mql_source.function_body(export_source, 'SYSTEM_FormatTimeUtc')
    assert 'SYSTEM_ToUtcTime' in body
    assert '.000Z' in body

def test_system_format_csv_number_formats_with_digits() -> None:
    assert export_reference.format_csv_number(1.0855, 5) == '1.08550'

def test_system_format_csv_number_function_uses_double_to_string(export_source: str) -> None:
    body = mql_source.function_body(export_source, 'SYSTEM_FormatCsvNumber')
    assert 'DoubleToString' in body

def test_system_calculate_spread_returns_ask_minus_bid() -> None:
    assert export_reference.calculate_spread(1.085, 1.0852) == pytest.approx(0.0002)

def test_system_calculate_spread_function_subtracts_bid_from_ask(export_source: str) -> None:
    body = mql_source.function_body(export_source, 'SYSTEM_CalculateSpread')
    assert 'ask' in body
    assert 'bid' in body

def test_system_calculate_spread_points_divides_by_point() -> None:
    assert export_reference.calculate_spread_points(0.0002, 1e-05) == pytest.approx(20.0)

def test_system_calculate_spread_points_function_divides_spread_by_point(export_source: str) -> None:
    body = mql_source.function_body(export_source, 'SYSTEM_CalculateSpreadPoints')
    assert 'spread' in body
    assert 'point' in body

def test_system_build_market_csv_row_exports_m1_candle_with_required_columns() -> None:
    row = export_reference.build_market_csv_row(time_utc='2026-07-07T06:00:00.000Z', open_price=1.085, high_price=1.086, low_price=1.084, close_price=1.0855, volume=120.0, symbol='EURUSD', digits=5, point=1e-05)
    csv_text = f'{export_reference.market_csv_header()}\n{row}\n'
    result = validate_market_csv(csv_text)
    assert result.is_valid
    assert result.row_count == 1
    parsed = next(csv.DictReader(StringIO(csv_text)))
    assert parsed['timeframe'] == TIMEFRAME_M1
    assert parsed['digits'] == '5'
    assert parsed['point'] == '0.00001'

def test_system_build_market_csv_row_function_uses_digits_and_point(export_source: str) -> None:
    body = mql_source.function_body(export_source, 'SYSTEM_BuildMarketCsvRow')
    assert 'SYSTEM_GetTimeframeM1' in body
    assert 'digits' in body
    assert 'point' in body

def test_system_build_sensor_csv_row_contains_bid_ask_and_spread() -> None:
    row = export_reference.build_sensor_csv_row(time_utc='2026-07-07T06:00:00.000Z', bid=1.085, ask=1.0852, symbol='EURUSD', digits=5, point=1e-05)
    csv_text = f'{export_reference.sensor_csv_header()}\n{row}\n'
    result = validate_sensor_csv(csv_text)
    assert result.is_valid
    assert result.row_count == 1
    parsed = next(csv.DictReader(StringIO(csv_text)))
    assert parsed['bid'] == '1.08500'
    assert parsed['ask'] == '1.08520'
    assert parsed['spread'] == '0.00020'
    assert parsed['spread_points'] == '20'

def test_system_build_sensor_csv_row_function_uses_bid_ask_and_spread_helpers(export_source: str) -> None:
    body = mql_source.function_body(export_source, 'SYSTEM_BuildSensorCsvRow')
    assert 'SYSTEM_CalculateSpread' in body
    assert 'SYSTEM_CalculateSpreadPoints' in body

def test_system_file_exists_uses_get_file_attributes(export_source: str) -> None:
    body = mql_source.function_body(export_source, 'SYSTEM_FileExists')
    assert 'GetFileAttributesW' in body

def test_system_read_text_file_uses_winapi_read(export_source: str) -> None:
    body = mql_source.function_body(export_source, 'SYSTEM_ReadTextFileDll')
    assert 'CreateFileW' in body
    assert 'ReadFile' in body
    assert 'CloseHandle' in body
    wrapper = mql_source.function_body(export_source, 'SYSTEM_ReadTextFile')
    assert 'SYSTEM_ReadTextFileDll' in wrapper
    assert 'SYSTEM_ReadTextFileCommon' in wrapper

def test_system_csv_contains_time_utc_detects_existing_timestamp() -> None:
    csv_text = 'time_utc,open\n2026-07-07T06:00:00.000Z,1.1\n'
    assert export_reference.csv_contains_time_utc(csv_text, '2026-07-07T06:00:00.000Z')
    assert not export_reference.csv_contains_time_utc(csv_text, '2026-07-07T06:01:00.000Z')

def test_system_csv_contains_time_utc_function_uses_string_find(export_source: str) -> None:
    body = mql_source.function_body(export_source, 'SYSTEM_CsvContainsTimeUtc')
    assert 'StringFind' in body

def test_system_append_csv_row_adds_header_and_row_for_new_file() -> None:
    row = export_reference.build_market_csv_row(time_utc='2026-07-07T06:00:00.000Z', open_price=1.085, high_price=1.086, low_price=1.084, close_price=1.0855, volume=120.0, symbol='EURUSD', digits=5, point=1e-05)
    output = export_reference.append_csv_row('', export_reference.market_csv_header(), row)
    assert output.startswith(export_reference.market_csv_header())
    assert row in output

def test_system_append_csv_row_skips_duplicate_time_utc() -> None:
    row = export_reference.build_market_csv_row(time_utc='2026-07-07T06:00:00.000Z', open_price=1.085, high_price=1.086, low_price=1.084, close_price=1.0855, volume=120.0, symbol='EURUSD', digits=5, point=1e-05)
    existing = f'{export_reference.market_csv_header()}\n{row}\n'
    assert export_reference.append_csv_row(existing, export_reference.market_csv_header(), row) == existing

def test_system_append_csv_row_function_checks_duplicate_time(export_source: str) -> None:
    body = mql_source.function_body(export_source, 'SYSTEM_AppendCsvRow')
    assert 'SYSTEM_CsvContainsTimeUtc' in body

def test_system_is_new_m1_bar_compares_current_bar_time(export_source: str) -> None:
    body = mql_source.function_body(export_source, 'SYSTEM_IsNewM1Bar')
    assert 'iTime' in body
    assert 'PERIOD_M1' in body

def test_system_export_market_bar_reads_mt4_m1_bar_and_writes_atomically(export_source: str) -> None:
    body = mql_source.function_body(export_source, 'SYSTEM_ExportMarketBar')
    assert 'iOpen' in body
    assert 'iHigh' in body
    assert 'iLow' in body
    assert 'iClose' in body
    assert 'iVolume' in body
    assert 'MODE_DIGITS' in body
    assert 'MODE_POINT' in body
    assert 'SYSTEM_AtomicWriteText' in body

def test_system_export_sensor_reading_uses_bid_and_ask_from_mt4(export_source: str) -> None:
    body = mql_source.function_body(export_source, 'SYSTEM_ExportSensorReading')
    assert 'MODE_BID' in body
    assert 'MODE_ASK' in body
    assert 'SYSTEM_AtomicWriteText' in body

def test_system_export_market_and_sensor_exports_closed_bar_and_sensor(export_source: str) -> None:
    body = mql_source.function_body(export_source, 'SYSTEM_ExportMarketAndSensor')
    assert 'SYSTEM_ExportMarketBar' in body
    assert 'SYSTEM_ExportSensorReading' in body
    assert 'magic, 1' in body

def test_system_export_performs_analysis_returns_false(export_source: str) -> None:
    body = mql_source.function_body(export_source, 'SYSTEM_ExportPerformsAnalysis')
    assert 'false' in body.lower()

def test_m1_market_row_matches_fixture_schema() -> None:
    fixture_row = '2026-07-07T06:00:00.000Z,1.08500,1.08600,1.08400,1.08550,120,EURUSD,M1,5,0.00001'
    built_row = export_reference.build_market_csv_row(time_utc='2026-07-07T06:00:00.000Z', open_price=1.085, high_price=1.086, low_price=1.084, close_price=1.0855, volume=120.0, symbol='EURUSD', digits=5, point=1e-05)
    assert built_row == fixture_row
    assert export_reference.market_csv_header() == ','.join(MARKET_CSV_COLUMNS)

def test_sensor_row_uses_spread_and_spread_points_from_bid_ask() -> None:
    built_row = export_reference.build_sensor_csv_row(time_utc='2026-07-07T06:00:00.000Z', bid=1.085, ask=1.0852, symbol='EURUSD', digits=5, point=1e-05)
    expected = '2026-07-07T06:00:00.000Z,1.08500,1.08520,0.00020,20,EURUSD,5,0.00001'
    assert built_row == expected
    csv_text = f'{export_reference.sensor_csv_header()}\n{built_row}\n'
    assert validate_sensor_csv(csv_text).is_valid
    assert export_reference.sensor_csv_header() == ','.join(SENSOR_CSV_COLUMNS)
