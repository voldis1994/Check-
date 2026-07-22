from __future__ import annotations
import json
import pytest
from engine.core.instance import Instance
from engine.core.paths import SystemPaths
from engine.execution.command import OrderCommand
from engine.execution.control_writer import publish_control
from engine.protocol.constants import AckStatus, OrderAction, PROTOCOL_SCHEMA_VERSION, Side
from engine.protocol.parser import parse_ack, parse_control
from engine.protocol.writer import ACK_REQUIRED_FIELDS
from tests.mql4 import control_reference, execution_reference, mql_source
from tests.protocol.test_parser import ACK_JSON_VALID, CONTROL_JSON_VALID

@pytest.fixture
def execution_source() -> str:
    return mql_source.load_mqh('SYSTEM_Execution.mqh')
CONTROL_JSON_OPEN_SELL = '{\n  "schema_version": "1.0.0",\n  "timestamp_utc": "2026-07-07T06:00:00.000Z",\n  "command_id": "cmd-open-sell",\n  "account_id": "12345",\n  "symbol": "EURUSD",\n  "magic": 100001,\n  "action": "OPEN",\n  "side": "SELL",\n  "volume": 0.2,\n  "stop_loss": 1.09000,\n  "take_profit": 1.07000,\n  "reason": "SELL selected",\n  "decision_id": "dec-sell"\n}'
CONTROL_JSON_MODIFY = '{\n  "schema_version": "1.0.0",\n  "timestamp_utc": "2026-07-07T06:00:00.000Z",\n  "command_id": "cmd-modify-1",\n  "account_id": "12345",\n  "symbol": "EURUSD",\n  "magic": 100001,\n  "action": "MODIFY",\n  "ticket": 555,\n  "stop_loss": 1.08100,\n  "take_profit": 1.09200,\n  "reason": "adjust levels",\n  "decision_id": "dec-modify"\n}'
CONTROL_JSON_CLOSE = '{\n  "schema_version": "1.0.0",\n  "timestamp_utc": "2026-07-07T06:00:00.000Z",\n  "command_id": "cmd-close-1",\n  "account_id": "12345",\n  "symbol": "EURUSD",\n  "magic": 100001,\n  "action": "CLOSE",\n  "ticket": 555,\n  "reason": "close position",\n  "decision_id": "dec-close"\n}'

def test_system_execution_public_functions_are_defined(execution_source: str) -> None:
    expected = {'SYSTEM_ResetAckResult', 'SYSTEM_BuildAckFilePath', 'SYSTEM_IsSupportedAckStatus', 'SYSTEM_BuildAckJson', 'SYSTEM_WriteAck', 'SYSTEM_SelectOrderByTicket', 'SYSTEM_IsSupportedTradeSide', 'SYSTEM_TradeCommandForSide', 'SYSTEM_SetRejectedAck', 'SYSTEM_SetFailedAck', 'SYSTEM_SetSuccessAck', 'SYSTEM_ExecuteOpen', 'SYSTEM_ExecuteModify', 'SYSTEM_ExecuteClose', 'SYSTEM_ExecuteControlCommand', 'SYSTEM_TryExecutePendingControl', 'SYSTEM_ExecutionPerformsAnalysis', 'SYSTEM_ProcessedCommandGvName', 'SYSTEM_IsCommandProcessed', 'SYSTEM_MarkCommandProcessed', 'SYSTEM_LoadProcessedCommandId', 'SYSTEM_SetSuccessAckWithFill', 'SYSTEM_SetSuccessAckWithModifyLevels', 'SYSTEM_SlImprovesProtection'}
    assert expected.issubset(set(mql_source.public_function_names(execution_source)))

def test_system_build_ack_file_path_uses_instance_template() -> None:
    path = execution_reference.build_ack_file_path('C:\\Check\\System', '12345', 'EURUSD', 100001)
    assert path == 'C:\\Check\\System\\data\\clients\\12345\\ack_EURUSD_100001.json'

def test_system_build_ack_file_path_function_uses_template(execution_source: str) -> None:
    body = mql_source.function_body(execution_source, 'SYSTEM_BuildAckFilePath')
    assert 'SYSTEM_ACK_FILENAME_TEMPLATE' in body
    assert 'SYSTEM_BuildAccountDir' in body

def test_system_is_supported_ack_status_accepts_protocol_statuses() -> None:
    for status in (AckStatus.SUCCESS.value, AckStatus.FAILED.value, AckStatus.REJECTED.value):
        assert execution_reference.is_supported_ack_status(status)
    assert not execution_reference.is_supported_ack_status('TIMEOUT')

def test_system_is_supported_ack_status_function_checks_all_statuses(execution_source: str) -> None:
    body = mql_source.function_body(execution_source, 'SYSTEM_IsSupportedAckStatus')
    assert 'SYSTEM_ACK_STATUS_SUCCESS' in body
    assert 'SYSTEM_ACK_STATUS_FAILED' in body
    assert 'SYSTEM_ACK_STATUS_REJECTED' in body

def test_system_build_ack_json_matches_protocol_parser() -> None:
    json_text = execution_reference.build_ack_json(command_id='cmd-1', account_id='12345', symbol='EURUSD', magic=100001, status=AckStatus.SUCCESS.value, timestamp_utc='2026-07-07T06:00:00.000Z', ticket=555)
    record = parse_ack(json_text)
    assert record.command_id == 'cmd-1'
    assert record.status == AckStatus.SUCCESS.value
    assert record.ticket == 555

def test_system_build_ack_json_function_includes_required_fields(execution_source: str) -> None:
    body = mql_source.function_body(execution_source, 'SYSTEM_BuildAckJson')
    for field in ACK_REQUIRED_FIELDS:
        assert field in body
    assert 'fill_price' in body
    assert 'open_time_utc' in body
    assert 'volume' in body
    assert 'side' in body
    assert 'requested_stop_loss' in body
    assert 'applied_stop_loss' in body
    assert 'requested_take_profit' in body
    assert 'applied_take_profit' in body
    assert 'broker_error_code' in body
    assert 'action' in body


def test_system_execute_modify_function_rereads_applied_levels(execution_source: str) -> None:
    body = mql_source.function_body(execution_source, 'SYSTEM_ExecuteModify')
    assert 'OrderModify' in body
    assert 'OrderStopLoss' in body
    assert 'OrderTakeProfit' in body
    assert 'SYSTEM_SetSuccessAckWithModifyLevels' in body
    assert 'SYSTEM_SlImprovesProtection' in body


def test_modify_success_ack_includes_applied_stop_loss() -> None:
    command, _ = control_reference.parse_control_command(CONTROL_JSON_MODIFY)
    assert command is not None
    context = execution_reference.OrderExecutionContext(
        symbol='EURUSD',
        magic=100001,
        known_tickets={555},
        previous_stop_loss=1.08000,
        applied_stop_loss=1.08100,
        applied_take_profit=1.09200,
        order_type=0,
    )
    result = execution_reference.execute_modify(command, context)
    assert result.status == AckStatus.SUCCESS.value
    assert result.ticket == 555
    assert result.applied_stop_loss == pytest.approx(1.08100)
    assert result.requested_stop_loss == pytest.approx(1.08100)
    assert result.action == OrderAction.MODIFY.value
    json_text = execution_reference.build_ack_json(
        command_id=command.command_id,
        account_id='12345',
        symbol='EURUSD',
        magic=100001,
        status=result.status,
        timestamp_utc='2026-07-07T06:00:00.000Z',
        ticket=result.ticket,
        action=result.action,
        requested_stop_loss=result.requested_stop_loss,
        applied_stop_loss=result.applied_stop_loss,
        requested_take_profit=result.requested_take_profit,
        applied_take_profit=result.applied_take_profit,
        broker_error_code=0,
    )
    record = parse_ack(json_text)
    assert record.applied_stop_loss == pytest.approx(1.08100)
    assert record.requested_stop_loss == pytest.approx(1.08100)
    assert record.action == OrderAction.MODIFY.value

def test_system_build_ack_json_includes_error_fields_for_failed_status() -> None:
    json_text = execution_reference.build_ack_json(command_id='cmd-fail', account_id='12345', symbol='EURUSD', magic=100001, status=AckStatus.FAILED.value, timestamp_utc='2026-07-07T06:00:00.000Z', error_code=130, error_message='OrderSend failed')
    record = parse_ack(json_text)
    assert record.status == AckStatus.FAILED.value
    assert record.error_code == 130
    assert record.error_message == 'OrderSend failed'

def test_system_write_ack_function_uses_atomic_write(execution_source: str) -> None:
    body = mql_source.function_body(execution_source, 'SYSTEM_WriteAck')
    assert 'SYSTEM_AtomicWriteText' in body
    assert 'SYSTEM_BuildAckJson' in body

def test_open_buy_executes_with_magic_context() -> None:
    command, _ = control_reference.parse_control_command(CONTROL_JSON_VALID)
    assert command is not None
    context = execution_reference.OrderExecutionContext(symbol='EURUSD', magic=100001)
    result = execution_reference.execute_open(command, context)
    assert result.status == AckStatus.SUCCESS.value
    assert result.ticket == 555
    assert result.has_ticket

def test_system_execute_open_function_uses_order_send_with_magic(execution_source: str) -> None:
    body = mql_source.function_body(execution_source, 'SYSTEM_ExecuteOpen')
    assert 'OrderSend' in body
    assert 'command.magic' in body
    assert 'SYSTEM_IsSupportedTradeSide' in body
    assert 'SYSTEM_TradeCommandForSide' in body
    assert 'SYSTEM_ResolveOpenOrderComment' in body
    assert 'OrderOpenPrice' in body
    assert 'SYSTEM_SetSuccessAckWithFill' in body
    assert 'command.reason' not in body or 'order_comment' in body


def test_system_build_open_order_comment_helpers_exist(execution_source: str) -> None:
    names = set(mql_source.public_function_names(execution_source))
    assert 'SYSTEM_BuildOpenOrderComment' in names
    assert 'SYSTEM_ResolveOpenOrderComment' in names
    assert 'SYSTEM_UIntToHex8' in names
    body = mql_source.function_body(execution_source, 'SYSTEM_BuildOpenOrderComment')
    assert '31' in body

def test_open_sell_executes_with_magic_context() -> None:
    command, _ = control_reference.parse_control_command(CONTROL_JSON_OPEN_SELL)
    assert command is not None
    context = execution_reference.OrderExecutionContext(symbol='EURUSD', magic=100001)
    result = execution_reference.execute_open(command, context)
    assert result.status == AckStatus.SUCCESS.value
    assert result.ticket == 556

def test_open_missing_side_is_rejected() -> None:
    payload = json.loads(CONTROL_JSON_VALID)
    del payload['side']
    command, _ = control_reference.parse_control_command(json.dumps(payload))
    assert command is not None
    result = execution_reference.execute_open(command, execution_reference.OrderExecutionContext(symbol='EURUSD', magic=100001))
    assert result.status == AckStatus.REJECTED.value

def test_open_order_send_failure_returns_failed_ack() -> None:
    command, _ = control_reference.parse_control_command(CONTROL_JSON_VALID)
    assert command is not None
    context = execution_reference.OrderExecutionContext(symbol='EURUSD', magic=100001, order_send_result=-1, order_send_error=130)
    result = execution_reference.execute_open(command, context)
    assert result.status == AckStatus.FAILED.value
    assert result.error_code == 130

def test_modify_sl_tp_executes_for_known_ticket() -> None:
    command, _ = control_reference.parse_control_command(CONTROL_JSON_MODIFY)
    assert command is not None
    context = execution_reference.OrderExecutionContext(symbol='EURUSD', magic=100001, known_tickets={555})
    result = execution_reference.execute_modify(command, context)
    assert result.status == AckStatus.SUCCESS.value
    assert result.ticket == 555

def test_system_execute_modify_function_uses_order_modify(execution_source: str) -> None:
    body = mql_source.function_body(execution_source, 'SYSTEM_ExecuteModify')
    assert 'OrderModify' in body
    assert 'stop_loss' in body
    assert 'take_profit' in body

def test_modify_unknown_ticket_is_rejected() -> None:
    command, _ = control_reference.parse_control_command(CONTROL_JSON_MODIFY)
    assert command is not None
    result = execution_reference.execute_modify(command, execution_reference.OrderExecutionContext(symbol='EURUSD', magic=100001, known_tickets=set()))
    assert result.status == AckStatus.REJECTED.value

def test_modify_failure_returns_failed_ack() -> None:
    command, _ = control_reference.parse_control_command(CONTROL_JSON_MODIFY)
    assert command is not None
    context = execution_reference.OrderExecutionContext(symbol='EURUSD', magic=100001, known_tickets={555}, order_modify_result=False, order_modify_error=1)
    result = execution_reference.execute_modify(command, context)
    assert result.status == AckStatus.FAILED.value

def test_close_position_executes_for_known_ticket() -> None:
    command, _ = control_reference.parse_control_command(CONTROL_JSON_CLOSE)
    assert command is not None
    context = execution_reference.OrderExecutionContext(symbol='EURUSD', magic=100001, known_tickets={555})
    result = execution_reference.execute_close(command, context)
    assert result.status == AckStatus.SUCCESS.value
    assert result.ticket == 555

def test_system_execute_close_function_uses_order_close(execution_source: str) -> None:
    body = mql_source.function_body(execution_source, 'SYSTEM_ExecuteClose')
    assert 'OrderClose' in body
    assert 'command.has_volume' in body
    assert 'command.volume' in body

def test_close_unknown_ticket_is_rejected() -> None:
    command, _ = control_reference.parse_control_command(CONTROL_JSON_CLOSE)
    assert command is not None
    result = execution_reference.execute_close(command, execution_reference.OrderExecutionContext(symbol='EURUSD', magic=100001, known_tickets=set()))
    assert result.status == AckStatus.REJECTED.value

def test_close_failure_returns_failed_ack() -> None:
    command, _ = control_reference.parse_control_command(CONTROL_JSON_CLOSE)
    assert command is not None
    context = execution_reference.OrderExecutionContext(symbol='EURUSD', magic=100001, known_tickets={555}, order_close_result=False, order_close_error=146)
    result = execution_reference.execute_close(command, context)
    assert result.status == AckStatus.FAILED.value
    assert result.error_code == 146

def test_ack_contains_command_id_from_control() -> None:
    command_id, result, error = execution_reference.try_execute_pending_control(CONTROL_JSON_VALID, account_id='12345', symbol='EURUSD', magic=100001, last_processed_command_id='', context=execution_reference.OrderExecutionContext(symbol='EURUSD', magic=100001), write_ack=lambda _command_id, _result: True)
    assert error == ''
    assert command_id == 'cmd-1'
    assert result is not None
    assert result.status == AckStatus.SUCCESS.value
    ack_json = execution_reference.build_ack_json(command_id=command_id, account_id='12345', symbol='EURUSD', magic=100001, status=result.status, timestamp_utc='2026-07-07T06:00:00.000Z', ticket=result.ticket)
    assert parse_ack(ack_json).command_id == parse_control(CONTROL_JSON_VALID).command_id

def test_system_try_execute_pending_control_skips_processed_command_id(execution_source: str) -> None:
    body = mql_source.function_body(execution_source, 'SYSTEM_TryExecutePendingControl')
    assert 'last_processed_command_id' in body
    assert 'SYSTEM_ReadControlCommand' in body
    assert 'SYSTEM_WriteAck' in body
    assert 'SYSTEM_IsCommandProcessed' in body
    assert 'SYSTEM_MarkCommandProcessed' in body
    mark_pos = body.find('SYSTEM_MarkCommandProcessed')
    write_positions = [idx for idx in range(len(body)) if body.startswith('SYSTEM_WriteAck', idx)]
    assert mark_pos >= 0
    assert any(write_pos > mark_pos for write_pos in write_positions)

def test_try_execute_pending_control_does_not_repeat_same_command_id() -> None:
    command_id, result, error = execution_reference.try_execute_pending_control(CONTROL_JSON_VALID, account_id='12345', symbol='EURUSD', magic=100001, last_processed_command_id='cmd-1', context=execution_reference.OrderExecutionContext(symbol='EURUSD', magic=100001))
    assert command_id is None
    assert result is None
    assert error == ''

def test_none_action_returns_success_without_ticket() -> None:
    none_json = CONTROL_JSON_VALID.replace('"OPEN"', '"NONE"').replace('"cmd-1"', '"cmd-none-2"')
    command, _ = control_reference.parse_control_command(none_json)
    assert command is not None
    result = execution_reference.execute_control_command(command, execution_reference.OrderExecutionContext(symbol='EURUSD', magic=100001))
    assert result.status == AckStatus.SUCCESS.value
    assert not result.has_ticket

def test_system_execute_control_command_dispatches_by_action(execution_source: str) -> None:
    body = mql_source.function_body(execution_source, 'SYSTEM_ExecuteControlCommand')
    assert 'SYSTEM_ACTION_OPEN' in body
    assert 'SYSTEM_ACTION_MODIFY' in body
    assert 'SYSTEM_ACTION_CLOSE' in body
    assert 'SYSTEM_ACTION_NONE' in body

def test_execution_does_not_decide_direction_only_executes_control(execution_source: str) -> None:
    combined = execution_source
    assert 'iCustom' not in combined
    assert 'iMA' not in combined
    assert 'iRSI' not in combined
    assert 'run_analysis_engine' not in combined
    body = mql_source.function_body(execution_source, 'SYSTEM_ExecutionPerformsAnalysis')
    assert 'false' in body.lower()

def test_valid_ack_fixture_matches_protocol_parser() -> None:
    record = parse_ack(ACK_JSON_VALID)
    assert record.status == AckStatus.SUCCESS.value
    assert record.command_id == 'cmd-1'

def test_try_execute_pending_control_reads_published_python_control(tmp_path) -> None:
    paths = SystemPaths(root_path=tmp_path)
    instance = Instance(account_id='12345', symbol='EURUSD', magic=100001)
    publish_control(paths, instance, OrderCommand(command_id='cmd-open-1', action=OrderAction.OPEN.value, reason='BUY selected', decision_id='dec-1', side=Side.BUY.value, volume=0.1, stop_loss=1.08, take_profit=1.09), timestamp_utc='2026-07-07T06:00:00.000Z')
    raw_text = (paths.account_dir('12345') / instance.control_filename()).read_text(encoding='utf-8')
    written: dict[str, execution_reference.AckResult] = {}

    def capture_ack(command_id: str, result: execution_reference.AckResult) -> bool:
        written[command_id] = result
        return True
    command_id, result, error = execution_reference.try_execute_pending_control(raw_text, account_id='12345', symbol='EURUSD', magic=100001, last_processed_command_id='', context=execution_reference.OrderExecutionContext(symbol='EURUSD', magic=100001), write_ack=capture_ack)
    assert error == ''
    assert command_id == 'cmd-open-1'
    assert result is not None
    assert result.status == AckStatus.SUCCESS.value
    assert written['cmd-open-1'].status == AckStatus.SUCCESS.value

def test_system_select_order_by_ticket_function_checks_symbol_and_magic(execution_source: str) -> None:
    body = mql_source.function_body(execution_source, 'SYSTEM_SelectOrderByTicket')
    assert 'OrderSelect' in body
    assert 'OrderSymbol' in body
    assert 'OrderMagicNumber' in body
