"""MT4 OrderComment helpers for OPEN command correlation.

MT4 truncates order comments to 31 characters. Full UUIDs do not fit, so we use
the raw command_id when short enough, otherwise a deterministic C{hex8} token.
Python stores the same token in pending state for status reconciliation.
"""
from __future__ import annotations

MT4_ORDER_COMMENT_MAX_LEN = 31


def command_id_comment_hash32(command_id: str) -> int:
    """djb2 uint32 — must match SYSTEM_CommandIdCommentHash in MQL4."""
    hash_value = 5381
    for ch in command_id:
        hash_value = ((hash_value * 33) + ord(ch)) & 0xFFFFFFFF
    return hash_value


def build_open_order_comment(command_id: str) -> str:
    """Stable OrderComment for OPEN; always <= MT4_ORDER_COMMENT_MAX_LEN."""
    if not command_id:
        raise ValueError('command_id must be non-empty')
    if len(command_id) <= MT4_ORDER_COMMENT_MAX_LEN:
        return command_id
    return f'C{command_id_comment_hash32(command_id):08X}'


def order_comment_matches_expected(*, order_comment: str | None, expected_comment: str | None, command_id: str | None=None) -> bool:
    """True when broker comment contains the expected OPEN identifier."""
    if expected_comment is None and command_id is not None:
        expected_comment = build_open_order_comment(command_id)
    if not expected_comment:
        return False
    if order_comment is None:
        return False
    comment = order_comment.strip()
    if not comment:
        return False
    if comment == expected_comment:
        return True
    return expected_comment in comment
