"""Margin gate helpers."""

from __future__ import annotations


def margin_allows_trade(*, free_margin: float) -> bool:
    """Conservative gate used by risk.engine — free margin must be positive."""
    return free_margin > 0


__all__ = ["margin_allows_trade"]
