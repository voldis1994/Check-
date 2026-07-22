"""Stable identifiers (UUID / SHA-256 only — never Python hash())."""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass


def new_message_id() -> str:
    return str(uuid.uuid4())


def new_command_id() -> str:
    return str(uuid.uuid4())


def sha256_hex(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class InstanceId:
    account_number: str
    symbol: str
    magic: int

    def as_key(self) -> str:
        return f"{self.account_number}:{self.symbol}:{self.magic}"
