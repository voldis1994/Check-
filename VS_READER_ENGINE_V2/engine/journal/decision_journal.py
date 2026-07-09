from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from engine.core.clock import now_utc
from engine.core.instance import Instance
from engine.core.paths import SystemPaths
from engine.protocol.constants import RiskResult
from engine.protocol.errors import DataIOError
from engine.protocol.models import DecisionJournalEntry
from engine.protocol.writer import write_decision_journal_entry

if TYPE_CHECKING:
    from engine.ai_decision_layer import AIDecisionMeta
    from engine.decision.engine import DecisionResult
    from engine.risk.engine import RiskEngineResult

MODULE_NAME = "journal.decision_journal"


def build_decision_journal_path(paths: SystemPaths, instance: Instance) -> Path:
    return paths.account_journal_dir(instance.account_id) / instance.decision_journal_filename()


def build_decision_journal_entry(
    instance: Instance,
    decision_result: DecisionResult,
    risk_engine_result: RiskEngineResult,
    *,
    timestamp_utc: str,
    ai_meta: AIDecisionMeta | None = None,
) -> DecisionJournalEntry:
    risk_reason: str | None = None
    if risk_engine_result.result == RiskResult.BLOCK.value:
        reason = risk_engine_result.reason.strip()
        risk_reason = reason or None

    return DecisionJournalEntry(
        decision_id=decision_result.decision_id,
        timestamp_utc=timestamp_utc,
        account_id=instance.account_id,
        symbol=instance.symbol,
        magic=instance.magic,
        decision=decision_result.decision,
        reason=decision_result.reason,
        buy_score=decision_result.buy_score,
        sell_score=decision_result.sell_score,
        risk_result=risk_engine_result.result,
        risk_reason=risk_reason,
        ai_mode=ai_meta.ai_mode if ai_meta is not None else None,
        ai_available=ai_meta.ai_available if ai_meta is not None else None,
        ai_error_type=ai_meta.ai_error_type if ai_meta is not None else None,
        ai_fallback_used=ai_meta.ai_fallback_used if ai_meta is not None else None,
        ai_reason=ai_meta.ai_reason if ai_meta is not None else None,
        system_decision_before_ai=ai_meta.system_decision_before_ai if ai_meta is not None else None,
        decision_after_ai=ai_meta.decision_after_ai if ai_meta is not None else None,
    )


def append_decision_journal_entry(
    paths: SystemPaths,
    instance: Instance,
    entry: DecisionJournalEntry,
) -> None:
    journal_path = build_decision_journal_path(paths, instance)
    paths.ensure_account_directories(instance.account_id)
    line = write_decision_journal_entry(entry)
    suffix = "" if line.endswith("\n") else "\n"
    try:
        with journal_path.open("a", encoding="utf-8") as handle:
            handle.write(f"{line}{suffix}")
            handle.flush()
            os.fsync(handle.fileno())
    except OSError as exc:
        raise DataIOError(
            "failed to append decision journal entry",
            module=MODULE_NAME,
            context={"path": str(journal_path), "error": str(exc)},
        ) from exc


def log_decision(
    paths: SystemPaths,
    instance: Instance,
    decision_result: DecisionResult,
    risk_engine_result: RiskEngineResult,
    *,
    timestamp_utc: str | None = None,
    ai_meta: AIDecisionMeta | None = None,
) -> DecisionJournalEntry:
    entry = build_decision_journal_entry(
        instance,
        decision_result,
        risk_engine_result,
        timestamp_utc=timestamp_utc or now_utc(),
        ai_meta=ai_meta,
    )
    append_decision_journal_entry(paths, instance, entry)
    return entry
