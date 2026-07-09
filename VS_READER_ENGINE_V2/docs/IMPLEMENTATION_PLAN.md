# SYSTEM — Implementācijas plāns

**Versija:** 1.0  
**Statuss:** Obligāts izstrādes avots  
**Avots:** `docs/SYSTEM_SPECIFICATION.md`, `docs/RULES.md`

Šis dokuments ir SYSTEM projekta vienīgais izstrādes plāns. Katrs posms ir pilnībā pabeidzams un testējams pirms nākamā posma sākšanas. Posmi ir sakārtoti tā, lai viss projekts tiktu uzbūvēts secīgi bez patch pieejas, bez pusgataviem moduļiem un bez atgriešanās, lai labotu iepriekšējo posmu pamatus.

**Posma formāts:**

| Lauks | Nozīme |
|-------|--------|
| **Rezultāts** | Konkrēts, pārbaudāms iznākums |
| **Atkarības** | Posmi, kas jābūt pabeigtiem |
| **Faili** | Faili, kas tiek izveidoti vai pilnībā implementēti |
| **Moduļi** | Moduļi, kas šajā posmā kļūst pilnībā gatavi |
| **Testi** | Testi, kas obligāti jāiziet |
| **Aizliegts pirms pabeigšanas** | Posmi, kas nedrīkst sākties |

---

## Posmu kopsavilkums

| Posms | Nosaukums |
|-------|-----------|
| P01 | Projekta pamats un atkarības |
| P02 | Protokola konstantes un kļūdas |
| P03 | Protokola datu modeļi |
| P04 | Protokola parseris |
| P05 | Protokola writer |
| P06 | Core ceļi un mapju inicializācija |
| P07 | Core pulkstenis |
| P08 | Core instance identitāte |
| P09 | Core konfigurācijas ielāde un validācija |
| P10 | Konfigurācijas fails `system.json` |
| P11 | Atomic I/O utilītas |
| P12 | Logging infrastruktūra |
| P13 | Market Loader |
| P14 | Sensor Loader |
| P15 | Status Loader |
| P16 | Universe Loader |
| P17 | Market Validator |
| P18 | Sensor Validator |
| P19 | Status Validator |
| P20 | Universe Validator |
| P21 | Market Normalizer |
| P22 | Instrumentu parametru noteikšana |
| P23 | Spread Model |
| P24 | Spread State |
| P25 | Instance State |
| P26 | Instance Memory |
| P27 | Cache sistēma |
| P28 | Error Journal |
| P29 | Context analīze |
| P30 | Structure analīze |
| P31 | Momentum un Trend analīze |
| P32 | Pressure analīze |
| P33 | Behavior analīze |
| P34 | Impact analīze |
| P35 | Analysis Engine orķestrācija |
| P36 | Reason modulis |
| P37 | Spread filtrs |
| P38 | Volatility filtrs |
| P39 | News filtrs |
| P40 | BUY aprēķins |
| P41 | SELL aprēķins |
| P42 | Scoring sistēma |
| P43 | WAIT un BLOCK loģika |
| P44 | Decision Engine |
| P45 | Risk Rules |
| P46 | Position Sizing |
| P47 | Stop Loss un Take Profit validācija |
| P48 | Risk Engine |
| P49 | Trade Management |
| P50 | Decision Journal |
| P51 | Trade Journal |
| P52 | Order Command |
| P53 | Control Writer |
| P54 | ACK Reader |
| P55 | Retry un Timeout |
| P56 | Execution Engine integrācija |
| P57 | MT4 EA — eksporta infrastruktūra |
| P58 | MT4 EA — market un sensor eksports |
| P59 | MT4 EA — status un universe eksports |
| P60 | MT4 EA — control lasīšana |
| P61 | MT4 EA — orderu izpilde un ACK |
| P62 | `run_live.py` — startup un shutdown |
| P63 | `run_live.py` — vienas instances cikls |
| P64 | `run_live.py` — multi-instance un multi-account |
| P65 | Recovery un Error Recovery |
| P66 | Dashboard |
| P67 | Live monitoring un Alert sistēma |
| P68 | Performance monitoring |
| P69 | Integration testi — datu plūsma |
| P70 | Integration testi — lēmumu plūsma |
| P71 | Integration testi — execution plūsma |
| P72 | End-to-End tests |
| P73 | Performance tests |
| P74 | LIVE sistēmas palaišana un validācija |
| P75 | Audita High labojumi un spec atbilstības nostiprināšana |
| P76 | AI decision slānis (advisory/required, OpenAI, journal, E2E) — **pabeigts 2026-07-08** |

---

## P01 — Projekta pamats un atkarības

**Rezultāts:** Projekta sakne ir konfigurēta ar Python vidi, `requirements.txt` satur visas nepieciešamās atkarības, `README.md` satur minimālo operacionālo aprakstu projekta palaišanai.

**Atkarības:** Nav.

**Faili:**
- `requirements.txt`
- `README.md`

**Moduļi:** Nav koda moduļu.

**Testi:**
- `pip install -r requirements.txt` izpildās bez kļūdām
- Python versija atbilst specifikācijas prasībai

**Aizliegts pirms pabeigšanas:** Visi P02–P74.

---

## P02 — Protokola konstantes un kļūdas

**Rezultāts:** Visas protokola konstantes, shēmu versijas, lēmumu tipi, reason kodi un exception hierarhija ir definēti un eksportējami.

**Atkarības:** P01.

**Faili:**
- `engine/protocol/constants.py`
- `engine/protocol/errors.py`
- `engine/protocol/__init__.py`

**Moduļi:** `protocol` — konstantes un kļūdu bāze.

**Testi:**
- `tests/protocol/test_constants.py` — visas konstantes eksistē un atbilst specifikācijai
- `tests/protocol/test_errors.py` — katrs exception tips ir definēts un mantojams

**Aizliegts pirms pabeigšanas:** P03–P74.

---

## P03 — Protokola datu modeļi

**Rezultāts:** Visi iekšējie datu objekti atbilstoši specifikācijas 19. un 20. sadaļai ir definēti kā tipizēti modeļi.

**Atkarības:** P02.

**Faili:**
- `engine/protocol/models.py`

**Moduļi:** `protocol` — datu modeļi.

**Testi:**
- `tests/protocol/test_models.py` — katrs modelis izveidojams ar obligātajiem laukiem
- `tests/protocol/test_models.py` — instance atslēga `(account_id, symbol, magic)` validācija

**Aizliegts pirms pabeigšanas:** P04–P74.

---

## P04 — Protokola parseris

**Rezultāts:** JSON un CSV faili tiek parsēti uz modeļiem. Nederīgs saturs izraisa `ProtocolError`, nevis silent failure.

**Atkarības:** P02, P03.

**Faili:**
- `engine/protocol/parser.py`

**Moduļi:** `protocol` — parseris (pabeigts).

**Testi:**
- `tests/protocol/test_parser.py` — market CSV parsēšana
- `tests/protocol/test_parser.py` — sensor CSV parsēšana
- `tests/protocol/test_parser.py` — status, universe, control, ack JSON parsēšana
- `tests/protocol/test_parser.py` — bojāts fails izraisa `ProtocolError`
- `tests/protocol/test_parser.py` — `schema_version` validācija

**Aizliegts pirms pabeigšanas:** P05, P13–P74.

---

## P05 — Protokola writer

**Rezultāts:** Visi iekšējie objekti tiek serializēti uz JSON un CSV saskaņā ar specifikāciju.

**Atkarības:** P02, P03.

**Faili:**
- `engine/protocol/writer.py`

**Moduļi:** `protocol` — pilnībā pabeigts.

**Testi:**
- `tests/protocol/test_writer.py` — round-trip: modelis → serializācija → parseris → modelis
- `tests/protocol/test_writer.py` — JSONL journal rindas formāts
- `tests/protocol/test_writer.py` — visi obligātie lauki ir klāt izvadē

**Aizliegts pirms pabeigšanas:** P06–P74, izņemot P06 var sākt paralēli pēc P03.

---

## P06 — Core ceļi un mapju inicializācija

**Rezultāts:** Sistēma dinamiski atrisina visus ceļus zem `C:\SYSTEM` un izveido trūkstošās mapes startup laikā.

**Atkarības:** P02.

**Faili:**
- `engine/core/paths.py`
- `engine/core/__init__.py`

**Moduļi:** `core/paths` — pabeigts.

**Testi:**
- `tests/core/test_paths.py` — visi specifikācijas ceļi tiek atrisināti
- `tests/core/test_paths.py` — `ensure_directories()` izveido pilnu `data/` hierarhiju
- `tests/core/test_paths.py` — instance ceļi: journal, state, cache

**Aizliegts pirms pabeigšanas:** P09, P13–P74.

---

## P07 — Core pulkstenis

**Rezultāts:** Vienots UTC laika avots visai sistēmai ar deterministisku testējamu saskarni.

**Atkarības:** P02.

**Faili:**
- `engine/core/clock.py`

**Moduļi:** `core/clock` — pabeigts.

**Testi:**
- `tests/core/test_clock.py` — `now_utc()` atgriež UTC
- `tests/core/test_clock.py` — ISO 8601 formāts ar milisekundēm

**Aizliegts pirms pabeigšanas:** P28, P50–P51, P62–P74.

---

## P08 — Core instance identitāte

**Rezultāts:** `Instance` objekts ar `(account_id, symbol, magic)` atslēgu, vienādības pārbaudi un failu nosaukumu ģenerēšanu.

**Atkarības:** P02, P06.

**Faili:**
- `engine/core/instance.py`

**Moduļi:** `core/instance` — pabeigts.

**Testi:**
- `tests/core/test_instance.py` — unikāla atslēga
- `tests/core/test_instance.py` — failu nosaukumu ģenerēšana atbilst 21. sadaļai
- `tests/core/test_instance.py` — dublikāta atslēga konstatēšana

**Aizliegts pirms pabeigšanas:** P25–P27, P50–P51, P56, P63–P74.

---

## P09 — Core konfigurācijas ielāde un validācija

**Rezultāts:** `system.json` tiek ielādēts, validēts pret shēmu, noraida aizliegtos laukus un nodrošina tipu pareizību.

**Atkarības:** P02, P03, P06.

**Faili:**
- `engine/core/config.py`

**Moduļi:** `core/config` — pabeigts.

**Testi:**
- `tests/core/test_config.py` — derīga konfigurācija ielādējas
- `tests/core/test_config.py` — trūkstošs obligātais lauks izraisa kļūdu
- `tests/core/test_config.py` — `timeframe` nav M1 → kļūda
- `tests/core/test_config.py` — cieti spread limiti → kļūda
- `tests/core/test_config.py` — cieti symbol saraksti → kļūda

**Aizliegts pirms pabeigšanas:** P10, P62–P74.

---

## P10 — Konfigurācijas fails `system.json`

**Rezultāts:** Pilnīgs, derīgs `config/system.json` ar visiem specifikācijas 19.1 laukiem un sākotnējām instances definīcijām.

**Atkarības:** P09.

**Faili:**
- `config/system.json`

**Moduļi:** Nav jaunu moduļu.

**Testi:**
- `tests/core/test_config.py` — faktiskais `system.json` ielādējas bez kļūdām
- Konfigurācijas `schema_version` atbilst `constants.py`

**Aizliegts pirms pabeigšanas:** P62–P74.

---

## P11 — Atomic I/O utilītas

**Rezultāts:** Atomic write, atomic read un failu stabilitātes pārbaude ir implementēta kā atkārtoti lietojama utilīta.

**Atkarības:** P06.

**Faili:**
- `engine/core/atomic_io.py`

**Moduļi:** `core/atomic_io` — pabeigts.

**Testi:**
- `tests/core/test_atomic_io.py` — rakstīšana caur `.tmp` un rename
- `tests/core/test_atomic_io.py` — lasīšana tikai bez `.tmp`
- `tests/core/test_atomic_io.py` — `fsync` pirms rename
- `tests/core/test_atomic_io.py` — bojāts `.tmp` netiek lasīts

**Aizliegts pirms pabeigšanas:** P13–P16, P28, P50–P54, P57–P61.

---

## P12 — Logging infrastruktūra

**Rezultāts:** Strukturēts logging ar specifikācijas 93. sadaļas formātu un `data/logs/` izvadi.

**Atkarības:** P06, P07, P09.

**Faili:**
- `engine/core/logging_setup.py`

**Moduļi:** `core/logging` — pabeigts.

**Testi:**
- `tests/core/test_logging.py` — log formāts satur timestamp, level, module
- `tests/core/test_logging.py` — log fails tiek izveidots zem `data/logs/`
- `tests/core/test_logging.py` — visi līmeņi darbojas

**Aizliegts pirms pabeigšanas:** P62–P68, P74.

---

## P13 — Market Loader

**Rezultāts:** `market_{symbol}_{magic}.csv` tiek ielādēts no diska ar metadatiem.

**Atkarības:** P04, P06, P08, P11.

**Faili:**
- `engine/loader/market_loader.py`
- `engine/loader/__init__.py`
- `tests/loader/test_market_loader.py`
- `tests/loader/fixtures/market_valid.csv`
- `tests/loader/fixtures/market_missing.csv`

**Moduļi:** `loader/market_loader` — pabeigts.

**Testi:**
- Derīgs CSV ielādējas ar pareizu rindu skaitu
- Trūkstošs fails izraisa `IOError` ar ziņojumu
- Loader nevalidē saturu

**Aizliegts pirms pabeigšanas:** P17, P21, P63–P74.

---

## P14 — Sensor Loader

**Rezultāts:** `sensor_{symbol}_{magic}.csv` tiek ielādēts no diska.

**Atkarības:** P04, P06, P08, P11.

**Faili:**
- `engine/loader/sensor_loader.py`
- `tests/loader/test_sensor_loader.py`
- `tests/loader/fixtures/sensor_valid.csv`

**Moduļi:** `loader/sensor_loader` — pabeigts.

**Testi:**
- Derīgs sensor CSV ielādējas
- Trūkstošs fails izraisa kļūdu
- Loader nevalidē spread konsekvenci

**Aizliegts pirms pabeigšanas:** P18, P23, P63–P74.

---

## P15 — Status Loader

**Rezultāts:** `status_{account_id}.json` tiek ielādēts konta līmenī.

**Atkarības:** P04, P06, P11.

**Faili:**
- `engine/loader/status_loader.py`
- `tests/loader/test_status_loader.py`
- `tests/loader/fixtures/status_valid.json`

**Moduļi:** `loader/status_loader` — pabeigts.

**Testi:**
- Derīgs status JSON ielādējas
- Trūkstošs fails izraisa kļūdu

**Aizliegts pirms pabeigšanas:** P19, P48, P63–P74.

---

## P16 — Universe Loader

**Rezultāts:** `universe.json` tiek ielādēts no konta mapes vai globālā ceļa.

**Atkarības:** P04, P06, P09, P11.

**Faili:**
- `engine/loader/universe_loader.py`
- `tests/loader/test_universe_loader.py`
- `tests/loader/fixtures/universe_valid.json`

**Moduļi:** `loader/universe_loader` — pabeigts. Viss `loader` modulis ir pabeigts.

**Testi:**
- Derīgs universe ielādējas
- Abi ceļu varianti darbojas
- Loader neinterpretē universe kā trade signālu

**Aizliegts pirms pabeigšanas:** P20, P29, P39, P63–P74.

---

## P17 — Market Validator

**Rezultāts:** Market CSV struktūra un OHLC saturs tiek validēts. INVALID rezultāts ar kļūdu sarakstu.

**Atkarības:** P04, P13.

**Faili:**
- `engine/validator/market_validator.py`
- `engine/validator/__init__.py`
- `tests/loader/test_market_validator.py`

**Moduļi:** `validator/market_validator` — pabeigts.

**Testi:**
- Derīgs market → VALID
- Bojāts OHLC → INVALID
- Trūkstoša kolonna → INVALID
- `timeframe` nav M1 → INVALID
- Dublikātu laiki → INVALID

**Aizliegts pirms pabeigšanas:** P21, P63–P74.

---

## P18 — Sensor Validator

**Rezultāts:** Sensor CSV spread konsekvence tiek validēta.

**Atkarības:** P04, P14.

**Faili:**
- `engine/validator/sensor_validator.py`
- `tests/loader/test_sensor_validator.py`

**Moduļi:** `validator/sensor_validator` — pabeigts.

**Testi:**
- `ask >= bid` → VALID
- `spread == ask - bid` → VALID
- Negatīvs spread → INVALID
- `spread_points` neatbilstība → INVALID

**Aizliegts pirms pabeigšanas:** P23, P63–P74.

---

## P19 — Status Validator

**Rezultāts:** Status JSON tiek validēts konta līmenī.

**Atkarības:** P04, P15.

**Faili:**
- `engine/validator/status_validator.py`
- `tests/loader/test_status_validator.py`

**Moduļi:** `validator/status_validator` — pabeigts.

**Testi:**
- Derīgs status → VALID
- `connected: false` → VALID bet atzīmēts kā netradeable
- Trūkstošs `balance` → INVALID
- NaN vērtības → INVALID

**Aizliegts pirms pabeigšanas:** P48, P63–P74.

---

## P20 — Universe Validator

**Rezultāts:** Universe JSON tiek validēts, aizliegtie trade signāla lauki tiek noraidīti.

**Atkarības:** P04, P16.

**Faili:**
- `engine/validator/universe_validator.py`
- `tests/loader/test_universe_validator.py`

**Moduļi:** `validator/universe_validator` — pabeigts. Viss `validator` modulis ir pabeigts.

**Testi:**
- Derīgs universe → VALID
- Lauks `signal` → INVALID
- Lauks `buy` → INVALID
- `market_regime` ārpus atļautā kopa → INVALID

**Aizliegts pirms pabeigšanas:** P29, P39, P63–P74.

---

## P21 — Market Normalizer

**Rezultāts:** Validēti market dati tiek pārveidoti par iekšējiem M1 objektiem ar UTC laikiem un pareizu precizitāti.

**Atkarības:** P03, P17.

**Faili:**
- `engine/normalizer/market_normalizer.py`
- `engine/normalizer/__init__.py`
- `tests/normalizer/test_market_normalizer.py`

**Moduļi:** `normalizer/market_normalizer` — pabeigts.

**Testi:**
- CSV → normalizēti M1 objekti
- Laiki ir UTC
- Cenas saglabā `digits` precizitāti
- `bar_index` piešķirts secīgi

**Aizliegts pirms pabeigšanas:** P22, P35, P63–P74.

---

## P22 — Instrumentu parametru noteikšana

**Rezultāts:** `digits`, `point` un `pip` tiek dinamiski noteikti no MT4 datiem.

**Atkarības:** P21.

**Faili:**
- `engine/normalizer/instrument_params.py`
- `tests/normalizer/test_instrument_params.py`

**Moduļi:** `normalizer/instrument_params` — pabeigts.

**Testi:**
- 5 digits → `pip = point * 10`
- 4 digits → `pip = point`
- Parametru maiņa tiek konstatēta

**Aizliegts pirms pabeigšanas:** P25, P46–P47, P63–P74.

---

## P23 — Spread Model

**Rezultāts:** Dinamiskais spread modelis ar mean, std, median un relative_spread.

**Atkarības:** P03, P18.

**Faili:**
- `engine/normalizer/spread_model.py`
- `tests/normalizer/test_spread_model.py`

**Moduļi:** `normalizer/spread_model` — pabeigts. Viss `normalizer` modulis ir pabeigts.

**Testi:**
- `relative_spread` aprēķins
- Nav cietu limitu
- Vēstures logs ierobežots pēc `lookback_bars`
- Jaunais sensor atjaunina modeli

**Aizliegts pirms pabeigšanas:** P24, P37, P63–P74.

---

## P24 — Spread State

**Rezultāts:** Spread stāvoklis tiek uzturēts atmiņā un persistēts `spread_{symbol}_{magic}.json`.

**Atkarības:** P05, P08, P11, P23.

**Faili:**
- `engine/state/spread_state.py`
- `tests/state/test_spread_state.py`

**Moduļi:** `state/spread_state` — pabeigts.

**Testi:**
- State atjaunināšana no spread modela
- Persistēšana un ielāde no diska
- Instance izolācija

**Aizliegts pirms pabeigšanas:** P26, P63–P74.

---

## P25 — Instance State

**Rezultāts:** Instance operacionālais stāvoklis tiek uzturēts un persistēts.

**Atkarības:** P05, P08, P11, P22.

**Faili:**
- `engine/state/instance_state.py`
- `tests/state/test_instance_state.py`

**Moduļi:** `state/instance_state` — pabeigts.

**Testi:**
- Visi specifikācijas 72.3 lauki
- Persistēšana un ielāde
- Pozīcijas lauku notīrīšana pēc close

**Aizliegts pirms pabeigšanas:** P26, P56, P63–P74.

---

## P26 — Instance Memory

**Rezultāts:** In-memory konteiners katram instance ar ierobežotu vēstures garumu.

**Atkarības:** P24, P25.

**Faili:**
- `engine/state/memory.py`
- `engine/state/__init__.py`
- `tests/state/test_memory.py`

**Moduļi:** `state/memory` — pabeigts. Viss `state` modulis ir pabeigts.

**Testi:**
- Instance izolācija atmiņā
- `lookback_bars` ierobežojums
- Atmiņas atbrīvošana deaktivizācijā

**Aizliegts pirms pabeigšanas:** P35, P63–P74.

---

## P27 — Cache sistēma

**Rezultāts:** Failu hash cache novērš liešu pārlasīšanu.

**Atkarības:** P06, P08, P11.

**Faili:**
- `engine/core/cache.py`
- `tests/core/test_cache.py`

**Moduļi:** `core/cache` — pabeigts.

**Testi:**
- Hash maiņa → jāielādē atkārtoti
- Hash nemainās → izlaišana
- Cache invalidācija startup laikā

**Aizliegts pirms pabeigšanas:** P63–P74.

---

## P28 — Error Journal

**Rezultāts:** Visas kļūdas tiek pierakstītas `error_{symbol}_{magic}.jsonl`.

**Atkarības:** P05, P07, P08, P11.

**Faili:**
- `engine/journal/error_journal.py`
- `engine/journal/__init__.py`
- `tests/journal/test_error_journal.py`

**Moduļi:** `journal/error_journal` — pabeigts.

**Testi:**
- Kļūdas ieraksts ar visiem 19.10 laukiem
- Append-only
- Instance izolācija
- Nav silent exception

**Aizliegts pirms pabeigšanas:** P44, P56, P63–P74.

---

## P29 — Context analīze

**Rezultāts:** Universe konteksts tiek apvienots ar lokālo M1 vidi `AnalysisContext` objektā.

**Atkarības:** P03, P20, P21.

**Faili:**
- `engine/analysis/context.py`
- `engine/analysis/__init__.py`
- `tests/analysis/test_context.py`

**Moduļi:** `analysis/context` — pabeigts.

**Testi:**
- `trade_environment` vērtības: FAVORABLE, NEUTRAL, HOSTILE
- `news_active` no universe
- Context neizraisa trade

**Aizliegts pirms pabeigšanas:** P35, P39, P44, P63–P74.

---

## P30 — Structure analīze

**Rezultāts:** Swing augstumi, zemumi, atbalsts, pretestība un structure bias tiek aprēķināti.

**Atkarības:** P21, P26.

**Faili:**
- `engine/analysis/structure.py`
- `tests/analysis/test_structure.py`

**Moduļi:** `analysis/structure` — pabeigts.

**Testi:**
- `swing_high` un `swing_low` identificēti
- `structure_bias` atgriež BULLISH, BEARISH, NEUTRAL
- `break_of_structure` detekcija

**Aizliegts pirms pabeigšanas:** P35, P40–P41, P47, P63–P74.

---

## P31 — Momentum un Trend analīze

**Rezultāts:** Momentum un trend komponentes tiek aprēķinātas M1 datos.

**Atkarības:** P21, P26.

**Faili:**
- `engine/analysis/momentum.py`
- `tests/analysis/test_momentum.py`

**Moduļi:** `analysis/momentum` — pabeigts (ieskaitot trend izvadi).

**Testi:**
- `momentum_score` diapazons no -1 līdz 1
- `trend_direction`: UP, DOWN, SIDEWAYS
- `trend_strength` diapazons no 0 līdz 1
- Momentum neizslēdz BUY vai SELL

**Aizliegts pirms pabeigšanas:** P35, P42, P63–P74.

---

## P32 — Pressure analīze

**Rezultāts:** Buy un sell spiediens tiek aprēķināts no M1 sveču ķermeņiem.

**Atkarības:** P21, P26.

**Faili:**
- `engine/analysis/pressure.py`
- `tests/analysis/test_pressure.py`

**Moduļi:** `analysis/pressure` — pabeigts.

**Testi:**
- `buy_pressure` un `sell_pressure` diapazons 0 līdz 1
- `pressure_delta` aprēķins
- `absorption_detected` boolean

**Aizliegts pirms pabeigšanas:** P35, P42, P63–P74.

---

## P33 — Behavior analīze

**Rezultāts:** Sveču uzvedības pattern novērtējums tiek pievienots analīzei.

**Atkarības:** P21, P26.

**Faili:**
- `engine/analysis/behavior.py`
- `tests/analysis/test_behavior.py`

**Moduļi:** `analysis/behavior` — pabeigts.

**Testi:**
- Behavior objekts ar konsekventu struktūru
- Neatkarīgs no lēmumu loģikas

**Aizliegts pirms pabeigšanas:** P35, P63–P74.

---

## P34 — Impact analīze

**Rezultāts:** Setup kvalitātes ietekmes novērtējums tiek aprēķināts.

**Atkarības:** P29, P30, P31, P32, P33.

**Faili:**
- `engine/analysis/impact.py`
- `tests/analysis/test_impact.py`

**Moduļi:** `analysis/impact` — pabeigts.

**Testi:**
- Impact objekts satur kvalitātes vērtējumu
- Impact neizraisa trade

**Aizliegts pirms pabeigšanas:** P35, P63–P74.

---

## P35 — Analysis Engine orķestrācija

**Rezultāts:** Visi analīzes moduļi tiek izsaukti fiksētā secībā un atgriež pilnu `AnalysisContext`.

**Atkarības:** P29–P34.

**Faili:**
- `engine/analysis/engine.py`
- `tests/analysis/test_engine.py`

**Moduļi:** `analysis` — pilnībā pabeigts.

**Testi:**
- Secība: context → structure → momentum → pressure → behavior → impact
- Pilns `AnalysisContext` atgriežas
- Analysis Engine neizsauc decision vai risk

**Aizliegts pirms pabeigšanas:** P40–P44, P63–P74.

---

## P36 — Reason modulis

**Rezultāts:** Standartizēti reason stringi tiek ģenerēti no reason kodiem un parametriem.

**Atkarības:** P02.

**Faili:**
- `engine/decision/reason.py`
- `engine/decision/__init__.py`
- `tests/decision/test_reason.py`

**Moduļi:** `decision/reason` — pabeigts.

**Testi:**
- Katrs reason kods no `constants.py` ģenerē stringu
- Reason satur kodu un detaļu
- Tukšs reason nav atļauts

**Aizliegts pirms pabeigšanas:** P43–P44, P50, P63–P74.

---

## P37 — Spread filtrs

**Rezultāts:** Dinamiskais spread filtrs ar `relative_spread` bez cietiem limitiem.

**Atkarības:** P23, P24.

**Faili:**
- `engine/decision/filters/spread_filter.py`
- `engine/decision/filters/__init__.py`
- `tests/decision/test_spread_filter.py`

**Moduļi:** `decision/filters/spread_filter` — pabeigts.

**Testi:**
- `spread_acceptable` balstās uz relatīvo slieksni
- Nav cietu max spread skaitļu
- Reason `SPREAD_ABNORMAL` ģenerējas

**Aizliegts pirms pabeigšanas:** P40–P44, P63–P74.

---

## P38 — Volatility filtrs

**Rezultāts:** Relatīvā M1 volatilitāte tiek novērtēta pret vēsturisko ATR.

**Atkarības:** P21, P26.

**Faili:**
- `engine/decision/filters/volatility_filter.py`
- `tests/decision/test_volatility_filter.py`

**Moduļi:** `decision/filters/volatility_filter` — pabeigts.

**Testi:**
- `relative_volatility` aprēķins
- Reason `VOLATILITY_ABNORMAL`
- Nav cietu symbol specifiku sliekšņu

**Aizliegts pirms pabeigšanas:** P40–P44, P63–P74.

---

## P39 — News filtrs

**Rezultāts:** Universe news logs tiek izmantots virzienu derīguma noteikšanai.

**Atkarības:** P20, P29.

**Faili:**
- `engine/decision/filters/news_filter.py`
- `tests/decision/test_news_filter.py`

**Moduļi:** `decision/filters/news_filter` — pabeigts. Visi filtri pabeigti.

**Testi:**
- `news_window_active` ar `high` impact → virziens nederīgs
- Reason `NEWS_WINDOW_ACTIVE`
- Universe netirgo

**Aizliegts pirms pabeigšanas:** P40–P44, P63–P74.

---

## P40 — BUY aprēķins

**Rezultāts:** `BuyCandidate` tiek aprēķināts ar entry, SL, TP un komponentu vērtībām.

**Atkarības:** P35, P37, P38, P39, P30, P36.

**Faili:**
- `engine/decision/buy.py`
- `tests/decision/test_buy.py`

**Moduļi:** `decision/buy` — pabeigts.

**Testi:**
- Derīgs BUY kandidāts ar visiem laukiem
- Nederīgs BUY ar obligātu `invalid_reason`
- BUY neizlaiž SELL pārbaudi

**Aizliegts pirms pabeigšanas:** P42–P44, P63–P74.

---

## P41 — SELL aprēķins

**Rezultāts:** `SellCandidate` tiek aprēķināts ar entry, SL, TP un komponentu vērtībām.

**Atkarības:** P35, P37, P38, P39, P30, P36.

**Faili:**
- `engine/decision/sell.py`
- `tests/decision/test_sell.py`

**Moduļi:** `decision/sell` — pabeigts.

**Testi:**
- Derīgs SELL kandidāts ar visiem laukiem
- Nederīgs SELL ar obligātu `invalid_reason`
- SELL vienmēr tiek aprēķināts pat ja BUY derīgs

**Aizliegts pirms pabeigšanas:** P42–P44, P63–P74.

---

## P42 — Scoring sistēma

**Rezultāts:** BUY un SELL tiek salīdzināti, `preferred_side` tiek noteikts.

**Atkarības:** P40, P41.

**Faili:**
- `engine/decision/scorer.py`
- `tests/decision/test_scorer.py`

**Moduļi:** `decision/scorer` — pabeigts.

**Testi:**
- Scoring salīdzina, nefiltrē
- Augstākais score nosaka `preferred_side`
- Vienādi score → `preferred_side` NONE
- Scoring neizdod BLOCK

**Aizliegts pirms pabeigšanas:** P43–P44, P63–P74.

---

## P43 — WAIT un BLOCK loģika

**Rezultāts:** WAIT un BLOCK nosacījumi tiek piemēroti saskaņā ar specifikācijas 50. un 51. sadaļu.

**Atkarības:** P36, P40, P41, P42.

**Faili:**
- `engine/decision/wait_block.py`
- `tests/decision/test_wait_block.py`

**Moduļi:** `decision/wait_block` — pabeigts.

**Testi:**
- WAIT nav noklusējums
- `BOTH_DIRECTIONS_INVALID` → WAIT
- `EQUAL_SCORES` → WAIT
- BLOCK nav WAIT
- Katram WAIT un BLOCK ir reason

**Aizliegts pirms pabeigšanas:** P44, P63–P74.

---

## P44 — Decision Engine

**Rezultāts:** Pilns lēmumu cikls: BUY + SELL → scoring → WAIT/BLOCK → `DecisionResult`.

**Atkarības:** P36, P40, P41, P42, P43, P28.

**Faili:**
- `engine/decision/engine.py`
- `tests/decision/test_engine.py`

**Moduļi:** `decision` — pilnībā pabeigts.

**Testi:**
- Abi virzieni vienmēr aprēķināti
- Ja BUY neder, SELL pārbaudīts
- Ja SELL neder, BUY pārbaudīts
- Katrs rezultāts ar `decision_id` un reason
- Kļūda → error journal, ne silent exception

**Aizliegts pirms pabeigšanas:** P48, P50, P56, P63–P74.

---

## P45 — Risk Rules

**Rezultāts:** Visi riska noteikumi definēti kā atsevišķas pārbaudes.

**Atkarības:** P09, P19, P25.

**Faili:**
- `engine/risk/rules.py`
- `engine/risk/__init__.py`
- `tests/risk/test_rules.py`

**Moduļi:** `risk/rules` — pabeigts.

**Testi:**
- `max_open_positions_per_instance` pārbaude
- `max_daily_loss_percent` pārbaude
- `max_drawdown_percent` pārbaude
- `trade_allowed: false` → BLOCK
- Katram BLOCK ir reason

**Aizliegts pirms pabeigšanas:** P48, P63–P74.

---

## P46 — Position Sizing

**Rezultāts:** Pozīcijas tilpums tiek aprēķināts no equity, riska procenta un SL attāluma.

**Atkarības:** P22, P45.

**Faili:**
- `engine/risk/position_sizing.py`
- `tests/risk/test_position_sizing.py`

**Moduļi:** `risk/position_sizing` — pabeigts.

**Testi:**
- Tilpums > 0 ja ALLOW
- Nulles tilpums → BLOCK
- Dinamiski `point` un `pip` bez cietām tabulām
- Noapaļošana uz `volume_step`

**Aizliegts pirms pabeigšanas:** P48, P63–P74.

---

## P47 — Stop Loss un Take Profit validācija

**Rezultāts:** SL un TP tiek validēti un aprēķināti pirms riska ALLOW.

**Atkarības:** P30, P46.

**Faili:**
- `engine/risk/sl_tp.py`
- `tests/risk/test_sl_tp.py`

**Moduļi:** `risk/sl_tp` — pabeigts.

**Testi:**
- BUY SL zem swing low
- SELL SL virs swing high
- TP no reward ratio
- Trūkstošs TP → BLOCK ar `MISSING_TAKE_PROFIT`
- `max_stop_loss_pips` relatīvi pret pip

**Aizliegts pirms pabeigšanas:** P48, P49, P63–P74.

---

## P48 — Risk Engine

**Rezultāts:** Risk Engine atgriež tikai ALLOW vai BLOCK ar position size, SL un TP.

**Atkarības:** P44, P45, P46, P47.

**Faili:**
- `engine/risk/engine.py`
- `tests/risk/test_engine.py`

**Moduļi:** `risk` — pilnībā pabeigts.

**Testi:**
- Risks nedod WAIT
- Risks nemaina `preferred_side`
- ALLOW satur volume, SL, TP
- BLOCK satur reason
- Risks nepieņem BUY vai SELL — tikai ALLOW/BLOCK

**Aizliegts pirms pabeigšanas:** P49–P56, P63–P74.

---

## P49 — Trade Management

**Rezultāts:** Breakeven, trailing stop, partial close un time stop loģika darbojas caur MODIFY/CLOSE komandām.

**Atkarības:** P48, P25.

**Faili:**
- `engine/risk/trade_management.py`
- `tests/risk/test_trade_management.py`

**Moduļi:** `risk/trade_management` — pabeigts.

**Testi:**
- Breakeven ģenerē MODIFY
- Trailing stop ģenerē MODIFY
- Time stop ģenerē CLOSE
- Trade management neveic jaunu BUY/SELL bez lēmumu cikla

**Aizliegts pirms pabeigšanas:** P56, P63–P74.

---

## P50 — Decision Journal

**Rezultāts:** Katrs lēmums tiek pierakstīts `decision_{symbol}_{magic}.jsonl`.

**Atkarības:** P05, P07, P08, P11, P44.

**Faili:**
- `engine/journal/decision_journal.py`
- `tests/journal/test_decision_journal.py`

**Moduļi:** `journal/decision_journal` — pabeigts.

**Testi:**
- Katrs `DecisionResult` → journal ieraksts
- Visi 19.8 lauki klāt
- Append-only
- Instance izolācija

**Aizliegts pirms pabeigšanas:** P56, P63–P74.

---

## P51 — Trade Journal

**Rezultāts:** Visi execution notikumi tiek pierakstīti `trade_{symbol}_{magic}.jsonl`.

**Atkarības:** P05, P07, P08, P11.

**Faili:**
- `engine/journal/trade_journal.py`
- `tests/journal/test_trade_journal.py`

**Moduļi:** `journal` — pilnībā pabeigts.

**Testi:**
- OPEN intent pirms control
- ACK rezultāts pēc izpildes
- Visi 19.9 lauki klāt
- MODIFY un CLOSE notikumi

**Aizliegts pirms pabeigšanas:** P56, P63–P74.

---

## P52 — Order Command

**Rezultāts:** `OrderCommand` objekts tiek veidots no lēmuma un riska rezultāta.

**Atkarības:** P03, P44, P48.

**Faili:**
- `engine/execution/command.py`
- `engine/execution/__init__.py`
- `tests/execution/test_command.py`

**Moduļi:** `execution/command` — pabeigts.

**Testi:**
- BUY + ALLOW → OPEN ar side BUY
- SELL + ALLOW → OPEN ar side SELL
- WAIT → action NONE
- BLOCK → action NONE ar reason
- `command_id` un `decision_id` unikāli

**Aizliegts pirms pabeigšanas:** P53–P56, P63–P74.

---

## P53 — Control Writer

**Rezultāts:** Control JSON tiek rakstīts atomiski uz disku.

**Atkarības:** P05, P08, P11, P52.

**Faili:**
- `engine/execution/control_writer.py`
- `tests/execution/test_control_writer.py`

**Moduļi:** `execution/control_writer` — pabeigts.

**Testi:**
- Atomic write caur `.tmp`
- Visi 19.4 lauki klāt
- Instance atbilstība
- `schema_version` klāt

**Aizliegts pirms pabeigšanas:** P56, P60–P61, P63–P74.

---

## P54 — ACK Reader

**Rezultāts:** ACK JSON tiek nolasīts, validēts un interpretēts.

**Atkarības:** P04, P08, P11.

**Faili:**
- `engine/execution/ack_reader.py`
- `tests/execution/test_ack_reader.py`

**Moduļi:** `execution/ack_reader` — pabeigts.

**Testi:**
- SUCCESS, FAILED, REJECTED interpretācija
- `command_id` atbilstība
- Nederīgs ACK → kļūda un error journal
- Timeout stāvoklis atbalstīts

**Aizliegts pirms pabeigšanas:** P55–P56, P61, P63–P74.

---

## P55 — Retry un Timeout

**Rezultāts:** Retry politika IO operācijām un ACK timeout loģika.

**Atkarības:** P09, P12, P28.

**Faili:**
- `engine/core/retry.py`
- `engine/core/timeout.py`
- `tests/core/test_retry.py`
- `tests/core/test_timeout.py`

**Moduļi:** `core/retry`, `core/timeout` — pabeigti.

**Testi:**
- `retry_max` ierobežojums
- `retry_delay_ms` starp mēģinājumiem
- ACK timeout → error journal ar `ACK_TIMEOUT`
- Control netiek atkārtots ar vienu `command_id`

**Aizliegts pirms pabeigšanas:** P56, P63–P74.

---

## P56 — Execution Engine integrācija

**Rezultāts:** Pilns execution cikls: command → control → ack → state → trade journal.

**Atkarības:** P25, P28, P49, P51, P52, P53, P54, P55.

**Faili:**
- `engine/execution/engine.py`
- `tests/execution/test_engine.py`

**Moduļi:** `execution` — pilnībā pabeigts.

**Testi:**
- ALLOW + BUY → control → ack SUCCESS → state atjaunināts
- FAILED ack → error journal
- Trade journal atspoguļo pilnu ciklu
- Execution neveic analīzi

**Aizliegts pirms pabeigšanas:** P63–P74.

---

## P57 — MT4 EA — eksporta infrastruktūra

**Rezultāts:** EA izveido konta mapi, inicializē ceļus un atomic write funkcijas MT4 pusē.

**Atkarības:** P06, P11 (koncepcija).

**Faili:**
- `mql4/Include/SYSTEM_IO.mqh`
- `mql4/Include/SYSTEM_Paths.mqh`

**Moduļi:** MT4 IO infrastruktūra — pabeigta.

**Testi:**
- EA startā izveido `data/clients/{account_id}/`
- Atomic write funkcija raksta `.tmp` un rename
- Ceļš norāda uz `C:\SYSTEM`

**Aizliegts pirms pabeigšanas:** P58–P61, P74.

---

## P58 — MT4 EA — market un sensor eksports

**Rezultāts:** EA eksportē M1 market CSV un sensor CSV ar visām obligātajām kolonnām.

**Atkarības:** P57, P04 (shēmas atbilstība).

**Faili:**
- `mql4/Experts/SYSTEM_EA.mq4` — eksporta daļa
- `mql4/Include/SYSTEM_Export.mqh`

**Moduļi:** MT4 market un sensor eksports — pabeigts.

**Testi:**
- M1 svece eksportēta ar pareizām kolonnām
- `timeframe` ir `M1`
- `digits` un `point` no MT4
- Sensor satur bid, ask, spread
- EA neveic analīzi

**Aizliegts pirms pabeigšanas:** P59–P61, P63–P74.

---

## P59 — MT4 EA — status un universe eksports

**Rezultāts:** EA eksportē status JSON un universe JSON.

**Atkarības:** P57, P58.

**Faili:**
- `mql4/Include/SYSTEM_Status.mqh`
- `mql4/Include/SYSTEM_Universe.mqh`

**Moduļi:** MT4 status un universe eksports — pabeigts.

**Testi:**
- Status satur balance, equity, connected, trade_allowed
- Universe nesatur trade signālu laukus
- `schema_version` klāt
- Atomic write darbojas

**Aizliegts pirms pabeigšanas:** P60–P61, P63–P74.

---

## P60 — MT4 EA — control lasīšana

**Rezultāts:** EA nolasa control JSON un validē instance laukus.

**Atkarības:** P57, P53 (shēmas atbilstība).

**Faili:**
- `mql4/Include/SYSTEM_Control.mqh`

**Moduļi:** MT4 control lasīšana — pabeigta.

**Testi:**
- Derīgs control nolasīts
- Nepareizs magic noraidīts
- Nepareizs symbol noraidīts
- `action: NONE` apstrādāts bez ordera

**Aizliegts pirms pabeigšanas:** P61, P63–P74.

---

## P61 — MT4 EA — orderu izpilde un ACK

**Rezultāts:** EA izpilda OPEN, MODIFY, CLOSE un raksta ACK.

**Atkarības:** P60.

**Faili:**
- `mql4/Include/SYSTEM_Execution.mqh`
- `mql4/Experts/SYSTEM_EA.mq4` — pilnīga EA integrācija

**Moduļi:** MT4 execution — pilnībā pabeigts.

**Testi:**
- OPEN BUY un OPEN SELL ar magic
- MODIFY SL/TP
- CLOSE pozīcija
- ACK ar SUCCESS, FAILED, REJECTED
- `command_id` atgriezts ACK
- EA nelemj virzienu — tikai izpilda control

**Aizliegts pirms pabeigšanas:** P63–P74.

---

## P62 — `run_live.py` — startup un shutdown

**Rezultāts:** Live process startē, validē vidi, inicializē instances un korekti apstājas.

**Atkarības:** P09, P10, P12, P08, P26.

**Faili:**
- `run_live.py`
- `engine/core/lifecycle.py`
- `tests/core/test_lifecycle.py`

**Moduļi:** `core/lifecycle` — pabeigts.

**Testi:**
- Startup ar derīgu konfigurāciju
- Startup ar nederīgu konfigurāciju → exit ar kļūdu
- Shutdown persistē state
- EA status `connected: false` netraucē shutdown

**Aizliegts pirms pabeigšanas:** P63–P74.

---

## P63 — `run_live.py` — vienas instances cikls

**Rezultāts:** Viena `(account_id, symbol, magic)` instance izpilda pilnu ciklu no load līdz execution.

**Atkarības:** P13–P56, P62.

**Faili:**
- `engine/core/cycle.py`
- `tests/core/test_cycle.py`

**Moduļi:** `core/cycle` — pabeigts.

**Testi:**
- Pilns cikls ar fixture failiem
- Nederīgs market → error journal, trade nenotiek
- Derīgs cikls → decision journal ieraksts
- BUY/SELL abi aprēķināti katrā ciklā

**Aizliegts pirms pabeigšanas:** P64–P74.

---

## P64 — `run_live.py` — multi-instance un multi-account

**Rezultāts:** Vairākas instances un konti tiek apstrādāti secīgi ar pilnu izolāciju.

**Atkarības:** P63.

**Faili:**
- `engine/core/orchestrator.py`
- `tests/core/test_orchestrator.py`

**Moduļi:** `core/orchestrator` — pabeigts.

**Testi:**
- Divas instances vienā kontā — izolēti state un journal
- Divi konti — izolēti ceļi
- Vienas instances kļūda neaptur otru
- `auto_discover_instances` atklāj jaunas instances

**Aizliegts pirms pabeigšanas:** P65–P74.

---

## P65 — Recovery un Error Recovery

**Rezultāts:** Pēc restarta sistēma atjauno state, identificē neapstiprinātas komandas un sinhronizē pozīcijas.

**Atkarības:** P25, P54, P55, P64.

**Faili:**
- `engine/core/recovery.py`
- `tests/core/test_recovery.py`

**Moduļi:** `core/recovery` — pabeigts.

**Testi:**
- State atjaunošana no diska
- ACK timeout recovery
- Neapstiprināta control netiek atkārtota bez jauna lēmuma
- Spread modelis atjaunots no sensor vēstures

**Aizliegts pirms pabeigšanas:** P66–P74.

---

## P66 — Dashboard

**Rezultāts:** Dashboard attēlo instances, lēmumus, reason, spread, pozīcijas un kļūdas bez analīzes.

**Atkarības:** P10, P12, P50, P51, P28.

**Faili:**
- `dashboard.py`
- `engine/dashboard/console.py`
- `engine/dashboard/reader.py`
- `tests/dashboard/test_console.py`

**Moduļi:** `dashboard` — pilnībā pabeigts.

**Testi:**
- Dashboard attēlo pēdējo lēmumu
- Dashboard neraksta control
- Dashboard neizsauc analysis, decision, risk
- Atjaunināšana pēc `refresh_interval_ms`

**Aizliegts pirms pabeigšanas:** P67–P74.

---

## P67 — Live monitoring un Alert sistēma

**Rezultāts:** Cycle latency, ACK latency, error rate un data freshness tiek monitorēti un alerti ģenerēti.

**Atkarības:** P12, P63.

**Faili:**
- `engine/core/monitoring.py`
- `engine/core/alerts.py`
- `tests/core/test_monitoring.py`
- `tests/core/test_alerts.py`

**Moduļi:** `core/monitoring`, `core/alerts` — pabeigti.

**Testi:**
- Data stale → WARNING
- ACK timeout → ERROR
- Alert neizraisa trade
- Metrikas rakstītas logā

**Aizliegts pirms pabeigšanas:** P68–P74.

---

## P68 — Performance monitoring

**Rezultāts:** Veiktspējas metrikas tiek mērītas un rakstītas logā.

**Atkarības:** P67.

**Faili:**
- `engine/core/performance.py`
- `tests/core/test_performance.py`

**Moduļi:** `core/performance` — pabeigts.

**Testi:**
- `cycle_duration_ms` mērīts
- `memory_rss_mb` mērīts
- Metrikas neietekmē lēmumus

**Aizliegts pirms pabeigšanas:** P69–P74.

---

## P69 — Integration testi — datu plūsma

**Rezultāts:** Load → validate → normalize → state ķēde darbojas ar fixture datiem.

**Atkarības:** P16, P20, P26.

**Faili:**
- `tests/integration/test_data_pipeline.py`
- `tests/integration/fixtures/` — pilns konta datu komplekts

**Moduļi:** Nav jaunu moduļu.

**Testi:**
- Pilna datu plūsma vienai instance
- Nederīgs fails aptur plūsmu ar error journal
- Spread modelis atjaunināts

**Aizliegts pirms pabeigšanas:** P70–P74.

---

## P70 — Integration testi — lēmumu plūsma

**Rezultāts:** Analysis → decision → risk → decision journal ķēde darbojas.

**Atkarības:** P44, P48, P50, P69.

**Faili:**
- `tests/integration/test_decision_pipeline.py`

**Moduļi:** Nav jaunu moduļu.

**Testi:**
- BUY un SELL abi aprēķināti
- WAIT ar reason
- BLOCK ar risk reason
- Decision journal satur visus lēmumus

**Aizliegts pirms pabeigšanas:** P71–P74.

---

## P71 — Integration testi — execution plūsma

**Rezultāts:** Execution → control → ack → trade journal → state ķēde darbojas.

**Atkarības:** P56, P51, P70.

**Faili:**
- `tests/integration/test_execution_pipeline.py`

**Moduļi:** Nav jaunu moduļu.

**Testi:**
- Control fails izveidots
- Simulēts ACK atjaunina state
- Trade journal pilns cikls
- FAILED ack → error journal

**Aizliegts pirms pabeigšanas:** P72–P74.

---

## P72 — End-to-End tests

**Rezultāts:** Pilns cikls no market faila līdz ACK un state atjaunināšanai darbojas automatizēti.

**Atkarības:** P69, P70, P71.

**Faili:**
- `tests/e2e/test_full_cycle.py`
- `tests/e2e/simulator/mt4_simulator.py`

**Moduļi:** MT4 simulators testiem — pabeigts.

**Testi:**
- Specifikācijas 100. sadaļas soļi 8–60 ar simulatoru
- BUY/SELL/WAIT/BLOCK scenāriji
- Multi-instance E2E

**Aizliegts pirms pabeigšanas:** P73–P74.

---

## P73 — Performance tests

**Rezultāts:** Sistēma iekļaujas `cycle_max_duration_ms` un atmiņa stabilizējas.

**Atkarības:** P68, P72.

**Faili:**
- `tests/performance/test_cycle_duration.py`
- `tests/performance/test_memory.py`

**Moduļi:** Nav jaunu moduļu.

**Testi:**
- Viena instance cikls < `cycle_max_duration_ms`
- 10 instances secīgi < kopējā limita
- Atmiņa neaug neierobežoti 1000 ciklos

**Aizliegts pirms pabeigšanas:** P74.

---

## P74 — LIVE sistēmas palaišana un validācija

**Rezultāts:** Pilnībā funkcionējoša LIVE sistēma ar reālu MT4, Python `run_live.py` un dashboard. Pilns darba cikls no M1 tick līdz order close darbojas produkcijas vidē.

**Atkarības:** P61, P64, P65, P66, P67, P68, P72, P73.

**Faili:**
- `docs/ARCHITECTURE.md` — gala arhitektūras kopsavilkums
- `docs/PROTOCOL.md` — gala protokola kopsavilkums
- `tools/validate_live.py` — LIVE vides validācijas utilīta

**Moduļi:** Visa sistēma — pilnībā pabeigta.

**Testi:**
- `tools/validate_live.py` apstiprina visus ceļus, konfigurāciju un EA savienojumu
- Reāls M1 eksports no MT4 nonāk Python
- Python pieņem lēmumu ar reason un journal
- Control nonāk MT4 un orderis izpildās
- ACK atgriežas Python un state atjauninās
- Dashboard rāda aktuālo stāvokli
- Specifikācijas 100. sadaļas pilns cikls izpildās reālā vidē
- Visi `docs/RULES.md` noteikumi ievēroti

**LIVE validācijas kontrolsaraksts:**

| # | Pārbaude |
|---|----------|
| 1 | M1 ir vienīgais timeframe |
| 2 | Multi-account darbojas |
| 3 | Multi-symbol darbojas |
| 4 | Instance izolācija starp account+symbol+magic |
| 5 | BUY un SELL abi aprēķināti katrā ciklā |
| 6 | WAIT nav noklusējums |
| 7 | Risk atgriež tikai ALLOW vai BLOCK |
| 8 | Spread dinamisks, bez cietiem limitiem |
| 9 | Nav cietu symbol sarakstu |
| 10 | Katram lēmumam ir reason |
| 11 | Katrs lēmums journal |
| 12 | Dashboard neanalizē |
| 13 | Universe netirgo |
| 14 | MT4 neanalizē |
| 15 | Kļūdas nav slēptas |

**Aizliegts pirms pabeigšanas:** Nav — šis ir gala posms.

---

## P75 — Audita High labojumi un spec atbilstības nostiprināšana

**Rezultāts:** Visi post-Critical audita High punkti novērsti; state, risk konfigurācija, recovery, I/O retry, timeout/stale enforcement, MT4 partial close, ACK robustums, E2E trade management un identitātes validācija atbilst `SYSTEM_SPECIFICATION.md` §54–55, §57.2, §78–79, §80.4.

**Atkarības:** P74 (funkcionālā bāze), `HIGH_FIX_PLAN.md` (audita plāns).

**Faili:**
- `engine/state/instance_state.py`, `engine/core/cycle.py`, `engine/core/recovery.py`, `engine/core/orchestrator.py`
- `engine/core/atomic_io.py`, `engine/loader/*.py`, `engine/execution/*.py`
- `engine/protocol/models.py`, `engine/protocol/identity.py`, `config/system.json`
- `mql4/Include/SYSTEM_Execution.mqh`
- `tests/e2e/test_trade_management_cycle.py`, `tests/protocol/test_identity.py`
- `HIGH_FIX_SUMMARY.md`, `AUDIT_AFTER_HIGH.md`

**Moduļi:** State, cycle, recovery, execution, protocol, MT4 execution — pilnīgāka LIVE gatavība.

**Testi:**
- 853+ automatizētie testi (`pytest tests/`)
- E2E: OPEN → MODIFY (SL atjaunināts), OPEN → CLOSE (state clear)
- Recovery: late ACK pēc TIMEOUT
- P67 / §79.3: stale dati aptur ciklu pirms lēmuma fāzes (baru laika zīmogi); monitoring joprojām brīdina pēc cikla

**Aizliegts pirms pabeigšanas:** Nav — šis ir post-LIVE audita posms.

---

## Posmu atkarību diagramma

```
P01
 └─► P02 ─► P03 ─┬─► P04 ─► P05
                 └─► P06 ─┬─► P09 ─► P10
                          ├─► P07
                          ├─► P08
                          ├─► P11
                          └─► P12

P04+P06+P08+P11 ─► P13–P16 (loaders)
P04+loaders ─► P17–P20 (validators)
P17 ─► P21 ─► P22
P18 ─► P23 ─► P24
P22 ─► P25 ─► P26
P06+P08+P11 ─► P27
P05+P07+P08+P11 ─► P28

P21+P20 ─► P29
P21+P26 ─► P30–P33
P29–P34 ─► P35

P02 ─► P36
P23+P24 ─► P37
P21+P26 ─► P38
P20+P29 ─► P39
P35+P37–P39+P30+P36 ─► P40–P41 ─► P42 ─► P43 ─► P44

P09+P19+P25 ─► P45 ─► P46 ─► P47 ─► P48
P48+P25 ─► P49
P44 ─► P50
P05+P07+P08+P11 ─► P51

P44+P48 ─► P52 ─► P53
P04+P08+P11 ─► P54
P09+P12+P28 ─► P55
P25+P28+P49+P51–P55 ─► P56

P06 ─► P57 ─► P58 ─► P59 ─► P60 ─► P61

P09+P10+P12+P08+P26 ─► P62
P13–P56+P62 ─► P63 ─► P64 ─► P65
P10+P12+P50+P51+P28 ─► P66
P12+P63 ─► P67 ─► P68

P16+P20+P26 ─► P69
P44+P48+P50+P69 ─► P70
P56+P51+P70 ─► P71
P69–P71 ─► P72
P68+P72 ─► P73
P61+P64–P68+P72+P73 ─► P74 (LIVE)
```

---

## Jaunu failu kopsavilkums (izveidojami implementācijas laikā)

Šie faili nav esošajā scaffold, bet ir nepieciešami saskaņā ar specifikāciju un šo plānu:

| Fails | Posms |
|-------|-------|
| `engine/core/atomic_io.py` | P11 |
| `engine/core/logging_setup.py` | P12 |
| `engine/core/cache.py` | P27 |
| `engine/core/retry.py` | P55 |
| `engine/core/timeout.py` | P55 |
| `engine/core/lifecycle.py` | P62 |
| `engine/core/cycle.py` | P63 |
| `engine/core/orchestrator.py` | P64 |
| `engine/core/recovery.py` | P65 |
| `engine/core/monitoring.py` | P67 |
| `engine/core/alerts.py` | P67 |
| `engine/core/performance.py` | P68 |
| `engine/normalizer/instrument_params.py` | P22 |
| `engine/journal/error_journal.py` | P28 |
| `engine/analysis/engine.py` | P35 |
| `engine/decision/filters/spread_filter.py` | P37 |
| `engine/decision/filters/volatility_filter.py` | P38 |
| `engine/decision/filters/news_filter.py` | P39 |
| `engine/decision/buy.py` | P40 |
| `engine/decision/sell.py` | P41 |
| `engine/decision/wait_block.py` | P43 |
| `engine/risk/position_sizing.py` | P46 |
| `engine/risk/sl_tp.py` | P47 |
| `engine/risk/trade_management.py` | P49 |
| `engine/execution/engine.py` | P56 |
| `engine/dashboard/reader.py` | P66 |
| `mql4/Include/SYSTEM_IO.mqh` | P57 |
| `mql4/Include/SYSTEM_Paths.mqh` | P57 |
| `mql4/Include/SYSTEM_Export.mqh` | P58 |
| `mql4/Include/SYSTEM_Status.mqh` | P59 |
| `mql4/Include/SYSTEM_Universe.mqh` | P59 |
| `mql4/Include/SYSTEM_Control.mqh` | P60 |
| `mql4/Include/SYSTEM_Execution.mqh` | P61 |
| `tools/validate_live.py` | P74 |
| `docs/ORDER_COMMAND.md` | P52 |
| `tools/validate_order_command.py` | P52 |

---

## Implementācijas noteikumi

1. **Viens posms — viens pabeigts rezultāts.** Posms nedrīkst atstāt pusimplementētus moduļus.

2. **Bez patch.** Ja posma rezultāts neatbilst specifikācijai, posms jāpabeidz pareizi, nevis jālabo nākamajos posmos ar workaround.

3. **Testi ir obligāti.** Posms ir pabeigts tikai tad, kad visi tā testi iziet.

4. **Atkarību secība ir strikta.** Posms nedrīkst sākties, kamēr nav pabeigti visi atkarību posmi.

5. **Specifikācija ir avots.** Jebkura implementācijas detaļa jāpārbauda pret `docs/SYSTEM_SPECIFICATION.md`.

6. **Noteikumi ir obligāti.** Jebkurš posms jāievēro `docs/RULES.md`.

7. **Gala mērķis ir P74.** Līdz P74 sistēma nav uzskatāma par pabeigtu LIVE platformu.

---

*Šis dokuments ir SYSTEM projekta vienīgais izstrādes plāns. Implementācija sākas ar P01 un beidzas ar P74.*
