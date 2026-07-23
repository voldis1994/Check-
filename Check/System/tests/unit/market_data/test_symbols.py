from __future__ import annotations

from checktrader.market_data.symbols import normalize_symbol, symbols_match


def test_normalize_strips_broker_suffixes() -> None:
    assert normalize_symbol("EURUSD.r") == "EURUSD"
    assert normalize_symbol("EURUSDm") == "EURUSD"
    assert normalize_symbol("naturalgas") == "NATURALGAS"
    assert normalize_symbol("NATURALGAS.") == "NATURALGAS"


def test_symbols_match_across_suffix() -> None:
    assert symbols_match("EURUSD", "EURUSD.r")
    assert symbols_match("EURUSDm", "EURUSD")
    assert not symbols_match("EURUSD", "USDCHF")
    assert not symbols_match("", "EURUSD")
