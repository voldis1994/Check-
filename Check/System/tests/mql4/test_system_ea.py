from __future__ import annotations
import pytest
from tests.mql4 import mql_source

@pytest.fixture
def ea_source() -> str:
    return mql_source.load_mq4('SYSTEM_EA.mq4')

@pytest.fixture
def export_source() -> str:
    return mql_source.load_mqh('SYSTEM_Export.mqh')

@pytest.fixture
def execution_source() -> str:
    return mql_source.load_mqh('SYSTEM_Execution.mqh')

def test_system_ea_configures_root_path_when_input_set(ea_source: str) -> None:
    assert 'SystemRootPath' in ea_source
    assert 'SYSTEM_ConfigureRootPath' in ea_source

def test_system_ea_includes_execution_module(ea_source: str) -> None:
    assert '#include <SYSTEM_Execution.mqh>' in ea_source
    assert '#include <SYSTEM_Status.mqh>' in ea_source
    assert '#include <SYSTEM_Universe.mqh>' in ea_source

def test_system_headers_use_angle_bracket_includes() -> None:
    """MQL4 quote-includes resolve vs Experts\\; SYSTEM headers must use Include\\ via <>."""
    for path in sorted(mql_source.MQL4_INCLUDE_DIR.glob('SYSTEM_*.mqh')):
        text = path.read_text(encoding='utf-8')
        assert '#include "SYSTEM_' not in text, f'{path.name} must use #include <SYSTEM_*.mqh>'

def test_system_ea_requires_m1_timeframe_on_init(ea_source: str) -> None:
    assert 'Period()' in ea_source
    assert 'PERIOD_M1' in ea_source
    assert 'INIT_FAILED' in ea_source

def test_system_ea_initializes_paths_on_init(ea_source: str) -> None:
    assert 'SYSTEM_InitPaths()' in ea_source

def test_system_ea_exports_market_and_universe_on_new_m1_bar(ea_source: str) -> None:
    assert 'SYSTEM_IsNewM1Bar' in ea_source
    assert 'SYSTEM_ExportMarketBar' in ea_source
    assert 'SYSTEM_ExportUniverse' in ea_source
    assert 'g_last_exported_bar_time' in ea_source

def test_system_ea_throttles_sensor_and_status_export(ea_source: str) -> None:
    assert 'SYSTEM_ExportSensorReading' in ea_source
    assert 'SYSTEM_ExportStatus' in ea_source
    assert 'SYSTEM_ExportClosedTrade' in ea_source
    assert 'g_sensor_status_export_interval_ms' in ea_source
    assert 'GetTickCount' in ea_source

def test_system_ea_loads_processed_command_id_on_init(ea_source: str) -> None:
    assert 'SYSTEM_LoadProcessedCommandId' in ea_source
    assert 'g_last_processed_command_id' in ea_source

def test_system_ea_uses_account_symbol_and_magic_for_export(ea_source: str) -> None:
    assert 'AccountNumber()' in ea_source
    assert 'Symbol()' in ea_source
    assert 'MagicNumber' in ea_source

def test_system_ea_processes_pending_control_on_tick(ea_source: str) -> None:
    assert 'SYSTEM_TryExecutePendingControl' in ea_source
    assert 'g_last_processed_command_id' in ea_source

def test_system_ea_does_not_perform_analysis(ea_source: str, export_source: str, execution_source: str) -> None:
    combined = f'{ea_source}\n{export_source}\n{execution_source}'
    assert 'engine.analysis' not in combined
    assert 'run_analysis_engine' not in combined
    assert 'iCustom' not in combined
    assert 'iMA' not in combined
    assert 'iRSI' not in combined
    body = mql_source.function_body(export_source, 'SYSTEM_ExportPerformsAnalysis')
    assert 'false' in body.lower()
    execution_body = mql_source.function_body(execution_source, 'SYSTEM_ExecutionPerformsAnalysis')
    assert 'false' in execution_body.lower()

def test_system_ea_delegates_order_execution_to_execution_module(ea_source: str, execution_source: str) -> None:
    assert 'OrderSend' not in ea_source
    assert 'OrderModify' not in ea_source
    assert 'OrderClose' not in ea_source
    assert 'OrderSend' in execution_source

def test_system_ea_export_module_writes_with_atomic_io(export_source: str) -> None:
    market_body = mql_source.function_body(export_source, 'SYSTEM_ExportMarketBar')
    sensor_body = mql_source.function_body(export_source, 'SYSTEM_ExportSensorReading')
    assert 'SYSTEM_AtomicWriteText' in market_body
    assert 'SYSTEM_AtomicWriteText' in sensor_body
