# CHECK

Clean trading platform (v4). Old `Check/System` removed.

## Start

```
Check/Platform/START.bat
```

Or build one EXE:

```
Check/Platform/BUILD_EXE.bat
→ dist/CHECK/CHECK.exe
```

## Flow

1. Settings → lot / SL / BE / trail / `terminal.exe` path → Save  
2. Accounts → Add (login, password, server) → Launch MT4  
3. Compile `mt4/CHECK.mq4`, attach to **M1**, set `BridgePath` from client `BRIDGE.txt`  
4. START LIVE  

Strategies: **trend** + **breakout** only · all on **M1**.
