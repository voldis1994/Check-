"""Margin gate helpers for fixed-lot orders."""

from __future__ import annotations


def margin_allows_trade(*, free_margin: float) -> bool:
    """Conservative gate — free margin must be positive."""
    return free_margin > 0


def margin_allows_fixed_lot(*, free_margin: float, fixed_lot: float) -> bool:
    """Margin must be positive for the exact fixed lot (never resize)."""
    return fixed_lot > 0 and free_margin > 0


__all__ = ["margin_allows_trade", "margin_allows_fixed_lot"]
