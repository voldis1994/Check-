# CHECK SYSTEM v3.0.0

CHECK SYSTEM v3 is a rebuild of the CHECK trading system around a deterministic Python engine and an MT4 file bridge. MT4 only exports broker data and applies commands; strategy, regime, risk, and trade-management decisions live outside MT4.

There is no profit guarantee. Trading can lose money, including in live mode.

## Layout

- `src/checktrader/` - Python engine.
- `config/system.example.json` - v3 example configuration.
- `mt4/` - MT4 Expert Advisor and include files.
- `scripts/` - Windows PowerShell setup and operation helpers.
- `tools/` - inspection, validation, replay, and audit utilities.
- `runtime/` - local runtime state, history, audit, bridge data, and stop files.

## Paper mode

```powershell
.\scripts\setup.ps1
.\scripts\start_paper.ps1
```

Paper mode can run from saved/runtime history without sending live orders. It is still a software simulation and should be validated against broker data before live use.

## Live mode

Live mode requires MT4, AutoTrading, DLL imports, a configured bridge, and explicit configuration with `runtime.mode = "live"` and `runtime.trading_enabled = true`.

```powershell
.\scripts\deploy_mt4.ps1
.\scripts\start_live.ps1 -ConfirmLive
```

Use `scripts/stop.ps1` to create `runtime/STOP_TRADING`. Operators should also disable AutoTrading in MT4 when stopping live execution.

## Windows MT4 setup

1. Install Python 3.12 or newer.
2. From this directory, run `.\scripts\setup.ps1`.
3. Run `.\scripts\deploy_mt4.ps1` **or double-click `DEPLOY_MT4.bat`**.
   This copies `CHECK_SYSTEM_V3.mq4` **and all four `CHECK_V3_*.mqh` files** into every terminal:
   - `MQL4\Experts\` (EA + includes side-by-side)
   - `MQL4\Include\`
4. In MetaEditor open the EA from **Data Folder → MQL4\Experts\CHECK_SYSTEM_V3.mq4** (not only from the git repo).
5. Compile with **F7** — must be **0 errors**.
6. Attach to an **M1** chart.
7. Enable **Allow DLL imports**.
8. Leave `BridgeRootPath` empty (AUTO).
9. Enable AutoTrading only when ready for live.

The default MT4 `BridgeRootPath` is empty, which resolves automatically to:

```text
TerminalDataPath\MQL4\Files\CHECK_SYSTEM
```

## Safety notes

- The system uses protocol version `3.0.0`.
- The MT4 EA contains no strategy decisions.
- Validate configuration before live use with `tools/validate_config.py`.
- Use broker demo accounts before real capital.
- Monitor ACK files, audit logs, and MT4 Journal/Experts tabs during operation.
