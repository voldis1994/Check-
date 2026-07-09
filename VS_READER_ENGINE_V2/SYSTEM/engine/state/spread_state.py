from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from engine.core.atomic_io import atomic_read_text, atomic_write_text
from engine.core.instance import Instance
from engine.core.paths import SystemPaths
from engine.normalizer.spread_model import SpreadModelSnapshot
from engine.protocol.constants import STATE_SCHEMA_VERSION
from engine.protocol.errors import ValidationError
from engine.protocol.models import SpreadStateRecord
from engine.protocol.parser import parse_spread_state
from engine.protocol.writer import write_spread_state


@dataclass
class SpreadState:
    instance: Instance
    record: SpreadStateRecord | None = None

    def path(self, paths: SystemPaths) -> Path:
        return paths.account_state_dir(self.instance.account_id) / self.instance.spread_state_filename()

    def update_from_snapshot(self, snapshot: SpreadModelSnapshot, updated_utc: str) -> SpreadStateRecord:
        self.record = SpreadStateRecord(
            schema_version=STATE_SCHEMA_VERSION,
            account_id=self.instance.account_id,
            symbol=self.instance.symbol,
            magic=self.instance.magic,
            sample_count=snapshot.sample_count,
            mean_spread=snapshot.mean_spread,
            std_spread=snapshot.std_spread,
            median_spread=snapshot.median_spread,
            current_spread=snapshot.current_spread,
            relative_spread=snapshot.relative_spread,
            updated_utc=updated_utc,
        )
        return self.record

    def save(self, paths: SystemPaths) -> None:
        if self.record is None:
            raise ValidationError(
                "spread state record is not initialized",
                module="state.spread_state",
            )
        paths.ensure_account_directories(self.instance.account_id)
        atomic_write_text(self.path(paths), write_spread_state(self.record))

    @classmethod
    def load(cls, paths: SystemPaths, instance: Instance) -> SpreadState:
        state = cls(instance=instance, record=None)
        state_path = state.path(paths)
        if not state_path.exists():
            return state
        raw_text = atomic_read_text(state_path)
        state.record = parse_spread_state(raw_text)
        return state
