# Patch notes - 2026-07-09

Fixed:
- `mql4/Include/SYSTEM_RootConfig.mqh`: restored root path to `C:\\SYSTEM`.
- `engine/protocol/models.py`: `AIConfig.fail_closed` now requires a real boolean via `_require_bool` instead of coercing strings with `bool(...)`.
- `engine/execution/engine.py`: OPEN ack trade-journal price now uses the resolved entry price instead of stop loss.
- `mql4/Include/SYSTEM_Control.mqh`: JSON string field extraction now handles escaped quotes/backslashes and checks bounds before reading.
- `tools/validate_live.py` and `tools/validate_order_command.py`: direct script execution now adds the SYSTEM root to `sys.path`.
- `tests/execution/test_engine.py`: updated the journal price assertion to match the corrected entry-price behavior.

Cleaned:
- Removed bundled `.venv`.
- Removed `.git` from the delivery package.
- Removed generated Python caches and common test-result artifacts.

Validation run before cleanup:
- `PYTHONPATH=. python3 -m pytest tests/mql4 -q` => 173 passed.
- Targeted Python suite covering protocol/execution/tools/root path => 109 passed.
- Larger core/analysis/decision/risk/execution/journal/protocol/tools suite reported 596 passed before the command timeout wrapper cut off after completion output.
