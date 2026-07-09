from __future__ import annotations
import json
from pathlib import Path
from engine.core.atomic_io import atomic_write_text
from engine.core.history import archive_processed_ack, archive_processed_control
from engine.core.instance import Instance
from engine.core.paths import SystemPaths
from engine.execution.ack_reader import build_ack_path
from engine.execution.control_writer import build_control_path
from engine.protocol.constants import PROTOCOL_SCHEMA_VERSION

def _instance() -> Instance:
    return Instance(account_id='12345', symbol='EURUSD', magic=100001)

def test_archive_processed_control_moves_file_to_history(tmp_path: Path) -> None:
    paths = SystemPaths(tmp_path)
    paths.ensure_directories()
    instance = _instance()
    paths.ensure_account_directories(instance.account_id)
    control_path = build_control_path(paths, instance)
    atomic_write_text(control_path, '{"command_id":"cmd-1"}')
    archived = archive_processed_control(paths, instance)
    assert archived is not None
    assert not control_path.exists()
    assert archived.name == 'control_EURUSD_100001.json'

def test_archive_processed_ack_moves_file_to_history(tmp_path: Path) -> None:
    paths = SystemPaths(tmp_path)
    paths.ensure_directories()
    instance = _instance()
    paths.ensure_account_directories(instance.account_id)
    ack_path = build_ack_path(paths, instance)
    payload = {'schema_version': PROTOCOL_SCHEMA_VERSION, 'timestamp_utc': '2026-07-07T06:00:00.000Z', 'command_id': 'cmd-1', 'account_id': '12345', 'symbol': 'EURUSD', 'magic': 100001, 'status': 'SUCCESS'}
    atomic_write_text(ack_path, json.dumps(payload))
    archived = archive_processed_ack(paths, instance)
    assert archived is not None
    assert not ack_path.exists()
