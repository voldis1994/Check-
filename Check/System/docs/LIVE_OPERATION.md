# Live Operation

Live operation requires explicit operator control. The system provides automation, but it does not remove market, broker, platform, or configuration risk.

## Pre-flight checklist

1. Use Python 3.12 or newer.
2. Run `scripts/setup.ps1`.
3. Validate configuration with `tools/validate_config.py`.
4. Deploy MT4 files with `scripts/deploy_mt4.ps1`.
5. Attach `CHECK_SYSTEM_V3` to an M1 chart for the configured symbol.
6. Enable **Allow DLL imports** for the EA.
7. Confirm the EA chart comment shows the expected bridge path.
8. Confirm MARKET and STATUS files are updating.
9. Confirm the configured magic number matches the EA input.
10. Test in demo before real capital.

## Paper run

```powershell
.\scripts\start_paper.ps1
```

Paper mode is for exercising the Python engine and audit flow. It is not evidence of future live results.

## Live run

Live mode requires:

- `runtime.mode = "live"`
- `runtime.trading_enabled = true`
- MT4 AutoTrading enabled
- EA DLL imports enabled
- A healthy bridge

Start:

```powershell
.\scripts\start_live.ps1 -ConfirmLive
```

## Stop

Create the stop sentinel:

```powershell
.\scripts\stop.ps1
```

Operators should also disable AutoTrading in MT4 for live stops.

## Monitoring

Use:

```powershell
.\scripts\health.ps1
python .\tools\inspect_bridge.py --bridge runtime\bridge
python .\tools\explain_signal.py --audit runtime\audit.jsonl
```

Also monitor:

- MT4 Experts tab
- MT4 Journal tab
- `runtime/audit.jsonl`
- ACK files under `runtime/bridge/acknowledgements`
- Archive files under `runtime/bridge/archive`

## Multi-account

Run one MT4 terminal per account. The default bridge root is terminal-specific, so AUTO paths separate accounts. If using a shared path, configure each account with a distinct `BridgeRootPath` and configure the Python process for the matching bridge.

## Incident response

If behavior is unexpected:

1. Disable AutoTrading in MT4.
2. Run `scripts/stop.ps1`.
3. Preserve `runtime/`, MT4 logs, ACK files, and command archives.
4. Inspect the latest audit entry and ACK rejection messages.
5. Resume only after the root cause is understood.
