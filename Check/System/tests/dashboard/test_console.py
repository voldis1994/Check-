from __future__ import annotations
import ast
import importlib
import json
import shutil
from pathlib import Path
import pytest
from engine.core.config import parse_config_payload
from engine.core.instance import Instance
from engine.core.lifecycle import build_system_paths
from engine.core.paths import SystemPaths
from engine.dashboard.console import format_dashboard, format_instance_view, format_position, render_dashboard
from engine.dashboard.reader import DashboardSnapshot, InstanceDashboardView, load_dashboard_snapshot, read_instance_dashboard_view, read_last_ack, read_last_decision_entry, read_last_error_entry, read_last_journal_line, read_system_log_tail
from engine.execution.control_writer import build_control_path
from engine.journal.decision_journal import append_decision_journal_entry
from engine.journal.error_journal import log_error
from engine.normalizer.spread_model import update_spread_model
from engine.protocol.constants import Decision, ErrorType, PROTOCOL_SCHEMA_VERSION, RiskResult
from engine.protocol.models import DecisionJournalEntry
from engine.state.instance_state import InstanceState
from engine.state.spread_state import SpreadState
from tests.core.config_payload import valid_system_config_payload
FIXTURES_DIR = Path(__file__).parent.parent / 'loader' / 'fixtures'

def _write_config(root: Path, *, refresh_interval_ms: int=1000) -> Path:
    payload = valid_system_config_payload()
    payload['system']['root_path'] = str(root)
    payload['dashboard'] = {'refresh_interval_ms': refresh_interval_ms}
    config_dir = root / 'config'
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / 'system.json'
    config_path.write_text(json.dumps(payload), encoding='utf-8')
    return config_path

def _instance() -> Instance:
    return Instance(account_id='12345', symbol='EURUSD', magic=100001)

def _install_dashboard_fixtures(paths: SystemPaths, instance: Instance) -> None:
    paths.ensure_account_directories(instance.account_id)
    account_dir = paths.account_dir(instance.account_id)
    market_csv = 'time_utc,open,high,low,close,volume,symbol,timeframe,digits,point\n2026-07-07T06:00:00.000Z,1.10000,1.10200,1.09900,1.10150,120,EURUSD,M1,5,0.00001\n'
    (account_dir / instance.market_filename()).write_text(market_csv, encoding='utf-8')
    shutil.copyfile(FIXTURES_DIR / 'status_valid.json', account_dir / instance.status_filename())
    shutil.copyfile(FIXTURES_DIR / 'universe_valid.json', account_dir / 'universe.json')

def _decision_entry(instance: Instance) -> DecisionJournalEntry:
    return DecisionJournalEntry(decision_id='decision-dashboard-1', timestamp_utc='2026-07-07T06:00:00.000Z', account_id=instance.account_id, symbol=instance.symbol, magic=instance.magic, decision=Decision.BUY.value, reason='BUY: preferred side selected', buy_score=0.8, sell_score=0.2, risk_result=RiskResult.ALLOW.value)

def _dashboard_paths(tmp_path: Path) -> tuple[SystemPaths, object]:
    config_path = _write_config(tmp_path)
    config = parse_config_payload(json.loads(config_path.read_text(encoding='utf-8')))
    paths = build_system_paths(config)
    paths.ensure_directories()
    return (paths, config)

def test_read_last_journal_line_returns_last_non_empty_line(tmp_path: Path) -> None:
    journal_path = tmp_path / 'journal.jsonl'
    journal_path.write_text('{"a":1}\n\n{"b":2}\n', encoding='utf-8')
    assert read_last_journal_line(journal_path) == '{"b":2}'
    assert read_last_journal_line(tmp_path / 'missing.jsonl') is None

def test_read_last_decision_entry_returns_parsed_decision(tmp_path: Path) -> None:
    paths, _ = _dashboard_paths(tmp_path)
    instance = _instance()
    _install_dashboard_fixtures(paths, instance)
    append_decision_journal_entry(paths, instance, _decision_entry(instance))
    entry = read_last_decision_entry(paths, instance)
    assert entry is not None
    assert entry.decision == Decision.BUY.value
    assert entry.reason == 'BUY: preferred side selected'

def test_read_last_error_entry_returns_parsed_error(tmp_path: Path) -> None:
    paths, _ = _dashboard_paths(tmp_path)
    instance = _instance()
    _install_dashboard_fixtures(paths, instance)
    log_error(paths, instance, module='dashboard.test', error_type=ErrorType.VALIDATION.value, message='market validation failed')
    entry = read_last_error_entry(paths, instance)
    assert entry is not None
    assert entry.error_type == ErrorType.VALIDATION.value
    assert entry.message == 'market validation failed'

def test_read_last_ack_returns_status_and_command_id(tmp_path: Path) -> None:
    paths, _ = _dashboard_paths(tmp_path)
    instance = _instance()
    _install_dashboard_fixtures(paths, instance)
    from engine.core.atomic_io import atomic_write_text
    from engine.execution.ack_reader import build_ack_path
    atomic_write_text(build_ack_path(paths, instance), f'{{\n  "schema_version": "{PROTOCOL_SCHEMA_VERSION}",\n  "timestamp_utc": "2026-07-07T06:00:00.000Z",\n  "command_id": "cmd-dashboard-1",\n  "account_id": "12345",\n  "symbol": "EURUSD",\n  "magic": 100001,\n  "status": "SUCCESS",\n  "ticket": 321\n}}')
    status, command_id = read_last_ack(paths, instance)
    assert status == 'SUCCESS'
    assert command_id == 'cmd-dashboard-1'

def test_read_instance_dashboard_view_aggregates_state_and_journals(tmp_path: Path) -> None:
    paths, _ = _dashboard_paths(tmp_path)
    instance = _instance()
    _install_dashboard_fixtures(paths, instance)
    state = InstanceState(instance=instance)
    state.update_position(open_ticket=555, position_side='BUY', position_volume=0.1)
    state.save(paths)
    spread_state = SpreadState(instance=instance)
    snapshot = update_spread_model((0.0001, 0.0002), current_spread=0.0003, lookback_bars=3)
    spread_state.update_from_snapshot(snapshot, '2026-07-07T06:00:00.000Z')
    spread_state.save(paths)
    append_decision_journal_entry(paths, instance, _decision_entry(instance))
    view = read_instance_dashboard_view(paths, instance)
    assert isinstance(view, InstanceDashboardView)
    assert view.last_decision == Decision.BUY.value
    assert view.last_reason == 'BUY: preferred side selected'
    assert view.risk_result == RiskResult.ALLOW.value
    assert view.relative_spread == pytest.approx(snapshot.relative_spread)
    assert view.open_ticket == 555
    assert view.position_side == 'BUY'

def test_load_dashboard_snapshot_returns_all_instances(tmp_path: Path) -> None:
    paths, config = _dashboard_paths(tmp_path)
    instance = _instance()
    _install_dashboard_fixtures(paths, instance)
    append_decision_journal_entry(paths, instance, _decision_entry(instance))
    snapshot = load_dashboard_snapshot(config, paths, timestamp_utc='2026-07-07T06:00:00.000Z')
    assert isinstance(snapshot, DashboardSnapshot)
    assert snapshot.instance_count == 1
    assert snapshot.instances[0].last_decision == Decision.BUY.value

def test_format_dashboard_displays_last_decision(tmp_path: Path) -> None:
    paths, config = _dashboard_paths(tmp_path)
    instance = _instance()
    _install_dashboard_fixtures(paths, instance)
    append_decision_journal_entry(paths, instance, _decision_entry(instance))
    snapshot = load_dashboard_snapshot(config, paths, timestamp_utc='2026-07-07T06:00:00.000Z')
    rendered = format_dashboard(snapshot)
    assert 'decision=BUY' in rendered
    assert 'BUY: preferred side selected' in rendered
    assert 'instances=1' in rendered

def test_format_position_and_instance_view_render_expected_fields() -> None:
    view = InstanceDashboardView(instance=_instance(), last_decision=Decision.SELL.value, last_reason='SELL: preferred side selected', risk_result=RiskResult.ALLOW.value, risk_reason=None, relative_spread=1.25, open_ticket=100, position_side='SELL', position_volume=0.2, last_ack_status='SUCCESS', last_ack_command_id='cmd-1', last_error_message=None, last_error_type=None, instance_health='VALID', cycle_latency_ms=1200, ack_latency_ms=500, data_freshness_ms=60000, error_count=0, error_rate_per_min=0.0)
    assert format_position(view) == 'SELL ticket=100 volume=0.20'
    rendered = format_instance_view(view)
    assert 'decision=SELL' in rendered
    assert 'spread=1.2500' in rendered
    assert 'ack=SUCCESS [cmd-1]' in rendered
    assert 'health=VALID' in rendered
    assert 'cycle_latency_ms=1200' in rendered
    assert 'error_rate_per_min=0.00' in rendered

def test_render_dashboard_returns_formatted_text() -> None:
    snapshot = DashboardSnapshot(generated_at_utc='2026-07-07T06:00:00.000Z', instances=())
    captured: list[str] = []
    rendered = render_dashboard(snapshot, output=captured.append)
    assert rendered == captured[0]
    assert 'no active instances' in rendered

def test_dashboard_does_not_write_control(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths, config = _dashboard_paths(tmp_path)
    instance = _instance()
    _install_dashboard_fixtures(paths, instance)

    def _fail_publish(*_args: object, **_kwargs: object) -> None:
        raise AssertionError('dashboard must not publish control')
    monkeypatch.setattr('engine.execution.control_writer.publish_control', _fail_publish)
    snapshot = load_dashboard_snapshot(config, paths)
    render_dashboard(snapshot)
    assert not build_control_path(paths, instance).exists()

def test_dashboard_does_not_call_analysis_decision_or_risk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths, config = _dashboard_paths(tmp_path)
    instance = _instance()
    _install_dashboard_fixtures(paths, instance)
    append_decision_journal_entry(paths, instance, _decision_entry(instance))

    def _forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError('dashboard must not invoke trading engines')
    monkeypatch.setattr('engine.analysis.engine.run_analysis_engine', _forbidden)
    monkeypatch.setattr('engine.decision.engine.run_decision_engine', _forbidden)
    monkeypatch.setattr('engine.risk.engine.run_risk_engine', _forbidden)
    snapshot = load_dashboard_snapshot(config, paths)
    render_dashboard(snapshot)

def test_dashboard_modules_do_not_import_analysis_decision_or_risk() -> None:
    forbidden_roots = {'engine.analysis', 'engine.decision', 'engine.risk'}
    module_names = ('engine.dashboard.reader', 'engine.dashboard.console', 'dashboard')
    for module_name in module_names:
        module = importlib.import_module(module_name)
        source = Path(module.__file__).read_text(encoding='utf-8')
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split('.')[0:2]
                    joined = '.'.join(root)
                    if joined in forbidden_roots or alias.name.split('.')[0] in {'analysis', 'decision', 'risk'}:
                        pytest.fail(f'{module_name} imports forbidden module {alias.name}')
            if isinstance(node, ast.ImportFrom) and node.module is not None:
                if node.module.startswith('engine.analysis'):
                    pytest.fail(f'{module_name} imports forbidden module {node.module}')
                if node.module.startswith('engine.decision'):
                    pytest.fail(f'{module_name} imports forbidden module {node.module}')
                if node.module.startswith('engine.risk'):
                    pytest.fail(f'{module_name} imports forbidden module {node.module}')

def test_run_dashboard_main_refreshes_on_interval(tmp_path: Path) -> None:
    import dashboard as dashboard_module
    config_path = _write_config(tmp_path, refresh_interval_ms=100)
    refresh_calls: list[int] = []
    original_refresh = dashboard_module.refresh_dashboard

    def _counting_refresh(runtime, **kwargs: object) -> str:
        refresh_calls.append(1)
        if len(refresh_calls) >= 2:
            dashboard_module.request_dashboard_shutdown(runtime)
        return original_refresh(runtime, **kwargs)

    def _fast_sleep(_seconds: float) -> None:
        return None
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(dashboard_module, 'refresh_dashboard', _counting_refresh)
    exit_code = dashboard_module.run_dashboard_main(root_path=tmp_path, config_path=config_path, sleep_fn=_fast_sleep)
    monkeypatch.undo()
    assert exit_code == 0
    assert len(refresh_calls) >= 2

def test_read_system_log_tail_returns_recent_lines(tmp_path: Path) -> None:
    paths, _ = _dashboard_paths(tmp_path)
    paths.logs_dir.mkdir(parents=True, exist_ok=True)
    (paths.logs_dir / 'system_2026-07-07.log').write_text('line-1\nline-2\nline-3\n', encoding='utf-8')
    tail = read_system_log_tail(paths, max_lines=2)
    assert tail == ('line-2', 'line-3')
