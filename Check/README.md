# CHECK v5 — from zero

One bat. Your MT4 template. New EXE. No ATR.

## 1. Put original MT4 here

```
Check\template\MetaTrader 4\terminal.exe
```

## 2. Run one file

```
Check\SETUP.bat
```

That syncs MT4 → installs EA → opens the desk.

## 3. Trade

1. **ACCOUNTS** → add login / password / server  
2. Set **SL / BE / TRAIL in POINTS for that account only**  
3. **LAUNCH** → attach **CHECK** on **M1** (`BridgePath` empty) → AutoTrading  
4. **START LIVE**

Strategies: M1 **trend** + **breakout** only.  
Stops are **your numbers per account** — not ATR.
