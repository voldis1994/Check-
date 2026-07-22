# CHECK SYSTEM v3 MT4 Bridge

`Experts/CHECK_SYSTEM_V3.mq4` is an MT4 transport bridge. It does not contain strategy decisions. It exports market/status JSON and executes command JSON created by the external CHECK SYSTEM v3 Python process.

## Install

Copy:

- `mt4/Experts/CHECK_SYSTEM_V3.mq4` to `<TerminalDataPath>/MQL4/Experts/`
- `mt4/Include/CHECK_V3_*.mqh` to `<TerminalDataPath>/MQL4/Include/`

Then restart MetaTrader 4 or refresh Navigator, compile the EA, and attach it to an M1 chart for the traded symbol.

## Required MT4 settings

- Attach the EA to an M1 chart. Initialization fails on any other timeframe.
- Enable AutoTrading if live order execution is required.
- Enable **Allow DLL imports** on the EA settings tab. The bridge imports `kernel32.dll` functions (`CreateDirectoryW`, `GetFileAttributesW`, `MoveFileExW`) to create absolute bridge paths and atomically replace JSON files.
- Confirm the EA input `MagicNumber` matches the Python configuration for the account.

## BridgeRootPath

`BridgeRootPath` defaults to an empty string. Empty means AUTO:

```text
TerminalDataPath\MQL4\Files\CHECK_SYSTEM
```

The EA creates this layout:

```text
runtime\bridge\
  market\
  status\
  commands\
  acknowledgements\
  archive\
```

Use a non-empty `BridgeRootPath` only when the Python process and MT4 terminal share another absolute path.

## Multi-account operation

Run one MT4 terminal instance per broker account. Each terminal has a distinct `TerminalDataPath`, so the default AUTO path naturally separates accounts. For shared roots, use a different `BridgeRootPath` per account or configure the Python process to read each account-specific bridge.

The EA writes account and symbol identifiers into MARKET, STATUS, ACK, and archive files. Commands are idempotent by `command_id`; processed command markers are written under `archive`.
