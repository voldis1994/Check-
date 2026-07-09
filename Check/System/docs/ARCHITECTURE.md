# SYSTEM — Arhitektūras kopsavilkums

Šis dokuments ir gala arhitektūras kopsavilkums SYSTEM LIVE platformai pēc P74 implementācijas.

## 1. Mērķis un robežas

| Komponents | Atbildība |
|------------|-----------|
| **Python (`engine/`)** | Datu ielāde, validācija, analīze, lēmumi, risks, execution, state, journal |
| **MT4 (`mql4/`)** | M1 datu eksports, control lasīšana, orderu izpilde, ACK |
| **Dashboard (`dashboard.py`)** | Read-only stāvokļa attēlošana |

Python pieņem visus tirdzniecības lēmumus. MT4 nekad neanalizē tirgu un neizvēlas BUY/SELL/WAIT/BLOCK.

## 2. Fiziskā struktūra

```
SYSTEM/
├── config/system.json          Vienīgā konfigurācija
├── data/
│   ├── clients/{account_id}/   MT4 ↔ Python failu apmaiņa
│   ├── logs/                   Sistēmas logi
│   ├── cache/                  Cache
│   ├── history/                Vēsture
│   └── universe/               Globālais universe konteksts
├── engine/                     Python biznesa loģika
├── mql4/                       MT4 EA un Include faili
├── tools/validate_live.py      LIVE vides validācija
├── run_live.py                 Live engine entry point
└── dashboard.py                Dashboard entry point
```

## 3. Instance modelis

**Account + Symbol + Magic = viena izolēta instance.**

Katrai instancei ir savi:

- state (`instance_{symbol}_{magic}.json`, `spread_{symbol}_{magic}.json`)
- journal (`decision_`, `trade_`, `error_`)
- control/ack (`control_{symbol}_{magic}.json`, `ack_{symbol}_{magic}.json`)
- risk un spread modelis atmiņā

Instances nedalās žurnālos, state vai control komandās.

## 4. Moduļu slāņi

```
core → protocol
loader → validator → normalizer → state
analysis → decision → risk
journal, execution
dashboard (tikai lasa state/journal/log)
```

Augstāki slāņi neapiet validāciju un analīzi. Dashboard neimportē `analysis`, `decision` vai `risk`.

## 5. Datu plūsma

### Ienākošā (MT4 → Python)

1. EA eksportē `market`, `sensor`, `status`, `universe`
2. Loader ielādē failus
3. Validator validē
4. Normalizer normalizē un atjaunina spread modeli
5. State atjaunina instance atmiņu

### Lēmumu plūsma

1. Analysis Engine ražo kontekstu
2. Decision Engine aprēķina BUY un SELL kandidātus
3. Scorer salīdzina virzienus
4. Risk Engine atgriež ALLOW vai BLOCK
5. Decision Journal pieraksta lēmumu ar reason

### Izejošā (Python → MT4)

1. Execution ģenerē Order Command
2. Control Writer raksta control JSON
3. EA izpilda orderu un raksta ACK
4. ACK Reader apstrādā ACK, trade journal un state tiek atjaunināti

## 6. Orchestrācija un novērošana

| Modulis | Loma |
|---------|------|
| `core/lifecycle.py` | Startup/shutdown, memory, spread modeli |
| `core/orchestrator.py` | Multi-instance cikli |
| `core/recovery.py` | Startup recovery, late ACK, pozīciju sinhronizācija ar status |
| `core/position_sync.py` | Status `open_positions` ↔ instance state, ārējā aizvēršana |
| `core/history.py` | Control/ACK/market arhivēšana uz `data/history/` |
| `journal/rotation.py` | Journal rotācija pēc `journal.retention_days` |
| `core/monitoring.py` | Instance monitoring |
| `core/alerts.py` | Alerti |
| `core/performance.py` | Cikla ilguma metrikas |

## 7. Testēšanas slāņi

| Slānis | Mērķis |
|--------|--------|
| `tests/` unit | Moduļu pareizība |
| `tests/integration/` | Datu, lēmumu un execution ķēdes |
| `tests/e2e/` | Pilns cikls ar MT4 simulatoru |
| `tests/performance/` | `cycle_max_duration_ms` un atmiņa |
| `tools/validate_live.py` | LIVE vides validācija |

## 8. Normatīvie avoti

- `docs/RULES.md` — obligātie noteikumi
- `docs/SYSTEM_SPECIFICATION.md` — pilna tehniskā specifikācija
- `docs/PROTOCOL.md` — failu protokola kopsavilkums

Pretrunā starp implementāciju un `docs/RULES.md` pareizi ir noteikumi.
