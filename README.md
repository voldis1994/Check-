# Check

Production trading system: [`Check/System`](Check/System)

## SYSTEM v3.0.0 (current)

Full rebuild: Python 3.12+ + MetaTrader 4 file bridge (protocol 3.0.0).

| Item | Path / command |
|------|----------------|
| Engine | `python -m checktrader --config config/local/system.json` |
| EA | `Check/System/mt4/Experts/CHECK_SYSTEM_V3.mq4` |
| Docs | `Check/System/README.md` |
| Release notes | `Check/System/CHANGELOG.md` |

v2 backup: git branch `backup/system-v2-before-v3-rebuild`, tag `system-v2-final-backup`.

Defaults: paper mode, `trading_enabled=false`, fixed lot `0.01`, `instrument.symbol=AUTO`.

```powershell
cd Check\System
py -3.12 -m pip install -e ".[dev]"
copy config\system.example.json config\local\system.json
.\scripts\setup.ps1
.\scripts\start_paper.ps1
# Live (requires mode=live AND trading_enabled=true):
.\scripts\deploy_mt4.ps1
.\scripts\start_live.ps1
```

Technical operability is not a profit guarantee.
