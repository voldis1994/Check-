from __future__ import annotations
import csv
import json
import time
from dataclasses import asdict, dataclass
from io import StringIO
from pathlib import Path
from typing import Any
from engine.core.atomic_io import atomic_read_text
from engine.core.clock import now_utc
from engine.core.instance import Instance
from engine.core.lifecycle import discover_instances
from engine.core.paths import SystemPaths
from engine.core.monitoring_store import load_instance_metrics
from engine.execution.ack_reader import build_ack_path, read_ack_record
from engine.execution.control_writer import build_control_path
from engine.journal.decision_journal import build_decision_journal_path
from engine.journal.error_journal import build_error_journal_path
from engine.journal.trade_journal import build_trade_journal_path
from engine.protocol.errors import SystemError
from engine.protocol.models import SystemConfig
from engine.protocol.parser import parse_control, parse_decision_journal_line, parse_error_journal_line, parse_status, parse_trade_journal_line
from engine.state.instance_state import InstanceState
from engine.state.spread_state import SpreadState
MODULE_NAME = 'dashboard.reader'
ACTION_FEED_LIMIT = 24
MARKET_SPARKLINE_BARS = 48

@dataclass(frozen=True)
class RobotActionEvent:
    timestamp_utc: str
    kind: str
    summary: str
    detail: str
    account_id: str = ''
    symbol: str = ''

@dataclass(frozen=True)
class InstanceDashboardView:
    instance: Instance
    last_decision: str | None
    last_reason: str | None
    risk_result: str | None
    risk_reason: str | None
    relative_spread: float | None
    open_ticket: int | None
    position_side: str | None
    position_volume: float | None
    last_ack_status: str | None
    last_ack_command_id: str | None
    last_error_message: str | None
    last_error_type: str | None
    instance_health: str | None = None
    cycle_latency_ms: int | None = None
    ack_latency_ms: int | None = None
    data_freshness_ms: int | None = None
    error_count: int | None = None
    error_rate_per_min: float | None = None
    buy_score: float | None = None
    sell_score: float | None = None
    ai_mode: str | None = None
    ai_reason: str | None = None
    entry_price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    position_bars_open: int | None = None
    cycle_count: int | None = None
    last_trade_event: str | None = None
    last_trade_reason: str | None = None
    last_trade_ack: str | None = None
    control_action: str | None = None
    control_reason: str | None = None
    control_timestamp_utc: str | None = None
    broker_connected: bool | None = None
    trade_allowed: bool | None = None
    balance: float | None = None
    equity: float | None = None
    bid: float | None = None
    ask: float | None = None
    current_spread: float | None = None
    market_age_ms: int | None = None
    sensor_age_ms: int | None = None
    status_age_ms: int | None = None
    sparkline: str = ''
    last_close: float | None = None
    ai_available: bool | None = None
    ai_fallback_used: bool | None = None
    system_decision_before_ai: str | None = None
    decision_after_ai: str | None = None
    exec_stale: bool = False

@dataclass(frozen=True)
class DashboardSnapshot:
    generated_at_utc: str
    instances: tuple[InstanceDashboardView, ...]
    monitoring_lines: tuple[str, ...] = ()
    action_feed: tuple[RobotActionEvent, ...] = ()
    system_name: str = 'SYSTEM'
    root_path: str = ''

    @property
    def instance_count(self) -> int:
        return len(self.instances)

def _file_age_ms(path: Path) -> int | None:
    if not path.exists():
        return None
    return max(0, int((time.time() - path.stat().st_mtime) * 1000))

def read_last_journal_line(path: Path) -> str | None:
    if not path.exists():
        return None
    last_line: str | None = None
    for line in atomic_read_text(path).splitlines():
        stripped = line.strip()
        if stripped:
            last_line = stripped
    return last_line

def read_journal_tail_lines(path: Path, *, max_lines: int) -> tuple[str, ...]:
    if max_lines <= 0 or not path.exists():
        return ()
    lines = [line.strip() for line in atomic_read_text(path).splitlines() if line.strip()]
    return tuple(lines[-max_lines:])

def read_last_decision_entry(paths: SystemPaths, instance: Instance):
    journal_path = build_decision_journal_path(paths, instance)
    last_line = read_last_journal_line(journal_path)
    if last_line is None:
        return None
    try:
        return parse_decision_journal_line(last_line)
    except SystemError:
        return None

def read_last_error_entry(paths: SystemPaths, instance: Instance):
    journal_path = build_error_journal_path(paths, instance)
    last_line = read_last_journal_line(journal_path)
    if last_line is None:
        return None
    try:
        return parse_error_journal_line(last_line)
    except SystemError:
        return None

def read_last_trade_entry(paths: SystemPaths, instance: Instance):
    journal_path = build_trade_journal_path(paths, instance)
    last_line = read_last_journal_line(journal_path)
    if last_line is None:
        return None
    try:
        return parse_trade_journal_line(last_line)
    except SystemError:
        return None

def read_last_ack(paths: SystemPaths, instance: Instance) -> tuple[str | None, str | None]:
    ack_path = build_ack_path(paths, instance)
    if not ack_path.exists():
        return (None, None)
    try:
        ack_record = read_ack_record(paths, instance)
    except SystemError:
        return (None, None)
    return (ack_record.status, ack_record.command_id)

def read_control_snapshot(paths: SystemPaths, instance: Instance) -> tuple[str | None, str | None, str | None]:
    control_path = build_control_path(paths, instance)
    if not control_path.exists():
        return (None, None, None)
    try:
        command = parse_control(atomic_read_text(control_path))
    except SystemError:
        return (None, None, None)
    return (command.action, command.reason, command.timestamp_utc)

def read_status_snapshot(paths: SystemPaths, instance: Instance) -> tuple[bool | None, bool | None, float | None, float | None]:
    status_path = paths.account_dir(instance.account_id) / instance.status_filename()
    if not status_path.exists():
        return (None, None, None, None)
    try:
        status = parse_status(atomic_read_text(status_path))
    except SystemError:
        return (None, None, None, None)
    return (status.connected, status.trade_allowed, status.balance, status.equity)

def read_sensor_snapshot(paths: SystemPaths, instance: Instance) -> tuple[float | None, float | None, float | None]:
    sensor_path = paths.account_dir(instance.account_id) / instance.sensor_filename()
    if not sensor_path.exists():
        return (None, None, None)
    try:
        rows = list(csv.DictReader(StringIO(atomic_read_text(sensor_path))))
    except (OSError, csv.Error, UnicodeError):
        return (None, None, None)
    if not rows:
        return (None, None, None)
    last = rows[-1]
    try:
        bid = float(last.get('bid', ''))
        ask = float(last.get('ask', ''))
        spread = float(last.get('spread', ask - bid))
    except (TypeError, ValueError):
        return (None, None, None)
    return (bid, ask, spread)

def _sparkline_from_closes(closes: list[float]) -> str:
    if not closes:
        return ''
    glyphs = '▁▂▃▄▅▆▇█'
    if len(closes) == 1:
        return glyphs[3]
    low = min(closes)
    high = max(closes)
    span = high - low
    if span <= 0:
        return glyphs[0] * len(closes)
    chars: list[str] = []
    for value in closes:
        index = int((value - low) / span * (len(glyphs) - 1))
        chars.append(glyphs[max(0, min(len(glyphs) - 1, index))])
    return ''.join(chars)

def read_market_sparkline(paths: SystemPaths, instance: Instance, *, max_bars: int=MARKET_SPARKLINE_BARS) -> tuple[str, float | None]:
    market_path = paths.account_dir(instance.account_id) / instance.market_filename()
    if not market_path.exists():
        return ('', None)
    try:
        rows = list(csv.DictReader(StringIO(atomic_read_text(market_path))))
    except (OSError, csv.Error, UnicodeError):
        return ('', None)
    closes: list[float] = []
    for row in rows[-max_bars:]:
        try:
            closes.append(float(row['close']))
        except (KeyError, TypeError, ValueError):
            continue
    if not closes:
        return ('', None)
    return (_sparkline_from_closes(closes), closes[-1])

def _collect_instance_actions(paths: SystemPaths, instance: Instance) -> list[RobotActionEvent]:
    events: list[RobotActionEvent] = []
    for line in read_journal_tail_lines(build_decision_journal_path(paths, instance), max_lines=8):
        try:
            entry = parse_decision_journal_line(line)
        except SystemError:
            continue
        events.append(RobotActionEvent(timestamp_utc=entry.timestamp_utc, kind='DECISION', summary=entry.decision, detail=entry.reason, account_id=instance.account_id, symbol=instance.symbol))
    for line in read_journal_tail_lines(build_trade_journal_path(paths, instance), max_lines=8):
        try:
            entry = parse_trade_journal_line(line)
        except SystemError:
            continue
        volume = '' if entry.volume is None else f' vol={entry.volume}'
        events.append(RobotActionEvent(timestamp_utc=entry.timestamp_utc, kind='TRADE', summary=f'{entry.event}/{entry.ack_status}', detail=f'{entry.reason}{volume}', account_id=instance.account_id, symbol=instance.symbol))
    for line in read_journal_tail_lines(build_error_journal_path(paths, instance), max_lines=4):
        try:
            entry = parse_error_journal_line(line)
        except SystemError:
            continue
        events.append(RobotActionEvent(timestamp_utc=entry.timestamp_utc, kind='ERROR', summary=entry.error_type, detail=entry.message, account_id=instance.account_id, symbol=instance.symbol))
    action, reason, timestamp_utc = read_control_snapshot(paths, instance)
    if action is not None and timestamp_utc is not None:
        events.append(RobotActionEvent(timestamp_utc=timestamp_utc, kind='CONTROL', summary=action, detail=reason or '', account_id=instance.account_id, symbol=instance.symbol))
    ack_status, ack_command_id = read_last_ack(paths, instance)
    if ack_status is not None:
        ack_path = build_ack_path(paths, instance)
        stamp = now_utc()
        if ack_path.exists():
            try:
                payload = json.loads(atomic_read_text(ack_path))
                if isinstance(payload, dict) and isinstance(payload.get('timestamp_utc'), str):
                    stamp = payload['timestamp_utc']
            except (OSError, json.JSONDecodeError, UnicodeError, TypeError):
                pass
        events.append(RobotActionEvent(timestamp_utc=stamp, kind='ACK', summary=ack_status, detail=ack_command_id or '', account_id=instance.account_id, symbol=instance.symbol))
    return events


def is_stale_failed_open(*, open_ticket: int | None, last_trade_event: str | None, last_trade_ack: str | None, last_trade_reason: str | None) -> bool:
    if open_ticket is not None:
        return False
    if last_trade_event != 'OPEN':
        return False
    if last_trade_ack in {'FAILED', 'REJECTED', 'TIMEOUT'}:
        return True
    reason = last_trade_reason or ''
    return 'ACK_TIMEOUT' in reason

def build_action_feed(paths: SystemPaths, instances: tuple[Instance, ...], *, limit: int=ACTION_FEED_LIMIT) -> tuple[RobotActionEvent, ...]:
    events: list[RobotActionEvent] = []
    for instance in instances:
        events.extend(_collect_instance_actions(paths, instance))
    events.sort(key=lambda item: item.timestamp_utc, reverse=True)
    return tuple(events[:limit])

def read_instance_dashboard_view(paths: SystemPaths, instance: Instance) -> InstanceDashboardView:
    instance_state = InstanceState.load(paths, instance)
    spread_state = SpreadState.load(paths, instance)
    decision_entry = read_last_decision_entry(paths, instance)
    error_entry = read_last_error_entry(paths, instance)
    trade_entry = read_last_trade_entry(paths, instance)
    ack_status, ack_command_id = read_last_ack(paths, instance)
    control_action, control_reason, control_timestamp = read_control_snapshot(paths, instance)
    connected, trade_allowed, balance, equity = read_status_snapshot(paths, instance)
    bid, ask, current_spread = read_sensor_snapshot(paths, instance)
    sparkline, last_close = read_market_sparkline(paths, instance)
    account_dir = paths.account_dir(instance.account_id)
    if ack_status is None:
        ack_status = instance_state.last_ack_status or None
    if ack_command_id is None and instance_state.last_command_id:
        ack_command_id = instance_state.last_command_id
    relative_spread = None
    if spread_state.record is not None:
        relative_spread = spread_state.record.relative_spread
        if current_spread is None:
            current_spread = spread_state.record.current_spread
    monitoring = load_instance_metrics(paths, instance)
    last_trade_event = None if trade_entry is None else trade_entry.event
    last_trade_reason = None if trade_entry is None else trade_entry.reason
    last_trade_ack = None if trade_entry is None else trade_entry.ack_status
    stale = is_stale_failed_open(open_ticket=instance_state.open_ticket, last_trade_event=last_trade_event, last_trade_ack=last_trade_ack, last_trade_reason=last_trade_reason)
    return InstanceDashboardView(
        instance=instance,
        last_decision=decision_entry.decision if decision_entry is not None else instance_state.last_decision,
        last_reason=decision_entry.reason if decision_entry is not None else instance_state.last_reason,
        risk_result=decision_entry.risk_result if decision_entry is not None else None,
        risk_reason=decision_entry.risk_reason if decision_entry is not None else None,
        relative_spread=relative_spread,
        open_ticket=instance_state.open_ticket,
        position_side=instance_state.position_side,
        position_volume=instance_state.position_volume,
        last_ack_status=ack_status,
        last_ack_command_id=ack_command_id,
        last_error_message=error_entry.message if error_entry is not None else None,
        last_error_type=error_entry.error_type if error_entry is not None else None,
        instance_health=monitoring.instance_health if monitoring is not None else None,
        cycle_latency_ms=monitoring.cycle_latency_ms if monitoring is not None else None,
        ack_latency_ms=monitoring.ack_latency_ms if monitoring is not None else None,
        data_freshness_ms=monitoring.data_freshness_ms if monitoring is not None else None,
        error_count=monitoring.error_count if monitoring is not None else None,
        error_rate_per_min=monitoring.error_rate_per_min if monitoring is not None else None,
        buy_score=None if decision_entry is None else decision_entry.buy_score,
        sell_score=None if decision_entry is None else decision_entry.sell_score,
        ai_mode=None if decision_entry is None else decision_entry.ai_mode,
        ai_reason=None if decision_entry is None else decision_entry.ai_reason,
        entry_price=instance_state.position_entry_price,
        stop_loss=instance_state.position_stop_loss,
        take_profit=instance_state.position_take_profit,
        position_bars_open=instance_state.position_bars_open if instance_state.open_ticket is not None else None,
        cycle_count=instance_state.cycle_count,
        last_trade_event=last_trade_event,
        last_trade_reason=last_trade_reason,
        last_trade_ack=last_trade_ack,
        control_action=control_action,
        control_reason=control_reason,
        control_timestamp_utc=control_timestamp,
        broker_connected=connected,
        trade_allowed=trade_allowed,
        balance=balance,
        equity=equity,
        bid=bid,
        ask=ask,
        current_spread=current_spread,
        market_age_ms=_file_age_ms(account_dir / instance.market_filename()),
        sensor_age_ms=_file_age_ms(account_dir / instance.sensor_filename()),
        status_age_ms=_file_age_ms(account_dir / instance.status_filename()),
        sparkline=sparkline,
        last_close=last_close,
        ai_available=None if decision_entry is None else decision_entry.ai_available,
        ai_fallback_used=None if decision_entry is None else decision_entry.ai_fallback_used,
        system_decision_before_ai=None if decision_entry is None else decision_entry.system_decision_before_ai,
        decision_after_ai=None if decision_entry is None else decision_entry.decision_after_ai,
        exec_stale=stale,
    )


def load_dashboard_snapshot(config: SystemConfig, paths: SystemPaths, *, timestamp_utc: str | None=None) -> DashboardSnapshot:
    instances = discover_instances(config, paths)
    views = tuple((read_instance_dashboard_view(paths, instance) for instance in instances))
    return DashboardSnapshot(generated_at_utc=timestamp_utc or now_utc(), instances=views, monitoring_lines=read_monitoring_log_lines(paths), action_feed=build_action_feed(paths, instances), system_name=config.system.name, root_path=str(paths.root))

def read_system_log_tail(paths: SystemPaths, *, max_lines: int=5) -> tuple[str, ...]:
    if max_lines <= 0:
        return ()
    log_dir = paths.logs_dir
    if not log_dir.is_dir():
        return ()
    log_files = sorted((entry for entry in log_dir.iterdir() if entry.is_file() and entry.suffix == '.log'), key=lambda entry: entry.stat().st_mtime, reverse=True)
    if not log_files:
        return ()
    lines = atomic_read_text(log_files[0]).splitlines()
    return tuple((line for line in lines[-max_lines:] if line.strip()))

def read_monitoring_log_lines(paths: SystemPaths, *, max_lines: int=10) -> tuple[str, ...]:
    lines = read_system_log_tail(paths, max_lines=max_lines * 3)
    monitoring_lines = [line for line in lines if ' metrics ' in line or ' alert code=' in line or 'runtime monitoring summary' in line]
    return tuple(monitoring_lines[-max_lines:])

def _view_to_dict(view: InstanceDashboardView) -> dict[str, Any]:
    data = asdict(view)
    instance = data.pop('instance')
    data['account_id'] = instance['account_id']
    data['symbol'] = instance['symbol']
    data['magic'] = instance['magic']
    return data

def snapshot_to_dict(snapshot: DashboardSnapshot) -> dict[str, Any]:
    return {'generated_at_utc': snapshot.generated_at_utc, 'system_name': snapshot.system_name, 'root_path': snapshot.root_path, 'instance_count': snapshot.instance_count, 'instances': [_view_to_dict(view) for view in snapshot.instances], 'action_feed': [asdict(event) for event in snapshot.action_feed], 'monitoring_lines': list(snapshot.monitoring_lines)}
