# Testing

Testing should cover configuration, deterministic Python behavior, bridge file shape, and operator scripts before live use.

## Python tests

Run:

```powershell
.\scripts\run_tests.ps1
```

Or directly:

```powershell
python -m pytest
python -m ruff check src tools
python -m mypy src/checktrader
```

## Configuration validation

```powershell
python .\tools\validate_config.py --config config\system.example.json
```

Validation checks JSON syntax, JSON Schema when available, pydantic model constraints, and runtime safety checks.

## MT4 compile check

After deployment:

1. Open MetaEditor.
2. Compile `Experts/CHECK_SYSTEM_V3.mq4`.
3. Confirm includes resolve from `MQL4\Include`.
4. Resolve any compiler messages before attaching to a chart.

## Bridge smoke test

1. Attach the EA to an M1 chart.
2. Enable DLL imports.
3. Confirm chart comment shows the bridge root.
4. Confirm files appear under:

```text
runtime\bridge\market
runtime\bridge\status
```

5. Run:

```powershell
python .\tools\inspect_bridge.py --bridge <bridge-path>\runtime\bridge
```

## Command dry run

Use a demo account before live. Place a small command file under `commands`, then verify:

- MT4 consumes the command file.
- An ACK appears under `acknowledgements`.
- A processed marker appears under `archive`.
- The command file is moved to archive.

## Replay

`tools/replay_market.py` is a minimal support utility that loads a history JSON file and reports available bars. It is intended for inspection and future replay harnesses, not strategy changes.

```powershell
python .\tools\replay_market.py --history runtime\history\history.json
```

## Audit inspection

```powershell
python .\tools\explain_signal.py --audit runtime\audit.jsonl
python .\tools\export_audit.py --audit runtime\audit.jsonl --out runtime\audit_export.json
```

## Live readiness

Before live:

- Demo test the same broker and symbol.
- Confirm spread/stop/freeze levels are reflected in market files.
- Confirm risk blocks behave as expected.
- Confirm MT4 ACKs reflect broker rejections.
- Confirm operator stop procedure works.
