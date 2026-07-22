"""Resolve whether the MT4 account is allowed (AUTO = trust bridge status)."""

from __future__ import annotations

from checktrader.config.models import SystemConfig

_AUTO_TOKENS = frozenset({"", "*", "AUTO", "auto", "FROM_MT4", "from_mt4", "ANY", "any"})


def is_auto_account_list(allowed: list[str]) -> bool:
    """Empty list or only AUTO tokens → accept whatever account MT4 reports."""
    if not allowed:
        return True
    normalized = [str(item).strip() for item in allowed if str(item).strip()]
    if not normalized:
        return True
    return all(item in _AUTO_TOKENS for item in normalized)


def account_is_allowed(config: SystemConfig, account_number: str) -> bool:
    account = str(account_number or "").strip()
    if not account:
        return False
    if is_auto_account_list(config.account.allowed_account_numbers):
        return True
    allowed = {str(item).strip() for item in config.account.allowed_account_numbers}
    return account in allowed
