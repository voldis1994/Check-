from __future__ import annotations
from pathlib import Path
from checktrader.bridge.atomic_files import write_json_atomic
from checktrader.bridge.protocol import command_message
from checktrader.domain.models import Command

def write_command(bridge_dir: Path, command: Command) -> Path:
    path=bridge_dir/f'command_{command.command_id}.json'; write_json_atomic(path, command_message(command)); return path
