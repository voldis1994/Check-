# Check

Production trading system: [`Check/System`](Check/System)

## SYSTEM v2.0.0 (current)

Python 3.12+ + MetaTrader 4 file bridge.

| Item | Path / command |
|------|----------------|
| Engine | `python -m checktrader --config config/local/system.json` |
| EA | `Check/System/mt4/Experts/CHECK_SYSTEM_V2.mq4` |
| Docs | `Check/System/README.md` |
| Release notes | `Check/System/CHANGELOG.md` |

Defaults: fixed lot `0.01`, `instrument.symbol = AUTO` (follows MT4 chart), ATR/tick distances for any MT4 instrument.

```powershell
cd Check\System
py -3.12 -m pip install -e ".[dev]"
copy config\system.example.json config\local\system.json
# edit allowed_account_numbers, paths.root, magic
py -3.12 -m checktrader --config config\local\system.json
```

Technical operability is not a profit guarantee.
