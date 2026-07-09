# SYSTEM — Protokola kopsavilkums

Šis dokuments ir gala failu protokola kopsavilkums starp MT4 EA un Python engine.

## 1. Shēmas versijas

| Konteksts | Lauks | Versija |
|-----------|-------|---------|
| Konfigurācija | `schema_version` | `1.0.0` |
| MT4 ↔ Python faili | `schema_version` | `1.0.0` |
| State faili | `schema_version` | `1.0.0` |

Major versijas izmaiņas maina nesaderīgu formātu. Minor versijas pievieno laukus ar atpakaļejošu saderību.

## 2. Timeframe un instance identitāte

- Vienīgais atļautais timeframe: **M1**
- Instance atslēga: `(account_id, symbol, magic)`
- Visi instance specifiskie faili izmanto `{symbol}` un `{magic}` nosaukumā

## 3. MT4 eksporta faili

Katram kontam: `data/clients/{account_id}/`

| Fails | Formāts | Avots |
|-------|---------|-------|
| `market_{symbol}_{magic}.csv` | CSV | EA export |
| `sensor_{symbol}_{magic}.csv` | CSV | EA export |
| `status_{account_id}.json` | JSON | EA export |
| `universe.json` | JSON | EA vai globālais `data/universe/universe.json` |

### Market CSV kolonnas

`time_utc, open, high, low, close, volume, symbol, timeframe, digits, point`

### Sensor CSV kolonnas

`time_utc, bid, ask, spread, spread_points, symbol, digits, point`

### Status JSON obligātie lauki

`schema_version, timestamp_utc, account_id, connected, trade_allowed, balance, equity, margin_free, ea_version`

Opcionāls lauks `open_positions[]` satur visas konta atvērtās pozīcijas (sk. spec §19.2.1).

### Universe JSON

Atļauts tikai konteksts (`session`, `market_regime`, `news_window_active`, u.c.). Aizliegti trade signālu lauki: `signal`, `direction`, `trade`, `buy`, `sell`, `action`.

## 4. Python → MT4 control

| Fails | Formāts |
|-------|---------|
| `control_{symbol}_{magic}.json` | JSON |

Galvenie lauki: `command_id`, `account_id`, `symbol`, `magic`, `action`, `reason`, `decision_id`, `side`, `volume`, `stop_loss`, `take_profit`, `ticket`.

`action` vērtības: `OPEN`, `MODIFY`, `CLOSE`, `NONE`.

## 5. MT4 → Python ACK

| Fails | Formāts |
|-------|---------|
| `ack_{symbol}_{magic}.json` | JSON |

Galvenie lauki: `command_id`, `account_id`, `symbol`, `magic`, `status`, `ticket`, `error_code`, `error_message`.

`status` vērtības ārējā ACK JSON failā: `SUCCESS`, `FAILED`, `REJECTED`.

`TIMEOUT` **nav** atļauta vērtība MT4 → Python ACK JSON (`is_valid_ack_status`). Timeout tiek interpretēts iekšēji (`InstanceState.last_ack_status`, trade journal `reason`), ja ACK fails neparādās noteiktā laikā.

## 6. State faili

Katrai instancei: `data/clients/{account_id}/state/`

| Fails | Saturs |
|-------|--------|
| `instance_{symbol}_{magic}.json` | Pēdējais lēmums, pozīcija, instrumenta parametri |
| `spread_{symbol}_{magic}.json` | Spread modeļa statistika |
| `monitoring_{symbol}_{magic}.json` | Pēdējās monitoring metrikas dashboard attēlošanai |

## 7. Journal faili (JSONL)

Katrai instancei: `data/clients/{account_id}/journal/`

| Fails | Notikums |
|-------|----------|
| `decision_{symbol}_{magic}.jsonl` | Katrs lēmums ar reason un risk rezultātu |
| `trade_{symbol}_{magic}.jsonl` | Trade intent un ACK |
| `error_{symbol}_{magic}.jsonl` | Validācijas, IO, execution un risk kļūdas |

Journal ir append-only. Katram ierakstam ir `timestamp_utc` un instance identifikatori.

Trade journal intent rindas pirms ACK izmanto `ack_status=REJECTED` kā pagaidu stāvokli; pēc ACK ieraksts tiek atjaunināts ar faktisko `SUCCESS`, `FAILED` vai `TIMEOUT` interpretāciju.

## 8. Lēmumu un riska protokols

| Lēmums | Nozīme |
|--------|--------|
| `BUY` | Izvēlēts pirkšanas virziens pēc scoring un ALLOW |
| `SELL` | Izvēlēts pārdošanas virziens pēc scoring un ALLOW |
| `WAIT` | Neviens virziens nav pieņemams pēc pilnas izvērtēšanas |
| `BLOCK` | Risks vai konta stāvoklis aizliedz trade |

Risk atgriež tikai `ALLOW` vai `BLOCK`. Katram lēmumam un BLOCK ir obligāts `reason`.

## 9. Atomiskā IO

Visi kritiskie faili tiek rakstīti caur atomisko write (`engine/core/atomic_io.py`):

1. Raksta uz temp failu
2. `fsync`
3. Atomic rename/replace

## 10. Validācijas secība

```
load → validate → normalize → analyze → decide → risk → journal → execute → ack → state
```

Nederīgi dati aptur plūsmu, pieraksta `error_journal` un neizraisa trade.

## 11. Saistītie dokumenti

- `docs/SYSTEM_SPECIFICATION.md` — pilna protokola specifikācija (17.–21. sadaļa)
- `docs/RULES.md` — obligātie noteikumi
- `engine/protocol/` — parser, writer, modeļi
