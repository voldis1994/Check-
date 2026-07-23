# CHECK Platform v4

One EXE. New files. New MQ4. M1 only · trend + breakout.

## Run

1. Double-click `START.bat` (or build `CHECK.exe` with `BUILD_EXE.bat`)
2. **Settings** → set lot / SL / BE / trail / path to `terminal.exe` → Save
3. **Accounts** → Add (login, password, server) → Launch MT4
4. In MT4: compile `mt4/CHECK.mq4`, attach to **M1**, set `BridgePath` from `BRIDGE.txt`
5. **START LIVE**

## Layout

```
Platform/
  START.bat / BUILD_EXE.bat / CHECK.spec
  app/          Python engine + UI (EXE)
  mt4/CHECK.mq4 brand-new EA
  config/       defaults
  clients/      per-account folders (auto)
  runtime/      engine state / audit
```
