# SYSTEM v1.1.2

Hotfix (2026-07-21): trailing + lockpoint.

## Hotfix
- Tehniskais trailing (`trailing_step_pips`) vairs netiek nogalināts, ja money-step nevar rēķināt (nav `tick_value`)
- Lockpoint (`money_step_trailing`) live config: activation `0.50`, step/lock `0.25` (0.01 lot)
- MODIFY trailing vairs netiek bloķēts aiz iesprūduša OPEN control faila
- MODIFY ACK vairs netīra pending OPEN identity

## Deploy

```bat
cd C:\Check\System
git pull
UZSTADIT.bat
FIX_MT4.bat
```

MetaEditor → `SYSTEM_EA.mq4` → **F7** → attach → `PALAID.bat`

Pārbaudi `config\\system.json` → `trade_management.money_step_trailing` vērtības **> 0**.
