# CHECK

Complete trading platform (v4). Old `Check/System` removed.

## Start (Windows)

```
Check\Platform\START.bat
```

Or build one EXE:

```
Check\Platform\BUILD_EXE.bat
→ dist\CHECK\CHECK.exe
```

## One flow

1. **SETTINGS** → set `terminal.exe` path → Save  
2. **ACCOUNTS** → Add (login / password / server) — DEPLOY runs automatically  
3. **LAUNCH MT4** → Navigator → **CHECK** onto **M1** → AutoTrading ON  
   (`BridgePath` = empty)  
4. FLOOR shows fresh MARKET → **START LIVE**

**PAPER** = signals only, no broker orders.

Strategies: **trend** + **breakout** only · all on **M1** · SL/BE/trail = ATR × settings.
