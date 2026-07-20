# SYSTEM v1.1.1

Hotfix (2026-07-20): iesprūduša `execution_outcome_unresolved` labojums.

## Hotfix
- Ja ACK timeout atstāj `pending_execution_command_id` un broker Trade ir tukšs >60s, pending tiek notīrīts
- Vairs nebloķē jaunus OPEN ar `execution_outcome_unresolved` mūžīgi
- `ENTRY_DEFERRED` uz tā paša M1 bara ir normāli (`execute_entries_on_closed_bar_only`)

## Deploy

```bat
cd C:\Check\System
git pull
UZSTADIT.bat
FIX_MT4.bat
```

MetaEditor → `SYSTEM_EA.mq4` → **F7** → attach → `PALAID.bat`

Ja pēc pull joprojām redzi veco pending: apturi Python (`Ctrl+C`), izdzēs `data/clients/<account>/state/*_instance_state.json` pending laukus vai restartē `PALAID.bat` — pēc 60s flat reconcile notīrīs automātiski.

---

# SYSTEM v1.1.0

Pilna live versija (2026-07-20). Python M1 engine + MT4 EA.

## Kas iekšā

### Izpilde / sync
- Fiksēts lots (`risk.fixed_lot_volume`), bez %-of-equity sizing
- Bez fiksēta Take Profit (`use_fixed_take_profit: false`)
- Ghost `open_ticket` tīrīšana, kad MT4 Trade ir tukšs (vairs nebloķē ar `RISK_MAX_POSITIONS`)
- Strict pending OPEN identity (OrderComment, volume, open time, preexisting tickets)
- `ALREADY_PROCESSED` / nav SUCCESS ar ticket 0
- Closed-trade eksportā side/volume; reconciliation izmanto broker vērtības

### Trailing
- Tehniskais trailing (structure + `trailing_step_pips`)
- Money-step trailing (config); ar `0.0` vērtībām **nestrādā**, līdz iestati derīgus skaitļus

### Dati
- Market CSV: auto-sanitize (dedupe + sort), ja `time_utc` nav secīgs → vairs nav `SKIP market_invalid`
- Sensor CSV: sanitize + truncate
- Sensor/status ~500 ms; market uz jaunu M1 bari

### Entry
- `block_ranging_chase_entries: false` (ranging chase vairs netur abus virzienus ciet visu dienu)
- BUY/SELL score / indikatoru formulas nemainītas

## Config piezīmes

- `analysis.block_ranging_chase_entries` — `false` live
- `trade_management.money_step_trailing` — iestati `activation_profit_money` u.c. `> 0`, lai ieslēgtu naudas soļus
- Multi-account: auto-discover no `data/clients/*/market_*.csv`
