from __future__ import annotations
from tools.analyze_trade_series import ClosedTrade, summarize


def test_bucket_thresholds() -> None:
    bad = ClosedTrade(1, 'BUY', 1.1, 1.098, 1.0985, 't')
    good = ClosedTrade(2, 'BUY', 1.1, 1.1015, 1.0985, 't')
    excellent = ClosedTrade(3, 'BUY', 1.1, 1.104, 1.0985, 't')
    assert bad.bucket == 'bad'
    assert good.bucket == 'good'
    assert excellent.bucket == 'excellent'


def test_summarize_classifies_positive_mix() -> None:
    trades = [
        ClosedTrade(1, 'BUY', 1.1, 1.098, 1.098, 't'),
        ClosedTrade(2, 'BUY', 1.1, 1.098, 1.098, 't'),
        ClosedTrade(3, 'BUY', 1.1, 1.101, 1.098, 't'),
        ClosedTrade(4, 'BUY', 1.1, 1.1015, 1.098, 't'),
        ClosedTrade(5, 'BUY', 1.1, 1.105, 1.098, 't'),
        ClosedTrade(6, 'BUY', 1.1, 1.106, 1.098, 't'),
    ]
    summary = summarize(trades, title='unit')
    assert summary['count'] == 6
    assert summary['mean_r'] > 0
