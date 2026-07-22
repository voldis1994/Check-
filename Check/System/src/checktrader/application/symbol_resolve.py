"""Resolve trading symbol from MT4 market snapshot vs optional config pin."""

from __future__ import annotations

from checktrader.config.models import SystemConfig
from checktrader.market_data.loader import MarketSnapshot

_AUTO_TOKENS = frozenset({"", "*", "AUTO", "auto", "FROM_MT4", "from_mt4"})


def is_auto_symbol(configured: str) -> bool:
    return configured.strip() in _AUTO_TOKENS


def resolve_trading_symbol(config: SystemConfig, market: MarketSnapshot) -> tuple[str | None, str]:
    """Return ``(symbol, mode)`` where mode is ``auto`` or ``pinned``.

    MT4 chart symbol (market snapshot) is the source of truth when config is AUTO.
    When config pins a concrete symbol, it must match the snapshot.
    """
    market_symbol = (market.specs.symbol or "").strip()
    if not market_symbol:
        return None, "missing"
    configured = (config.instrument.symbol or "").strip()
    if is_auto_symbol(configured):
        return market_symbol, "auto"
    if configured != market_symbol:
        return None, "mismatch"
    return market_symbol, "pinned"
