"""Lightweight in-process counters for ops visibility."""

from __future__ import annotations

from collections import Counter
from threading import Lock

_lock = Lock()
_counters: Counter[str] = Counter()


def incr(name: str, amount: int = 1) -> None:
    with _lock:
        _counters[name] += amount


def get_metrics() -> dict[str, int]:
    with _lock:
        return dict(_counters)


def reset_metrics() -> None:
    with _lock:
        _counters.clear()


__all__ = ["incr", "get_metrics", "reset_metrics"]
