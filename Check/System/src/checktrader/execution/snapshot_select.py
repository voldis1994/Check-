"""Select newest valid bridge snapshot by sequence (not lexicographic filename)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from checktrader.execution.protocol import read_json


@dataclass(frozen=True, slots=True)
class SnapshotChoice:
    path: Path
    sequence: int
    generated_at_utc: str
    payload: dict[str, Any]


def select_latest_snapshot(
    directory: Path,
    *,
    min_sequence_exclusive: int | None = None,
) -> SnapshotChoice | None:
    """
    Choose the snapshot with the largest valid ``sequence``.

    Ties break on ``generated_at_utc``. Invalid/unreadable files are skipped.
    When ``min_sequence_exclusive`` is set, only sequences strictly greater are returned
    (stale/repeated sequences are ignored as "new").
    """
    if not directory.exists():
        return None
    best: SnapshotChoice | None = None
    for path in directory.glob("*.json"):
        try:
            payload = read_json(path)
            sequence = int(payload["sequence"])
            generated_at_utc = str(payload["generated_at_utc"])
        except (OSError, KeyError, TypeError, ValueError):
            continue
        if min_sequence_exclusive is not None and sequence <= min_sequence_exclusive:
            continue
        if best is None:
            best = SnapshotChoice(path, sequence, generated_at_utc, payload)
            continue
        if sequence > best.sequence or (sequence == best.sequence and generated_at_utc > best.generated_at_utc):
            best = SnapshotChoice(path, sequence, generated_at_utc, payload)
    return best
