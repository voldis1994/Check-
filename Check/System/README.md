# Check System (M1)

Python + MT4 live trading system. **Versija 1.1.0.**

## Kas ir iekšā (v1.1.0)

- M1 entry (BUY/SELL scores, closed-bar gate, optional ranging chase)
- Universal trailing (AI + money-step) ar `use_fixed_take_profit` atbalstu
- Ghost / stale open-ticket aizsardzība
- Market CSV un sensor CSV sanitizācija (time_utc)
- Risk no live broker status, ACK timeout identity
- Closed-trade side/volume no MT4 Trade

## Windows (MT4 + Python)

```bat
cd Check\System\scripts\windows
FIX_MT4.bat
PALAID.bat
```

Pēc EA atjaunināšanas: MetaEditor → `SYSTEM_EA.mq4` → Compile (F7).

## Config

`config/system.json` — konts, magic, lot, trailing, filtri.

## Tests

```bash
cd Check/System
python -m pytest -q
```

## Dokumentācija

- [RELEASE_NOTES.md](RELEASE_NOTES.md) — v1.1.0 izmaiņas
- [docs/PATH_CONTRACT.md](docs/PATH_CONTRACT.md)
- [docs/WINDOWS_LIVE.md](docs/WINDOWS_LIVE.md)
