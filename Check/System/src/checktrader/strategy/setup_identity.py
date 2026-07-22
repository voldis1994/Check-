"""Setup fingerprint (SHA-256)."""

from __future__ import annotations

from checktrader.domain.enums import Side
from checktrader.domain.identifiers import sha256_hex


def build_setup_fingerprint(
    *,
    setup_version: str,
    symbol: str,
    setup_type: str,
    direction: Side,
    context_structure_id: str,
    pullback_structure_id: str,
    setup_origin_timestamp: str,
    trigger_level: float,
    invalidation_level: float,
    digits: int,
) -> str:
    payload = "|".join(
        [
            setup_version,
            symbol,
            setup_type,
            direction.value,
            context_structure_id,
            pullback_structure_id,
            setup_origin_timestamp,
            f"{trigger_level:.{digits}f}",
            f"{invalidation_level:.{digits}f}",
        ]
    )
    return sha256_hex(payload)
