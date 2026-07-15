from __future__ import annotations
import os
import sys
from typing import Callable
from engine.dashboard.reader import DashboardSnapshot, InstanceDashboardView, RobotActionEvent
MODULE_NAME = 'dashboard.console'

RESET = '\033[0m'
BOLD = '\033[1m'
DIM = '\033[2m'
FG_BRAND = '\033[38;2;232;168;73m'
FG_INK = '\033[38;2;230;236;240m'
FG_MUTED = '\033[38;2;120;138;148m'
FG_LIVE = '\033[38;2;62;207;142m'
FG_ALERT = '\033[38;2;255;95;95m'
FG_BUY = '\033[38;2;64;196;160m'
FG_SELL = '\033[38;2;240;120;90m'
FG_WAIT = '\033[38;2;180;170;90m'
FG_LINE = '\033[38;2;45;58;66m'

def _color_enabled() -> bool:
    return sys.stdout.isatty() and os.environ.get('NO_COLOR') is None

def _c(code: str, text: str) -> str:
    if not _color_enabled():
        return text
    return f'{code}{text}{RESET}'

def _decision_color(decision: str | None) -> str:
    value = (decision or '').upper()
    if value == 'BUY':
        return FG_BUY
    if value == 'SELL':
        return FG_SELL
    if value in {'WAIT', 'BLOCK'}:
        return FG_WAIT
    return FG_INK

def _age_label(age_ms: int | None) -> str:
    if age_ms is None:
        return 'MISSING'
    if age_ms < 2000:
        return f'{age_ms}ms LIVE'
    if age_ms < 60000:
        return f'{age_ms / 1000:.1f}s'
    return f'{age_ms / 60000:.1f}m STALE'

def format_position(view: InstanceDashboardView) -> str:
    if view.open_ticket is None:
        return 'none'
    side = view.position_side or '-'
    volume = '-' if view.position_volume is None else f'{view.position_volume:.2f}'
    return f'{side} ticket={view.open_ticket} volume={volume}'

def format_instance_view(view: InstanceDashboardView) -> str:
    instance = view.instance
    spread = '-' if view.relative_spread is None else f'{view.relative_spread:.4f}'
    risk = view.risk_result or '-'
    if view.risk_reason:
        risk = f'{risk} ({view.risk_reason})'
    ack = view.last_ack_status or '-'
    if view.last_ack_command_id:
        ack = f'{ack} [{view.last_ack_command_id}]'
    error = '-'
    if view.last_error_message is not None:
        error_type = view.last_error_type or 'ERROR'
        error = f'{error_type}: {view.last_error_message}'
    health = view.instance_health or '-'
    cycle_latency = '-' if view.cycle_latency_ms is None else str(view.cycle_latency_ms)
    ack_latency = '-' if view.ack_latency_ms is None else str(view.ack_latency_ms)
    freshness = '-' if view.data_freshness_ms is None else str(view.data_freshness_ms)
    error_count = '-' if view.error_count is None else str(view.error_count)
    error_rate = '-' if view.error_rate_per_min is None else f'{view.error_rate_per_min:.2f}'
    return f'{instance.account_id}/{instance.symbol}/{instance.magic} decision={view.last_decision or "-"} reason={view.last_reason or "-"} risk={risk} spread={spread} position={format_position(view)} ack={ack} error={error} health={health} cycle_latency_ms={cycle_latency} ack_latency_ms={ack_latency} data_freshness_ms={freshness} error_count={error_count} error_rate_per_min={error_rate}'

def _format_action(event: RobotActionEvent) -> str:
    stamp = event.timestamp_utc.replace('T', ' ').replace('Z', '')
    if len(stamp) > 19:
        stamp = stamp[:19]
    prefix = f'{stamp}  {event.kind:<8} {event.symbol or "-":<7} {event.summary}'
    return f'{prefix}  {event.detail}'

def format_command_center(snapshot: DashboardSnapshot) -> str:
    width = 108
    rule = _c(FG_LINE, '─' * width)
    brand = _c(FG_BRAND + BOLD, snapshot.system_name)
    title = _c(FG_INK + BOLD, 'COMMAND CENTER')
    stamp = _c(FG_MUTED, snapshot.generated_at_utc)
    lines = [f'{brand}  {title}  {stamp}', _c(FG_MUTED, f'root={snapshot.root_path or "-"}  instances={snapshot.instance_count}  feed={len(snapshot.action_feed)}'), rule]
    if not snapshot.instances:
        lines.append(_c(FG_ALERT, 'no active instances — start PALAID.bat + attach SYSTEM_EA on M1'))
    for view in snapshot.instances:
        instance = view.instance
        decision = view.last_decision or '-'
        decision_text = _c(_decision_color(decision) + BOLD, decision)
        health = view.instance_health or 'UNKNOWN'
        health_color = FG_LIVE if health.upper() in {'VALID', 'OK', 'HEALTHY'} else FG_ALERT
        connected = 'YES' if view.broker_connected else 'NO' if view.broker_connected is False else '?'
        allowed = 'YES' if view.trade_allowed else 'NO' if view.trade_allowed is False else '?'
        lines.append(_c(FG_BRAND + BOLD, f'{instance.symbol}') + _c(FG_MUTED, f'  account={instance.account_id}  magic={instance.magic}  cycles={view.cycle_count if view.cycle_count is not None else "-"}'))
        lines.append(f'  NOW {_c(FG_MUTED, "decision=")}{decision_text}  {_c(FG_MUTED, "risk=")}{view.risk_result or "-"}  {_c(FG_MUTED, "health=")}{_c(health_color, health)}')
        lines.append(f'  {_c(FG_MUTED, "reason")} {view.last_reason or "-"}')
        if view.buy_score is not None or view.sell_score is not None:
            buy = '-' if view.buy_score is None else f'{view.buy_score:.3f}'
            sell = '-' if view.sell_score is None else f'{view.sell_score:.3f}'
            lines.append(f'  {_c(FG_MUTED, "scores (system)")} buy={_c(FG_BUY, buy)}  sell={_c(FG_SELL, sell)}')
        ai_mode = view.ai_mode or '-'
        ai_avail = '-' if view.ai_available is None else ('yes' if view.ai_available else 'no')
        ai_fb = '-' if view.ai_fallback_used is None else ('yes' if view.ai_fallback_used else 'no')
        before = view.system_decision_before_ai or '-'
        after = view.decision_after_ai or '-'
        lines.append(f'  {_c(FG_MUTED, "ai")} mode={ai_mode} available={ai_avail} fallback={ai_fb} system={before} after={after}')
        if view.ai_reason:
            lines.append(f'           {_c(FG_MUTED, "ai_reason")} {view.ai_reason}')
        spark = view.sparkline or _c(FG_MUTED, '(waiting for market bars)')
        close = '-' if view.last_close is None else f'{view.last_close:.5f}'
        bid = '-' if view.bid is None else f'{view.bid:.5f}'
        ask = '-' if view.ask is None else f'{view.ask:.5f}'
        spread = '-' if view.current_spread is None else f'{view.current_spread:.5f}'
        rel = '-' if view.relative_spread is None else f'{view.relative_spread:.2f}σ'
        lines.append(f'  {_c(FG_MUTED, "tape")} {spark}')
        lines.append(f'  {_c(FG_MUTED, "px")} close={close}  bid={bid}  ask={ask}  spread={spread} ({rel})')
        lines.append(f'  {_c(FG_MUTED, "ages")} market={_age_label(view.market_age_ms)}  sensor={_age_label(view.sensor_age_ms)}  status={_age_label(view.status_age_ms)}')
        lines.append(f'  {_c(FG_MUTED, "broker")} connected={connected}  trade_allowed={allowed}  bal={view.balance if view.balance is not None else "-"}  eq={view.equity if view.equity is not None else "-"}')
        if view.open_ticket is None:
            lines.append(f'  {_c(FG_MUTED, "position")} flat')
        else:
            lines.append(f'  {_c(FG_LIVE + BOLD, "POSITION")} {view.position_side} ticket={view.open_ticket} vol={view.position_volume} bars={view.position_bars_open}')
            lines.append(f'           entry={view.entry_price}  sl={view.stop_loss}  tp={view.take_profit or 0.0}')
        control = view.control_action or '-'
        trade = view.last_trade_event or '-'
        trade_ack = view.last_trade_ack or '-'
        ack = view.last_ack_status or '-'
        if view.exec_stale:
            lines.append(f'  {_c(FG_MUTED, "exec")} idle (flat)')
            lines.append(f'  {_c(FG_ALERT, "last_fail")} {trade}/{trade_ack}  ack={ack}  {view.last_trade_reason or ""}')
        else:
            lines.append(f'  {_c(FG_MUTED, "exec")} control={control}  trade={trade}/{trade_ack}  ack={ack}')
        if view.control_reason and not view.exec_stale:
            lines.append(f'           {_c(FG_MUTED, "control_reason")} {view.control_reason}')
        if view.last_error_message:
            lines.append(f'  {_c(FG_ALERT, "error")} {view.last_error_type}: {view.last_error_message}')
        lines.append(rule)
    lines.append(_c(FG_BRAND + BOLD, 'ROBOT ACTION FEED') + _c(FG_MUTED, '  (real journals + control + ack)'))
    if not snapshot.action_feed:
        lines.append(_c(FG_MUTED, '  waiting for first live cycle...'))
    else:
        for event in snapshot.action_feed[:18]:
            kind_color = FG_ALERT if event.kind == 'ERROR' else FG_LIVE if event.kind in {'TRADE', 'CONTROL', 'ACK'} else FG_INK
            lines.append('  ' + _c(kind_color, _format_action(event)))
    if snapshot.monitoring_lines:
        lines.append(rule)
        lines.append(_c(FG_MUTED, 'MONITORING'))
        for line in snapshot.monitoring_lines[-6:]:
            lines.append(_c(DIM, f'  {line[:width]}'))
    lines.append(rule)
    lines.append(_c(FG_MUTED, 'CMD: DASHBOARD.bat  |  live engine: PALAID.bat  |  Ctrl+C exit'))
    return '\n'.join(lines)

def format_dashboard(snapshot: DashboardSnapshot) -> str:
    return format_command_center(snapshot)

def clear_console() -> None:
    if os.name == 'nt':
        os.system('cls')
    else:
        sys.stdout.write('\033[2J\033[H')
        sys.stdout.flush()

def render_dashboard(snapshot: DashboardSnapshot, *, output: Callable[[str], None] | None=None, clear: bool=False) -> str:
    rendered = format_dashboard(snapshot)
    if output is not None:
        if clear:
            clear_console()
        output(rendered)
    return rendered

def live_console_printer(text: str) -> None:
    clear_console()
    print(text, flush=True)
