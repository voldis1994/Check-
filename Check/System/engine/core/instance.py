from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable
from engine.protocol.constants import FILENAME_ACK, FILENAME_CONTROL, FILENAME_DECISION_JOURNAL, FILENAME_ERROR_JOURNAL, FILENAME_INSTANCE_STATE, FILENAME_MARKET, FILENAME_MONITORING_SNAPSHOT, FILENAME_SENSOR, FILENAME_SPREAD_STATE, FILENAME_STATUS, FILENAME_TRADE_JOURNAL
from engine.protocol.identity import validate_account_id, validate_magic, validate_symbol
from engine.protocol.errors import ValidationError
INSTANCE_MODULE = 'core.instance'

def _validation_error(message: str, **context: object) -> ValidationError:
    return ValidationError(message, module=INSTANCE_MODULE, context=dict(context))

@dataclass(frozen=True)
class Instance:
    account_id: str
    symbol: str
    magic: int

    def __post_init__(self) -> None:
        object.__setattr__(self, 'account_id', validate_account_id(self.account_id, INSTANCE_MODULE))
        object.__setattr__(self, 'symbol', validate_symbol(self.symbol, INSTANCE_MODULE))
        object.__setattr__(self, 'magic', validate_magic(self.magic, INSTANCE_MODULE))

    @property
    def instance_key(self) -> tuple[str, str, int]:
        return (self.account_id, self.symbol, self.magic)

    def matches(self, account_id: str, symbol: str, magic: int) -> bool:
        return self.instance_key == (validate_account_id(account_id, INSTANCE_MODULE), validate_symbol(symbol, INSTANCE_MODULE), validate_magic(magic, INSTANCE_MODULE))

    def market_filename(self) -> str:
        return FILENAME_MARKET.format(symbol=self.symbol, magic=self.magic)

    def sensor_filename(self) -> str:
        return FILENAME_SENSOR.format(symbol=self.symbol, magic=self.magic)

    def control_filename(self) -> str:
        return FILENAME_CONTROL.format(symbol=self.symbol, magic=self.magic)

    def ack_filename(self) -> str:
        return FILENAME_ACK.format(symbol=self.symbol, magic=self.magic)

    def decision_journal_filename(self) -> str:
        return FILENAME_DECISION_JOURNAL.format(symbol=self.symbol, magic=self.magic)

    def trade_journal_filename(self) -> str:
        return FILENAME_TRADE_JOURNAL.format(symbol=self.symbol, magic=self.magic)

    def error_journal_filename(self) -> str:
        return FILENAME_ERROR_JOURNAL.format(symbol=self.symbol, magic=self.magic)

    def instance_state_filename(self) -> str:
        return FILENAME_INSTANCE_STATE.format(symbol=self.symbol, magic=self.magic)

    def spread_state_filename(self) -> str:
        return FILENAME_SPREAD_STATE.format(symbol=self.symbol, magic=self.magic)

    def monitoring_snapshot_filename(self) -> str:
        return FILENAME_MONITORING_SNAPSHOT.format(symbol=self.symbol, magic=self.magic)

    def status_filename(self) -> str:
        return FILENAME_STATUS.format(account_id=self.account_id)

def ensure_unique_instance_keys(instances: Iterable[Instance]) -> None:
    seen: set[tuple[str, str, int]] = set()
    duplicates: list[tuple[str, str, int]] = []
    for instance in instances:
        key = instance.instance_key
        if key in seen and key not in duplicates:
            duplicates.append(key)
        seen.add(key)
    if duplicates:
        raise _validation_error('duplicate instance keys detected', duplicates=duplicates)
