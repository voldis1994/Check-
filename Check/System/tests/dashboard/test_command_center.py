from __future__ import annotations
import json
from pathlib import Path
import pytest
from engine.core.atomic_io import atomic_write_text
from engine.core.instance import Instance
from engine.dashboard.console import format_command_center, format_dashboard
from engine.dashboard.reader import build_action_feed, load_dashboard_snapshot, read_instance_dashboard_view, read_market_sparkline, snapshot_to_dict
from engine.dashboard.web import create_dashboard_handler
from engine.execution.ack_reader import build_ack_path
from engine.execution.control_writer import build_control_path
from engine.journal.decision_journal import append_decision_journal_entry
from engine.journal.trade_journal import append_trade_journal_entry
from engine.protocol.constants import Decision, PROTOCOL_SCHEMA_VERSION, RiskResult, TradeEvent
from engine.protocol.models import DecisionJournalEntry, TradeJournalEntry
from engine.state.instance_state import InstanceState
from tests.dashboard.test_console import _dashboard_paths, _install_dashboard_fixtures, _instance

def test_read_instance_dashboard_view_includes_live_market_and_control(tmp_path: Path) -> None:
    paths, _ = _dashboard_paths(tmp_path)
    instance = _instance()
    _install_dashboard_fixtures(paths, instance)
    account_dir = paths.account_dir(instance.account_id)
    (account_dir / instance.sensor_filename()).write_text('time_utc,bid,ask,spread,spread_points,symbol,digits,point\n2026-07-07T06:00:00.000Z,1.10140,1.10160,0.00020,20,EURUSD,5,0.00001\n', encoding='utf-8')
    atomic_write_text(build_control_path(paths, instance), f'{{\n  "schema_version": "{PROTOCOL_SCHEMA_VERSION}",\n  "timestamp_utc": "2026-07-07T06:00:01.000Z",\n  "command_id": "cmd-1",\n  "account_id": "12345",\n  "symbol": "EURUSD",\n  "magic": 100001,\n  "action": "MODIFY",\n  "reason": "TRAILING",\n  "decision_id": "d1",\n  "ticket": 555,\n  "stop_loss": 1.1008\n}}')
    state = InstanceState(instance=instance)
    state.update_position(open_ticket=555, position_side='BUY', position_volume=0.01, entry_price=1.1, stop_loss=1.098, take_profit=0.0)
    state.save(paths)
    view = read_instance_dashboard_view(paths, instance)
    assert view.bid == pytest.approx(1.1014)
    assert view.ask == pytest.approx(1.1016)
    assert view.control_action == 'MODIFY'
    assert view.control_reason == 'TRAILING'
    assert view.open_ticket == 555
    assert view.entry_price == pytest.approx(1.1)
    assert view.sparkline
    assert view.last_close == pytest.approx(1.1015)

def test_action_feed_merges_decision_trade_and_control(tmp_path: Path) -> None:
    paths, _ = _dashboard_paths(tmp_path)
    instance = _instance()
    _install_dashboard_fixtures(paths, instance)
    append_decision_journal_entry(paths, instance, DecisionJournalEntry(decision_id='d1', timestamp_utc='2026-07-07T06:00:00.000Z', account_id=instance.account_id, symbol=instance.symbol, magic=instance.magic, decision=Decision.BUY.value, reason='BUY preferred', risk_result=RiskResult.ALLOW.value, buy_score=0.8, sell_score=0.2))
    append_trade_journal_entry(paths, instance, TradeJournalEntry(trade_id='t1', timestamp_utc='2026-07-07T06:00:02.000Z', account_id=instance.account_id, symbol=instance.symbol, magic=instance.magic, event=TradeEvent.OPEN.value, command_id='cmd-open', ack_status='SUCCESS', reason='OPEN filled', side='BUY', volume=0.01, ticket=100))
    atomic_write_text(build_control_path(paths, instance), f'{{\n  "schema_version": "{PROTOCOL_SCHEMA_VERSION}",\n  "timestamp_utc": "2026-07-07T06:00:03.000Z",\n  "command_id": "cmd-2",\n  "account_id": "12345",\n  "symbol": "EURUSD",\n  "magic": 100001,\n  "action": "OPEN",\n  "reason": "BUY",\n  "decision_id": "d1",\n  "side": "BUY",\n  "volume": 0.01,\n  "stop_loss": 1.098,\n  "take_profit": 0.0\n}}')
    feed = build_action_feed(paths, (instance,))
    kinds = {event.kind for event in feed}
    assert 'DECISION' in kinds
    assert 'TRADE' in kinds
    assert 'CONTROL' in kinds

def test_format_command_center_shows_robot_feed(tmp_path: Path) -> None:
    paths, config = _dashboard_paths(tmp_path)
    instance = _instance()
    _install_dashboard_fixtures(paths, instance)
    append_decision_journal_entry(paths, instance, DecisionJournalEntry(decision_id='d1', timestamp_utc='2026-07-07T06:00:00.000Z', account_id=instance.account_id, symbol=instance.symbol, magic=instance.magic, decision=Decision.SELL.value, reason='SELL preferred', risk_result=RiskResult.ALLOW.value))
    snapshot = load_dashboard_snapshot(config, paths, timestamp_utc='2026-07-07T06:00:05.000Z')
    rendered = format_command_center(snapshot)
    assert 'COMMAND CENTER' in rendered
    assert 'ROBOT ACTION FEED' in rendered
    assert 'SELL' in rendered
    assert format_dashboard(snapshot) == rendered

def test_snapshot_to_dict_is_json_serializable(tmp_path: Path) -> None:
    paths, config = _dashboard_paths(tmp_path)
    instance = _instance()
    _install_dashboard_fixtures(paths, instance)
    snapshot = load_dashboard_snapshot(config, paths, timestamp_utc='2026-07-07T06:00:05.000Z')
    payload = snapshot_to_dict(snapshot)
    encoded = json.dumps(payload)
    assert 'instance_count' in encoded
    assert payload['instance_count'] == 1

def test_web_handler_serves_html_and_snapshot(tmp_path: Path) -> None:
    paths, config = _dashboard_paths(tmp_path)
    instance = _instance()
    _install_dashboard_fixtures(paths, instance)
    snapshot = load_dashboard_snapshot(config, paths, timestamp_utc='2026-07-07T06:00:05.000Z')
    handler_cls = create_dashboard_handler(lambda: snapshot)
    captured: dict[str, object] = {}

    class Probe(handler_cls):  # type: ignore[misc,valid-type]
        def __init__(self) -> None:
            self.path = '/'
            self.wfile = type('W', (), {'write': lambda self, b: captured.__setitem__('body', b)})()
            self._headers: list[tuple[str, str]] = []

        def send_response(self, code: int) -> None:
            captured['code'] = code

        def send_header(self, key: str, value: str) -> None:
            self._headers.append((key, value))

        def end_headers(self) -> None:
            captured['headers'] = list(self._headers)

    probe = Probe()
    probe.do_GET()
    assert captured['code'] == 200
    assert b'SYSTEM' in captured['body']
    assert b'phone' in captured['body'].lower() or b'LIVE' in captured['body']
    probe.path = '/api/snapshot'
    probe.do_GET()
    assert captured['code'] == 200
    assert b'generated_at_utc' in captured['body']
    probe.path = '/manifest.webmanifest'
    probe.do_GET()
    assert captured['code'] == 200
    assert b'short_name' in captured['body']
    probe.path = '/icon.svg'
    probe.do_GET()
    assert captured['code'] == 200
    assert b'<svg' in captured['body']

def test_dashboard_modules_forbid_trading_engine_imports() -> None:
    import ast
    import importlib
    forbidden = ('engine.analysis', 'engine.decision', 'engine.risk')
    for module_name in ('engine.dashboard.reader', 'engine.dashboard.console', 'engine.dashboard.web', 'dashboard'):
        module = importlib.import_module(module_name)
        source = Path(module.__file__).read_text(encoding='utf-8')
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module is not None:
                for root in forbidden:
                    if node.module.startswith(root):
                        pytest.fail(f'{module_name} imports forbidden module {node.module}')

def test_dashboard_bind_lan_prints_phone_url(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    import dashboard as dashboard_module
    monkeypatch.setattr(dashboard_module, '_resolve_lan_ip', lambda: '192.168.0.55')
    dashboard_module._print_dashboard_urls(web_host='0.0.0.0', web_port=8765, bind_lan=True)
    captured = capsys.readouterr().out
    assert '127.0.0.1:8765' in captured
    assert '192.168.0.55:8765' in captured
