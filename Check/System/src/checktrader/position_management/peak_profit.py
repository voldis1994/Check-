"""Peak net profit tracking helpers."""

from __future__ import annotations

from checktrader.domain.trailing import TrailingState


def update_peak_net_profit(trailing: TrailingState, current_net_profit: float) -> float:
    trailing.current_net_profit = current_net_profit
    trailing.peak_net_profit = max(trailing.peak_net_profit, current_net_profit)
    return trailing.peak_net_profit


def giveback_ratio(*, peak_net_profit: float, current_net_profit: float) -> float:
    eps = 1e-9
    return (peak_net_profit - current_net_profit) / max(abs(peak_net_profit), eps)


__all__ = ["update_peak_net_profit", "giveback_ratio"]
