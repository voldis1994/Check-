from __future__ import annotations

from pathlib import Path


def processed_command_gv_name(account_id: str, symbol: str, magic: int) -> str:
    return f'SYSTEM_CMD_{account_id}_{symbol}_{magic}'


def command_id_hash(command_id: str) -> float:
    hash_value = 5381.0
    for char in command_id:
        hash_value = hash_value * 33.0 + float(ord(char))
    return hash_value


class CommandIdempotenceStore:
    """Python mirror of MQL4 command idempotence: mark before ack write."""

    def __init__(self, *, store_dir: Path | None = None) -> None:
        self._memory: dict[str, str] = {}
        self._gv: dict[str, float] = {}
        self._store_dir = store_dir
        if store_dir is not None:
            store_dir.mkdir(parents=True, exist_ok=True)

    def _key(self, account_id: str, symbol: str, magic: int) -> str:
        return processed_command_gv_name(account_id, symbol, magic)

    def _file_path(self, account_id: str, symbol: str, magic: int) -> Path | None:
        if self._store_dir is None:
            return None
        return self._store_dir / f'processed_cmd_{symbol}_{magic}.txt'

    def is_processed(self, account_id: str, symbol: str, magic: int, command_id: str) -> bool:
        if not command_id:
            return False
        key = self._key(account_id, symbol, magic)
        if self._memory.get(key) == command_id:
            return True
        if key in self._gv and self._gv[key] == command_id_hash(command_id):
            return True
        path = self._file_path(account_id, symbol, magic)
        if path is not None and path.exists():
            return path.read_text(encoding='utf-8').strip() == command_id
        return False

    def mark_processed(self, account_id: str, symbol: str, magic: int, command_id: str) -> None:
        if not command_id:
            return
        key = self._key(account_id, symbol, magic)
        self._memory[key] = command_id
        self._gv[key] = command_id_hash(command_id)
        path = self._file_path(account_id, symbol, magic)
        if path is not None:
            path.write_text(command_id + '\n', encoding='utf-8')

    def load_processed(self, account_id: str, symbol: str, magic: int) -> str:
        key = self._key(account_id, symbol, magic)
        if key in self._memory:
            return self._memory[key]
        path = self._file_path(account_id, symbol, magic)
        if path is not None and path.exists():
            return path.read_text(encoding='utf-8').strip()
        return ''


def try_execute_with_idempotence(
    *,
    command_id: str,
    account_id: str,
    symbol: str,
    magic: int,
    store: CommandIdempotenceStore,
    last_processed_command_id: str,
    execute_open,
    write_ack,
) -> tuple[bool, str, bool]:
    """
    Mirror SYSTEM_TryExecutePendingControl success path:
    - skip duplicate command_id without re-opening
    - mark processed immediately after successful open, before ack write
    - if ack write fails after success, keep processed and do not retry open

    Returns (did_open, processed_command_id, ack_written).
    """
    if command_id == last_processed_command_id or store.is_processed(account_id, symbol, magic, command_id):
        write_ack(command_id, success=True, duplicate=True)
        return (False, '', True)

    opened = execute_open(command_id)
    if not opened:
        write_ack(command_id, success=False, duplicate=False)
        return (False, '', True)

    store.mark_processed(account_id, symbol, magic, command_id)
    ack_ok = write_ack(command_id, success=True, duplicate=False)
    return (True, command_id, ack_ok)
