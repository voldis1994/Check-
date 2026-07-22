from __future__ import annotations
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal
from engine.core.atomic_io import atomic_write_text
from engine.core.instance import Instance
from engine.core.paths import SystemPaths
from engine.execution.ack_reader import build_ack_path
from engine.execution.control_writer import build_control_path
from engine.protocol.constants import AckStatus, OrderAction, PROTOCOL_SCHEMA_VERSION
from engine.protocol.models import AckRecord, ControlCommand
from engine.protocol.parser import parse_control
MarketScenario = Literal['bullish', 'bearish', 'flat']
StatusScenario = Literal['tradeable', 'not_tradeable']
MODULE_NAME = 'e2e.simulator.mt4_simulator'

@dataclass(frozen=True)
class ExportTickResult:
    instance: Instance
    market_path: Path
    sensor_path: Path
    status_path: Path
    universe_path: Path

def build_market_csv(*, symbol: str, scenario: MarketScenario='bullish', timestamp_utc: str='2026-07-07T06:02:00.000Z', close_override: float | None=None) -> str:
    if scenario == 'bullish':
        rows = [('2026-07-07T06:00:00.000Z', 1.1, 1.102, 1.099, 1.1015, 120), ('2026-07-07T06:01:00.000Z', 1.1015, 1.103, 1.1005, 1.1022, 110), ('2026-07-07T06:02:00.000Z', 1.1022, 1.104, 1.101, 1.1031, 105)]
    elif scenario == 'flat':
        rows = [('2026-07-07T06:00:00.000Z', 1.1, 1.101, 1.099, 1.1, 100), ('2026-07-07T06:01:00.000Z', 1.1, 1.101, 1.099, 1.1, 100), ('2026-07-07T06:02:00.000Z', 1.1, 1.101, 1.099, 1.1, 100)]
    else:
        rows = [('2026-07-07T06:00:00.000Z', 1.104, 1.1045, 1.102, 1.1025, 120), ('2026-07-07T06:01:00.000Z', 1.1025, 1.103, 1.101, 1.1012, 110), ('2026-07-07T06:02:00.000Z', 1.1012, 1.1018, 1.099, 1.0995, 105)]
    lines = ['time_utc,open,high,low,close,volume,symbol,timeframe,digits,point']
    for time_value, open_, high, low, close, volume in rows:
        if close_override is not None and time_value == rows[-1][0]:
            resolved_close = close_override
            resolved_high = max(high, open_, resolved_close, low)
            resolved_low = min(low, open_, resolved_close)
        else:
            resolved_close = close
            resolved_high = high
            resolved_low = low
        lines.append(f'{time_value},{open_:.5f},{resolved_high:.5f},{resolved_low:.5f},{resolved_close:.5f},{volume},{symbol},M1,5,0.00001')
    if timestamp_utc != rows[-1][0]:
        lines[-1] = lines[-1].replace(rows[-1][0], timestamp_utc, 1)
    return '\n'.join(lines) + '\n'

def build_sensor_csv(*, symbol: str, scenario: MarketScenario='bullish', timestamp_utc: str='2026-07-07T06:02:00.000Z', close_override: float | None=None) -> str:
    if scenario == 'bullish':
        readings = [('2026-07-07T06:00:00.000Z', 1.1014, 1.10155, 0.00015, 15), ('2026-07-07T06:01:00.000Z', 1.1021, 1.1023, 0.0002, 20), ('2026-07-07T06:02:00.000Z', 1.1029, 1.10315, 0.00025, 25)]
    elif scenario == 'flat':
        readings = [('2026-07-07T06:00:00.000Z', 1.0999, 1.1001, 0.0002, 20), ('2026-07-07T06:01:00.000Z', 1.0999, 1.1001, 0.0002, 20), ('2026-07-07T06:02:00.000Z', 1.0999, 1.1001, 0.0002, 20)]
    else:
        readings = [('2026-07-07T06:00:00.000Z', 1.1024, 1.10255, 0.00015, 15), ('2026-07-07T06:01:00.000Z', 1.1011, 1.1013, 0.0002, 20), ('2026-07-07T06:02:00.000Z', 1.0994, 1.09965, 0.00025, 25)]
    lines = ['time_utc,bid,ask,spread,spread_points,symbol,digits,point']
    for time_value, bid, ask, spread, spread_points in readings:
        if close_override is not None and time_value == readings[-1][0]:
            half = spread / 2.0
            bid = close_override - half
            ask = close_override + half
        lines.append(f'{time_value},{bid:.5f},{ask:.5f},{spread:.5f},{spread_points},{symbol},5,0.00001')
    if timestamp_utc != readings[-1][0]:
        lines[-1] = lines[-1].replace(readings[-1][0], timestamp_utc, 1)
    return '\n'.join(lines) + '\n'

def build_status_json(*, account_id: str, scenario: StatusScenario='tradeable', timestamp_utc: str='2026-07-07T06:02:00.000Z', open_positions: tuple[dict[str, object], ...]=()) -> str:
    trade_allowed = scenario == 'tradeable'
    payload: dict[str, object] = {'schema_version': PROTOCOL_SCHEMA_VERSION, 'timestamp_utc': timestamp_utc, 'account_id': account_id, 'connected': trade_allowed, 'trade_allowed': trade_allowed, 'balance': 10000.0, 'equity': 10020.5, 'margin_free': 9800.0, 'ea_version': '1.0.0'}
    if open_positions:
        payload['open_positions'] = list(open_positions)
    return json.dumps(payload)

def build_universe_json(*, timestamp_utc: str='2026-07-07T06:02:00.000Z') -> str:
    payload = {'schema_version': PROTOCOL_SCHEMA_VERSION, 'timestamp_utc': timestamp_utc, 'session': 'LONDON', 'market_regime': 'trending', 'news_window_active': False, 'news_impact_level': 'low', 'metadata': {'source': 'calendar'}}
    return json.dumps(payload)

@dataclass
class MT4Simulator:
    paths: SystemPaths
    ticket_seed: int = 10000
    _ticket_counter: int = field(init=False)
    _open_positions: dict[tuple[str, str, int], dict[str, object]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self._ticket_counter = self.ticket_seed

    def _all_position_payload(self) -> tuple[dict[str, object], ...]:
        return tuple(self._open_positions.values())

    def _position_payload(self, instance: Instance) -> tuple[dict[str, object], ...]:
        return self._all_position_payload()

    def _sync_position_from_ack(self, control: ControlCommand, ack_record: AckRecord) -> None:
        key = control.instance_key.as_tuple()
        if ack_record.status != AckStatus.SUCCESS.value:
            return
        if control.action == OrderAction.OPEN.value:
            if ack_record.ticket is None or control.side is None or control.volume is None:
                return
            position: dict[str, object] = {'symbol': control.symbol, 'magic': control.magic, 'ticket': ack_record.ticket, 'side': control.side, 'volume': control.volume, 'stop_loss': control.stop_loss, 'take_profit': control.take_profit}
            if ack_record.fill_price is not None:
                position['entry_price'] = ack_record.fill_price
            self._open_positions[key] = position
        elif control.action == OrderAction.MODIFY.value:
            position = self._open_positions.get(key)
            if position is None:
                return
            if control.stop_loss is not None:
                position['stop_loss'] = control.stop_loss
            if control.take_profit is not None:
                position['take_profit'] = control.take_profit
        elif control.action == OrderAction.CLOSE.value:
            self._open_positions.pop(key, None)

    def refresh_status(self, instance: Instance, *, timestamp_utc: str) -> Path:
        status_path = self.paths.account_dir(instance.account_id) / instance.status_filename()
        atomic_write_text(status_path, build_status_json(account_id=instance.account_id, timestamp_utc=timestamp_utc, open_positions=self._position_payload(instance)))
        return status_path

    def next_ticket(self) -> int:
        self._ticket_counter += 1
        return self._ticket_counter

    def export_tick(self, instance: Instance, *, market_scenario: MarketScenario='bullish', status_scenario: StatusScenario='tradeable', timestamp_utc: str='2026-07-07T06:02:00.000Z', close_override: float | None=None) -> ExportTickResult:
        self.paths.ensure_account_directories(instance.account_id)
        account_dir = self.paths.account_dir(instance.account_id)
        market_path = account_dir / instance.market_filename()
        sensor_path = account_dir / instance.sensor_filename()
        status_path = account_dir / instance.status_filename()
        universe_path = account_dir / 'universe.json'
        atomic_write_text(market_path, build_market_csv(symbol=instance.symbol, scenario=market_scenario, timestamp_utc=timestamp_utc, close_override=close_override))
        atomic_write_text(sensor_path, build_sensor_csv(symbol=instance.symbol, scenario=market_scenario, timestamp_utc=timestamp_utc, close_override=close_override))
        atomic_write_text(status_path, build_status_json(account_id=instance.account_id, scenario=status_scenario, timestamp_utc=timestamp_utc, open_positions=self._position_payload(instance)))
        atomic_write_text(universe_path, build_universe_json(timestamp_utc=timestamp_utc))
        return ExportTickResult(instance=instance, market_path=market_path, sensor_path=sensor_path, status_path=status_path, universe_path=universe_path)

    def read_control(self, instance: Instance) -> ControlCommand | None:
        control_path = build_control_path(self.paths, instance)
        if not control_path.exists():
            return None
        return parse_control(control_path.read_text(encoding='utf-8'))

    def build_ack_for_control(self, control: ControlCommand, *, status: str=AckStatus.SUCCESS.value, ticket: int | None=None, fill_price: float | None=None, error_code: int | None=None, error_message: str | None=None, timestamp_utc: str='2026-07-07T06:03:00.000Z') -> AckRecord:
        resolved_ticket = ticket
        if status == AckStatus.SUCCESS.value and resolved_ticket is None:
            resolved_ticket = self.next_ticket()
        kwargs: dict[str, object] = {
            'schema_version': PROTOCOL_SCHEMA_VERSION,
            'timestamp_utc': timestamp_utc,
            'command_id': control.command_id,
            'account_id': control.account_id,
            'symbol': control.symbol,
            'magic': control.magic,
            'status': status,
            'ticket': resolved_ticket,
            'error_code': error_code,
            'error_message': error_message,
        }
        if status == AckStatus.SUCCESS.value and control.action == OrderAction.OPEN.value:
            if control.side is not None:
                kwargs['side'] = control.side
            if control.volume is not None:
                kwargs['volume'] = control.volume
            if fill_price is not None:
                kwargs['fill_price'] = fill_price
            elif control.side == 'BUY':
                kwargs['fill_price'] = 1.10315
            else:
                kwargs['fill_price'] = 1.10290
        return AckRecord(**kwargs)

    def write_ack(self, instance: Instance, ack_record: AckRecord) -> Path:
        if ack_record.instance_key.as_tuple() != instance.instance_key:
            raise ValueError('ack record instance does not match target instance')
        self.paths.ensure_account_directories(instance.account_id)
        ack_path = build_ack_path(self.paths, instance)
        from engine.protocol.writer import write_ack
        atomic_write_text(ack_path, write_ack(ack_record))
        return ack_path

    def fulfill_control(self, instance: Instance, *, status: str=AckStatus.SUCCESS.value, ticket: int | None=None, fill_price: float | None=None, error_code: int | None=None, error_message: str | None=None, timestamp_utc: str='2026-07-07T06:03:00.000Z') -> AckRecord | None:
        control = self.read_control(instance)
        if control is None:
            return None
        ack_record = self.build_ack_for_control(control, status=status, ticket=ticket, fill_price=fill_price, error_code=error_code, error_message=error_message, timestamp_utc=timestamp_utc)
        self.write_ack(instance, ack_record)
        self._sync_position_from_ack(control, ack_record)
        self.refresh_status(instance, timestamp_utc=timestamp_utc)
        return ack_record

    def install_auto_ack_hook(self, monkeypatch) -> None:
        simulator = self
        import engine.core.cycle as cycle_module
        import engine.execution.engine as execution_engine
        original_run = execution_engine.run_execution_engine
        original_wait = execution_engine.wait_for_ack

        def patched_run_execution_engine(**kwargs: object):
            instance = kwargs['instance']

            def sim_wait(*, ack_available, **wait_kwargs: object):
                simulator.fulfill_control(instance, ticket=simulator.next_ticket())
                return original_wait(ack_available=ack_available, **wait_kwargs)
            execution_engine.wait_for_ack = sim_wait
            try:
                return original_run(**kwargs)
            finally:
                execution_engine.wait_for_ack = original_wait
        monkeypatch.setattr(execution_engine, 'run_execution_engine', patched_run_execution_engine)
        monkeypatch.setattr(cycle_module, 'run_execution_engine', patched_run_execution_engine)
