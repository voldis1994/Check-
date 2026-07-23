"""Symbol identity helpers for multi-broker chart/position matching."""

from __future__ import annotations


def normalize_symbol(symbol: str | None) -> str:
    """Uppercase + strip common broker suffixes (Capital.com etc.)."""
    raw = (symbol or "").strip().upper()
    if not raw:
        return ""
    # Drop typical MT4 suffixes: EURUSD.r, EURUSDm, EURUSD_i, NATURALGAS.
    for sep in (".", "_", " "):
        if sep in raw:
            raw = raw.split(sep, 1)[0]
    # Trailing broker markers without separator (EURUSDm, EURUSDpro)
    for suffix in ("PRO", "MICRO", "MINI", "M", "I"):
        if len(raw) > len(suffix) + 2 and raw.endswith(suffix):
            # Only strip single-letter m/i when base looks like a FX pair (6–7 chars + suffix)
            if suffix in {"M", "I"} and len(raw) - len(suffix) not in {6, 7}:
                continue
            raw = raw[: -len(suffix)]
            break
    return raw


def symbols_match(a: str | None, b: str | None) -> bool:
    na, nb = normalize_symbol(a), normalize_symbol(b)
    return bool(na) and na == nb
