# CHECK Platform v4 — complete trading system

One EXE. New MQ4. M1 trend + breakout. ATR stops.

## Run

```
cd Check\Platform
START.bat
```

Build EXE:

```
BUILD_EXE.bat
→ dist\CHECK\CHECK.exe
```

## Checklist (also shown in the UI)

1. **SETTINGS** → browse `terminal.exe` → Save  
2. **ACCOUNTS** → + ADD ACCOUNT (login / password / server)  
3. **LAUNCH MT4** → attach **CHECK** on **M1**, AutoTrading ON, `BridgePath` empty  
4. When FLOOR shows live MARKET age → **START LIVE**

**PAPER** logs signals without writing OPEN/MODIFY to MT4.

## What the EXE controls

| Setting | Meaning |
|---------|---------|
| LOT | Fixed lot (per-account override on add) |
| SL ATR × | Initial stop = ATR × this |
| BE START / OFFSET | Breakeven |
| TRAIL START / LOCK | Trailing |
| TREND / BREAKOUT | Strategies (M1 only) |
| MT4 terminal.exe | Used by LAUNCH + DEPLOY |

## Layout

```
Platform/
  START.bat / BUILD_EXE.bat / CHECK.spec
  app/          desk UI + engine + bridge
  mt4/CHECK.mq4 M1 bridge EA
  config/       defaults + settings
  clients/      per-account folders + launch bat
  runtime/      audit / STOP
```

Bridge discovery: Python reads `MQL4/Files/CHECK` under MetaQuotes Terminal (and local `clients/*/bridge`).
