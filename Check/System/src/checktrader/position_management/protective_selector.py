"""Protective action selector — wraps engine.choose_protective_action."""

from __future__ import annotations

from checktrader.position_management.engine import ProtectiveDecision, choose_protective_action

__all__ = ["ProtectiveDecision", "choose_protective_action"]
