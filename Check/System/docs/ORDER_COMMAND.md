# SYSTEM — Order Command kopsavilkums

Šis dokuments ir gala `OrderCommand` protokola kopsavilkums saskaņā ar `docs/SYSTEM_SPECIFICATION.md` 75. sadaļu.

## 1. Modulis

`engine/execution/command.py`

## 2. Objekts

`OrderCommand` satur šādus laukus:

| Lauks | Apraksts |
|-------|----------|
| `command_id` | Unikāls UUID |
| `action` | `OPEN`, `MODIFY`, `CLOSE`, `NONE` |
| `side` | `BUY` vai `SELL` atvēršanai un pozīcijas pārvaldībai |
| `volume` | Lotes apjoms `OPEN` un `CLOSE` komandām |
| `stop_loss` | Stop Loss cena `OPEN` un `MODIFY` komandām |
| `take_profit` | Take Profit cena `OPEN` un `MODIFY` komandām |
| `ticket` | Esošā pozīcijas tickets `MODIFY` un `CLOSE` komandām |
| `reason` | Obligāts lēmuma vai trade management reason |
| `decision_id` | Saite uz decision journal ierakstu |

## 3. Komandu veidošana

| Funkcija | Mērķis |
|----------|--------|
| `build_order_command` | Veido `OPEN` vai `NONE` no `DecisionResult` un `RiskEngineResult` |
| `build_modify_order_command` | Veido `MODIFY` ar ticket, SL un TP |
| `build_close_order_command` | Veido `CLOSE` ar ticket un volume |
| `build_management_order_command` | Pārveido `TradeManagementResult` uz `MODIFY` vai `CLOSE` |
| `resolve_order_command` | Izvēlas trade management komandu, ja tā ir aktīva, citādi lēmuma komandu |

## 4. Action noteikumi

### OPEN

Tiek izveidots, ja lēmums ir `BUY` vai `SELL`, risks atgriež `ALLOW`, un trade parametri ir pieejami.

### MODIFY

Tiek izveidots no trade management loģikas, kad jāmaina esošās pozīcijas SL vai TP. Obligāti lauki: `ticket`, `side`, `stop_loss`, `take_profit`, `reason`, `decision_id`.

### CLOSE

Tiek izveidots no trade management loģikas, kad jāaizver visa vai daļa no pozīcijas. Obligāti lauki: `ticket`, `side`, `volume`, `reason`, `decision_id`.

### NONE

Ja lēmums ir `WAIT` vai `BLOCK`, `action` ir `NONE`. Control fails joprojām tiek rakstīts informācijas sinhronizācijai ar `reason`, bet trade intent netiek izpildīts.

## 5. Izpildes secība

```
DecisionResult + RiskEngineResult
        │
        ├─► build_order_command ──► OPEN / NONE
        │
TradeManagementResult + open position
        │
        ├─► build_management_order_command ──► MODIFY / CLOSE
        │
resolve_order_command
        │
        ▼
control_writer.publish_control
        │
        ▼
MT4 EA izpilde un ACK
```

## 6. Validācija

`tools/validate_order_command.py` pārbauda:

- `OrderCommand` datu struktūru
- `OPEN`, `MODIFY`, `CLOSE`, `NONE` līgumu
- trade management pārveidi uz izpildāmām komandām
- control writer atbalstu visām action vērtībām

## 7. Saistītie dokumenti

- `docs/SYSTEM_SPECIFICATION.md` — 75., 76., 77. sadaļa
- `docs/PROTOCOL.md` — control un ACK protokols
- `engine/execution/control_writer.py` — control serializācija
- `engine/risk/trade_management.py` — MODIFY/CLOSE avots
