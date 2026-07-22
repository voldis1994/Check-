# SYSTEM — Tehniskā specifikācija

**Versija:** 1.0  
**Statuss:** Obligāts implementācijas avots  
**Projekta sakne:** `C:\Check\System`

Šis dokuments ir SYSTEM tirdzniecības platformas vienīgais tehniskais avots. Visa implementācija tiek veidota tieši pēc šī dokumenta. Dokuments neparedz un neatbalsta nekādu iepriekšēju kodu, patch pieeju vai legacy saderību.

Saistītie noteikumi: `docs/RULES.md` ir normatīvais noteikumu kopums. Pretrunā starp implementāciju un `docs/RULES.md` pareizi ir noteikumi. Šī specifikācija detalizē noteikumus līdz implementējamam līmenim.

---

## Satura rādītājs

1. Projekta filozofija  
2. Sistēmas mērķis  
3. Pilna arhitektūra  
4. Visa mapju struktūra  
5. Visa failu struktūra  
6. Moduļu atbildība  
7. Moduļu savstarpējās atkarības  
8. Visa datu plūsma  
9. MT4 arhitektūra  
10. Python arhitektūra  
11. Dashboard arhitektūra  
12. Konfigurācijas arhitektūra  
13. Multi Account arhitektūra  
14. Multi Symbol arhitektūra  
15. Instance izolācija  
16. Account + Symbol + Magic loģika  
17. Pilns komunikācijas protokols starp MT4 un Python  
18. Visi izmantotie faili  
19. Visi JSON formāti  
20. Visi CSV formāti  
21. Failu nosaukumu standarts  
22. Mapju organizācija  
23. Failu dzīves cikls  
24. Startup process  
25. Shutdown process  
26. Recovery process  
27. Error Recovery  
28. Failu validācija  
29. Datu validācija  
30. Datu normalizācija  
31. Market Loader  
32. Sensor Loader  
33. Status Loader  
34. Universe Loader  
35. Market Validator  
36. Sensor Validator  
37. Universe Validator  
38. Spread modelis  
39. Instrumentu parametru noteikšana  
40. Analysis Engine  
41. Momentum analīze  
42. Trend analīze  
43. Structure analīze  
44. Pressure analīze  
45. Context analīze  
46. Scoring sistēma  
47. BUY aprēķins  
48. SELL aprēķins  
49. BUY pret SELL salīdzināšana  
50. WAIT loģika  
51. BLOCK loģika  
52. Decision Engine  
53. Risk Engine  
54. Position Sizing  
55. Stop Loss  
56. Take Profit  
57. Trade Management  
58. Spread filtrs  
59. Volatility filtrs  
60. News filtrs  
61. Universe izmantošana  
62. Journal sistēma  
63. Decision Journal  
64. Trade Journal  
65. Error Journal  
66. Dashboard  
67. Live monitorings  
68. Alert sistēma  
69. Performance monitorings  
70. Memory pārvaldība  
71. Cache sistēma  
72. State sistēma  
73. Instance Memory  
74. Execution Engine  
75. Order Command  
76. Control faili  
77. ACK sistēma  
78. Retry loģika  
79. Timeout loģika  
80. Drošības principi  
81. Thread Safety  
82. File Locking  
83. Atomic Write  
84. Atomic Read  
85. Konfigurācijas noteikumi  
86. Dynamic Spread  
87. Dynamic Instrument Detection  
88. Dynamic Digits  
89. Dynamic Point  
90. Dynamic Pip  
91. Coding standarts  
92. Naming standarts  
93. Logging standarts  
94. Testēšanas arhitektūra  
95. Unit Test  
96. Integration Test  
97. End-to-End Test  
98. Performance Test  
99. Future Extension Architecture  
100. Pilns sistēmas darba cikls no pirmā Tick līdz Order Close  

---

## 1. Projekta filozofija

SYSTEM ir deterministiska, instance-izolēta, failu balstīta tirdzniecības platforma, kurā lēmumu inteliģence atrodas Python pusē, bet izpilde un tirgus datu ieguve — MT4 pusē.

Galvenie filozofijas principi:

**Vienas atbildības princips.** Katrs modulis veic vienu skaidri definētu uzdevumu. Analīze neveic riska vērtējumu. Risks nepieņem virziena lēmumu. Execution neanalizē tirgu. Dashboard neko nelemj.

**Instance absolūtā izolācija.** Katra `(Account, Symbol, Magic)` tripleta darbojas kā neatkarīga vienība ar savu stāvokli, spread modeli, žurnālu, riska kontekstu un execution kanālu. Neviena instance nevar kļūdaini ietekmēt citu.

**Virzienu simetrija.** BUY un SELL vienmēr tiek vērtēti abi. Sistēma neoptimizē uz vienu virzienu. WAIT nav drošības mehānisms neziņā — tas ir tikai informēts secinājums pēc pilnas abu virzienu izvērtēšanas.

**Dinamiska tirgus adaptācija.** Instrumentu īpašības, spread norma, digits, point un pip netiek iepriekš fiksēti. Tie tiek noteikti no reāliem MT4 datiem un uzturēti dinamiski.

**Kļūdu caurredzamība.** Neviena kļūda netiek slēpta. Bojāti vai nepilnīgi dati izraisa trade apturēšanu un obligātu kļūdas reģistrāciju.

**Ilgtspējīga arhitektūra.** Sistēma projektēta tā, lai nākotnes paplašinājumi notiktu moduļu iekšienē vai jaunos moduļos, nemainot pamata datu plūsmu, instance modeli un lēmumu secību.

**Bez kompromisiem ar noteikumiem.** Neviens modulis, konfigurācijas lauks vai operacionāls process nedrīkst apiet `docs/RULES.md` prasības.

---

## 2. Sistēmas mērķis

SYSTEM mērķis ir nodrošināt automatizētu, daudzkontu, daudzinstrumentu M1 tirdzniecības platformu, kas:

- Saņem M1 tirgus datus un sensoru datus no MT4
- Normalizē un validē datus instance līmenī
- Veic strukturētu tirgus analīzi un salīdzina BUY pret SELL
- Piemēro riska kontroli ar ALLOW vai BLOCK rezultātu
- Ģenerē execution komandas ar pilnu reason un journal pierakstu
- Nodrošina MT4 orderu izpildi un atpakaļejošu ACK apstiprinājumu
- Sniedz operacionālu pārskatu caur dashboard bez analītiskas iejaukšanās

Sistēma nav paredzēta kā signālu ģenerators bez izpildes, kā MT4 analītiskais spraudnis vai kā manuāla tirdzniecības saskarne. Tā ir pilna lēmumu un izpildes cilpa ar stingru atbildības sadalījumu.

---

## 3. Pilna arhitektūra

SYSTEM sastāv no četriem galvenajiem slāņiem:

### 3.1. Datu ieguves slānis (MT4)

`SYSTEM_EA.mq4` eksportē M1 tirgus datus, sensoru datus, konta statusu un universuma kontekstu uz `data/clients/`. Lasа control komandas no `data/clients/` un izpilda orderus. Sūta ACK atpakaļ.

MT4 nesasniedz analīzes, lēmumu, riska vai scoring moduļus.

### 3.2. Datu apstrādes slānis (Python — loader, validator, normalizer)

Ielasa MT4 eksporta failus, validē struktūru un saturu, normalizē uz iekšējiem modeļiem, atjaunina spread modeli un instrumentu parametrus.

### 3.3. Intelekta slānis (Python — analysis, decision, risk)

Veic analīzi, aprēķina BUY un SELL kandidātus, salīdzina ar scoring, piemēro riska noteikumus, pieņem gala lēmumu ar reason.

### 3.4. Izpildes un novērošanas slānis (Python execution, journal, dashboard; MT4 execution)

Raksta control failus, lasa ACK, uztur state, žurnalē visus notikumus, rāda operacionālo attēlu dashboard.

### 3.5. Arhitektūras diagramma (loģiskā)

```
MT4 (SYSTEM_EA)
  │ export: market, sensor, status, universe
  ▼
data/clients/{account_id}/
  │ load
  ▼
Loader → Validator → Normalizer
  │ normalized data
  ▼
Analysis Engine → Decision Engine → Risk Engine
  │ decision + reason
  ▼
Journal + Execution (control write)
  │ control.json
  ▼
MT4 (order execution)
  │ ack.json
  ▼
ACK Reader → State Update → Trade Journal
  │
  ▼
Dashboard (read-only display)
```

Visi procesi notiek instance kontekstā: `(account_id, symbol, magic)`.

---

## 4. Visa mapju struktūra

```
C:\Check\System\
├── mql4\
│   ├── Experts\
│   └── Include\
├── engine\
│   ├── protocol\
│   ├── core\
│   ├── loader\
│   ├── validator\
│   ├── normalizer\
│   ├── analysis\
│   ├── decision\
│   ├── risk\
│   ├── execution\
│   ├── state\
│   ├── journal\
│   └── dashboard\
├── config\
├── data\
│   ├── clients\
│   ├── logs\
│   ├── cache\
│   ├── history\
│   └── universe\
├── tests\
│   ├── protocol\
│   ├── loader\
│   ├── normalizer\
│   ├── decision\
│   ├── risk\
│   └── execution\
├── docs\
├── tools\
├── run_live.py
├── dashboard.py
├── README.md
└── requirements.txt
```

### 4.1. `mql4/`

MT4 puses kods. `Experts/` satur EA. `Include/` satur MT4 koplietojamos header failus, ja nepieciešams EA modulārai uzbūvei.

### 4.2. `engine/`

Visa Python biznesa loģika. Apakšmapes atbilst vienai atbildības zonai.

### 4.3. `config/`

Vienīgā konfigurācijas vieta. Satur `system.json`.

### 4.4. `data/`

Visi runtime dati. Nekas ārpus `data/` netiek rakstīts kā operacionāls datu krātuve, izņemot log failus zem `data/logs/`.

| Apakšmape | Mērķis |
|-----------|--------|
| `clients/` | MT4 ↔ Python komunikācijas faili pa kontiem |
| `logs/` | Sistēmas, kļūdu un operacionālie logi |
| `cache/` | Īslaicīga cache datu glabāšana |
| `history/` | Ilgtermiņa vēsturiskie datu arhīvi |
| `universe/` | Universuma konteksta faili |

### 4.5. `tests/`

Automatizēto testu katalogs, strukturēts pēc moduļu grupām.

### 4.6. `docs/`

Dokumentācija. `SYSTEM_SPECIFICATION.md` ir primārais tehniskais avots.

### 4.7. `tools/`

Palīgutilītas, kas nav daļa no live runtime cilpas.

---

## 5. Visa failu struktūra

### 5.1. MT4 faili

| Fails | Mērķis |
|-------|--------|
| `mql4/Experts/SYSTEM_EA.mq4` | Galvenais EA: eksports, control lasīšana, orderu izpilde, ACK |

### 5.2. Python engine faili

| Modulis | Faili |
|---------|-------|
| `protocol/` | `__init__.py`, `constants.py`, `errors.py`, `models.py`, `parser.py`, `writer.py` |
| `core/` | `__init__.py`, `config.py`, `clock.py`, `instance.py`, `paths.py` |
| `loader/` | `__init__.py`, `market_loader.py`, `sensor_loader.py`, `status_loader.py`, `universe_loader.py` |
| `validator/` | `__init__.py`, `market_validator.py`, `sensor_validator.py`, `status_validator.py`, `universe_validator.py` |
| `normalizer/` | `__init__.py`, `market_normalizer.py`, `spread_model.py` |
| `analysis/` | `__init__.py`, `context.py`, `momentum.py`, `pressure.py`, `structure.py`, `behavior.py`, `impact.py` |
| `decision/` | `__init__.py`, `scorer.py`, `engine.py`, `reason.py` |
| `risk/` | `__init__.py`, `engine.py`, `rules.py` |
| `execution/` | `__init__.py`, `command.py`, `control_writer.py`, `ack_reader.py` |
| `state/` | `__init__.py`, `memory.py`, `spread_state.py`, `instance_state.py` |
| `journal/` | `__init__.py`, `decision_journal.py`, `trade_journal.py` |
| `dashboard/` | `__init__.py`, `console.py` |

### 5.3. Konfigurācija un entry point

| Fails | Mērķis |
|-------|--------|
| `config/system.json` | Vienīgā sistēmas konfigurācija |
| `run_live.py` | Live engine palaišana |
| `dashboard.py` | Dashboard palaišana |
| `requirements.txt` | Python atkarības |
| `README.md` | Projekta operacionālais kopsavilkums |

### 5.4. Dokumentācija

| Fails | Mērķis |
|-------|--------|
| `docs/RULES.md` | Obligātie noteikumi |
| `docs/SYSTEM_SPECIFICATION.md` | Šis dokuments |
| `docs/ARCHITECTURE.md` | Arhitektūras kopsavilkums implementācijas laikā |
| `docs/PROTOCOL.md` | Protokola kopsavilkums implementācijas laikā |

### 5.5. Runtime datu faili (ģenerēti)

Katram kontam `data/clients/{account_id}/` un katram instance identifikatoram tiek izmantoti standartizēti faili, definēti 17., 18., 19., 20. un 21. sadaļā.

---

## 6. Moduļu atbildība

| Modulis | Vienīgā atbildība |
|---------|-------------------|
| `protocol` | Datu modeļu definīcija, parsēšana, rakstīšana, protokola kļūdas |
| `core` | Konfigurācijas ielāde, ceļi, pulkstenis, instance identitāte |
| `loader` | MT4 eksporta failu ielāde no diska |
| `validator` | Ielādēto datu struktūras un satura validācija |
| `normalizer` | Validētu datu pārveide uz iekšējo formātu; spread modeļa aprēķins |
| `analysis` | Tirgus analīze bez lēmumu pieņemšanas |
| `decision` | BUY/SELL kandidātu aprēķins, salīdzināšana, WAIT/BLOCK secība |
| `risk` | ALLOW/BLOCK vērtējums |
| `execution` | Control komandu veidošana un ACK lasīšana |
| `state` | Instance stāvokļa uzturēšana atmiņā |
| `journal` | Lēmumu un darījumu pierakstīšana |
| `dashboard` | Datu attēlošana bez analīzes |
| `SYSTEM_EA.mq4` | Datu eksports, orderu izpilde, ACK |

Neviens modulis nedrīkst pildīt cita moduļa funkciju.

---

## 7. Moduļu savstarpējās atkarības

Atkarības virziens ir vienvirziena — no apakšas uz augšu. Augstākais slānis nedrīkst importēt zemāku slāni apiet analīzes vai validācijas kārtību.

```
core
  ↑
protocol
  ↑
loader → validator → normalizer → state
  ↑
analysis (izmanto normalizer + state + universe)
  ↑
decision (izmanto analysis + reason)
  ↑
risk (izmanto decision kandidātus + state + rules)
  ↑
journal (raksta pēc decision un risk)
  ↑
execution (raksta control pēc gala lēmuma)
  ↑
ack_reader → state → trade_journal

dashboard (tikai lasa state, journal, logs — neimportē analysis vai decision)
```

**Atkarību noteikumi:**

- `loader` nedrīkst importēt `analysis`, `decision`, `risk`, `execution`
- `analysis` nedrīkst importēt `decision`, `risk`, `execution`
- `decision` nedrīkst importēt `execution`
- `risk` nedrīkst mainīt scoring rezultātu — tikai ALLOW/BLOCK
- `dashboard` nedrīkst importēt `analysis`, `decision`, `risk`
- `SYSTEM_EA` nekomunicē tieši ar Python moduļiem — tikai ar failiem

---

## 8. Visa datu plūsma

### 8.1. Ienākošā plūsma (MT4 → Python)

1. MT4 aizver jaunu M1 sveci vai sasniedz eksporta intervālu
2. EA raksta `market_{symbol}_{magic}.csv`
3. EA raksta `sensor_{symbol}_{magic}.csv`
4. EA raksta `status_{account_id}.json`
5. EA raksta vai atjaunina `universe.json` kontekstu
6. Python `run_live.py` cikls detektē failu atjauninājumu
7. Loader ielādē failus
8. Validator validē
9. Normalizer normalizē un atjaunina spread modeli
10. State atjaunina instance atmiņu

### 8.2. Analītiskā plūsma

1. Analysis Engine saņem normalizētus datus instance kontekstā
2. Momentum, Structure, Pressure, Context, Behavior, Impact moduļi ražo analītiskos rezultātus
3. Rezultāti tiek nodoti Decision Engine bez trade komandas

### 8.3. Lēmumu plūsma

1. Decision Engine aprēķina BUY kandidātu
2. Decision Engine aprēķina SELL kandidātu
3. Scorer salīdzina BUY pret SELL
4. Risk Engine piemēro ALLOW/BLOCK
5. Reason tiek pievienots gala lēmumam
6. Decision Journal pieraksta lēmumu

### 8.4. Izejošā plūsma (Python → MT4)

1. Ja lēmums ir BUY vai SELL un risks ir ALLOW, Execution ģenerē Order Command
2. Control Writer raksta `control_{symbol}_{magic}.json` atomiski
3. MT4 EA nolasa control
4. MT4 izpilda orderu
5. MT4 raksta `ack_{symbol}_{magic}.json`
6. ACK Reader apstrādā ACK
7. Trade Journal un State atjaunināšana

### 8.5. Novērošanas plūsma

1. Dashboard periodiski lasa state, journal un log failus
2. Dashboard attēlo bez modificēšanas

---

## 9. MT4 arhitektūra

### 9.1. EA struktūra

`SYSTEM_EA.mq4` darbojas uz katra chart, kur tas ir pievienots. Katram EA eksemplāram ir piesaistīts:

- `AccountNumber` — konta identifikators
- `Symbol` — instruments chartā
- `MagicNumber` — instance magic numurs

EA neveic tirgus analīzi. EA funkcijas ir:

1. **Export cikls** — periodiski vai uz jaunas M1 sveces raksta market un sensor failus
2. **Status cikls** — raksta konta statusu
3. **Control lasīšana** — nolasa control failu instance atslēgai
4. **Order izpilde** — izpilda OPEN, MODIFY, CLOSE komandas
5. **ACK rakstīšana** — apstiprina komandas izpildi vai kļūdu

### 9.2. EA darba režīms

EA darbojas uz M1 timeframe. EA neizmanto citus timeframes pat iekšējiem aprēķiniem. Visi eksportētie OHLC dati ir M1.

### 9.3. EA ceļu noteikšana

EA izmanto `C:\Check\System\data\clients\{account_id}\` kā bāzes ceļu. `account_id` ir MT4 `AccountNumber` kā virkne.

### 9.4. EA kļūdu apstrāde

Ja fails nav rakstāms, EA pieraksta kļūdu `status_{account_id}.json` laukā `last_error` un neizpilda trade bez derīga control. EA nekad nerada noklusējuma orderus.

### 9.5. EA un multi-instance

Vairāki EA var strādāt uz viena konta dažādiem simboliem vai ar dažādiem magic numuriem. Katrs EA eksplorē tikai savu `(symbol, magic)` failu kopu.

---

## 10. Python arhitektūra

### 10.1. Runtime modelis

`run_live.py` ir galvenais process. Tas:

1. Ielādē `config/system.json`
2. Inicializē `core` moduļus
3. Atklāj aktīvās instances no `data/clients/` struktūras
4. Izpilda galveno ciklu katram account un instance

Python process ir vienīgais lēmumu avots.

### 10.2. Instance cilpas arhitektūra

Katrai `(account_id, symbol, magic)` tripletei tiek izveidots `Instance` objekts ar atsaucēm uz:

- `InstanceState`
- `SpreadState`
- `SpreadModel`
- `DecisionJournal` ceļu
- `TradeJournal` ceļu
- `ControlWriter` ceļu

Instances netiek koplietotas starp threadiem bez sinhronizācijas mehānismiem, definētiem 81. sadaļā.

### 10.3. Moduļu orķestrācija

`run_live.py` izsauc moduļus stingrā secībā:

```
load → validate → normalize → analyze → decide → ai → risk → journal → execute → ack
```

Ja jebkurā posmā validācija neizdodas, cikls šai instance beidzas ar kļūdas pierakstu un bez trade.

### 10.3.1. AI decision slānis (OpenAI)

Pēc SYSTEM lēmuma (`engine/decision/engine.py`) cikls izsauc `engine/ai_decision_layer.py`:

| Režīms | Uzvedība |
|--------|----------|
| `advisory` (noklusējums) | AI kļūda → SYSTEM fallback; valid AI → veto/allow |
| `required` / `fail_closed` | AI kļūda → BLOCK |

Konfigurācija: `config/system.json` sadaļa `ai`. API atslēga: vides mainīgais `OPENAI_API_KEY`.

Secība: **decide → AI → risk (uz post-AI signāla) → journal → trade management (respektē `allow_close`) → execution**.

### 10.4. Dashboard process

`dashboard.py` ir atsevišķs process. Tas neietilpst `run_live.py` cilpā un neinterferē ar lēmumu pieņemšanu.

---

## 11. Dashboard arhitektūra

### 11.1. Mērķis

Dashboard nodrošina operacionālu redzamību: aktīvās instances, pēdējos lēmumus, reason, risk statusu, spread stāvokli, atvērtās pozīcijas, ACK statusu un kļūdas.

### 11.2. Datu avoti

Dashboard lasa tikai:

- `data/clients/` control un ack failus
- `engine/state` persistētos stāvokļus, ja tādi ir eksportēti
- `data/logs/`
- instance journal failus

### 11.3. Aizliegumi

Dashboard:

- Neizsauc `analysis`, `decision`, `risk`
- Neraksta control failus
- Nemaina `config/system.json`
- Neveic trade lēmumus

### 11.4. Attēlošanas modulis

`engine/dashboard/console.py` atbild par formātētu izvadi terminālī. `dashboard.py` inicializē un periodiski atjaunina skatu.

### 11.5. Atjaunināšanas intervāls

Dashboard atjaunināšanas intervāls nāk no `config/system.json` lauka `dashboard.refresh_interval_ms`. Intervāls neietekmē lēmumu cikla ātrumu.

---

## 12. Konfigurācijas arhitektūra

### 12.1. Vienots konfigurācijas fails

Visi konfigurācijas parametri atrodas `config/system.json`. Nav citu konfigurācijas failu live režīmā.

### 12.2. Konfigurācijas slāņi

| Slānis | Satur |
|--------|-------|
| `system` | Procesa nosaukums, versija, root ceļš |
| `paths` | Relatīvie ceļi uz data apakšmapēm |
| `runtime` | Cikla intervāli, timeout, retry |
| `instances` | Aktīvo instance definīcijas vai auto-discovery flag |
| `risk` | Riska noteikumu parametri bez cietajiem spread limitiem |
| `analysis` | Analīzes moduļu parametri |
| `journal` | Žurnālu ceļi un rotācijas noteikumi |
| `dashboard` | Dashboard parametri |
| `logging` | Log līmeņi un formāts |

### 12.3. Konfigurācijas ielāde

`engine/core/config.py` ielādē JSON starta laikā. Konfigurācija tiek validēta pirms jebkura moduļa starta. Nederīga konfigurācija aptur sistēmas startu ar skaidru kļūdu.

### 12.4. Konfigurācijas aizliegumi

`system.json` nedrīkst saturēt:

- Cietus max spread skaitļus
- Cietus symbol sarakstus
- Cietas digits, point, pip vērtības
- Trade lēmumu loģiku

---

## 13. Multi Account arhitektūra

### 13.1. Account identifikācija

`account_id` ir MT4 konta numurs kā virkne. Katram kontam ir atsevišķa mape:

`data/clients/{account_id}/`

### 13.2. Account izolācija

Konti nedalās:

- Status failiem
- Journal struktūras saknēm
- Log prefiksiem

Tomēr universe konteksts var būt globāls failā `data/universe/universe.json`, ja konfigurācija to nosaka, bet tas joprojām ir tikai konteksts.

### 13.3. Vairāku kontu apstrāde

`run_live.py` iterē pār visām `data/clients/` apakšmapēm. Katra mape ar derīgu struktūru tiek uzskatīta par aktīvu kontu.

### 13.4. Konta statusa monitorings

`status_{account_id}.json` satur savienojuma, maržas un kļūdu informāciju. Ja status ir nederīgs, visas šī konta instances tiek bloķētas ar BLOCK un attiecīgu reason.

---

## 14. Multi Symbol arhitektūra

### 14.1. Symbol identifikācija

`symbol` ir MT4 simbola nosaukums precīzi tā formā, kā to atgriež MT4. Sistēma nepārveido simbolu nosaukumus un nefiltrē pēc fiksēta saraksta.

### 14.2. Symbol dinamiska atklāšana

Aktīvie simboli tiek atklāti no:

- `config/system.json` instance definīcijām
- Eksistējošiem market failiem `data/clients/{account_id}/`

Ja parādās jauns simbols ar derīgiem failiem un konfigurācijas atbalstu, sistēma inicializē jaunu instance bez koda izmaiņām.

### 14.3. Symbol neatkarība

Katram simbolam savs spread modelis, state un journal. Simbolu stāvokļi netiek koplietoti.

---

## 15. Instance izolācija

### 15.1. Instance definīcija

Instance ir sistēmas mazākā autonomā vienība. Instance identitāte ir pilnībā noteikta ar:

```
instance_key = (account_id, symbol, magic)
```

### 15.2. Instance resursi

Katrai instance pieder:

| Resurss | Apraksts |
|---------|----------|
| `InstanceState` | Pašreizējais operacionālais stāvoklis |
| `SpreadState` | Spread vēstures un pašreizējais novērtējums |
| `SpreadModel` | Dinamiskais spread profils |
| `DecisionJournal` | Lēmumu vēsture |
| `TradeJournal` | Darījumu vēsture |
| `ControlChannel` | Control un ACK failu pāris |
| `RiskContext` | Instance riska stāvoklis |

### 15.3. Izolācijas garantijas

Kļūda vienā instance neaptur citu instanču ciklu. BLOCK vienā instance neizraisa BLOCK citā. State mutācijas notiek tikai instance ietvaros.

### 15.4. Instance dzīves cikls

Instance tiek izveidota pirmajā derīgajā datu ielādē. Instance tiek deaktivizēta, ja status kļūst nederīgs vai konfigurācija to izslēdz. Instance stāvoklis tiek persistēts pirms deaktivizācijas.

---

## 16. Account + Symbol + Magic loģika

### 16.1. Magic numura loma

`magic` ir vesels skaitlis, ko EA izmanto visiem orderiem šai instance. Magic nodrošina orderu identifikāciju MT4 pusē un instance atdalīšanu vienam kontam un simbolam.

### 16.2. Tripleta unikalitāte

Sistēma uzskata, ka `(account_id, symbol, magic)` ir unikāls. Ja konfigurācijā vai failos parādās dublikāts, sistēma pieraksta kļūdu un neizpilda trade līdz konflikta novēršanai.

### 16.3. Tripleta kartēšana uz failiem

Visi instance specifiskie faili satur `symbol` un `magic` faila nosaukumā. `account_id` ir mapes līmenī.

### 16.4. Tripleta kartēšana uz orderiem

Katram MT4 orderim jābūt ar `magic`, kas atbilst instance `magic`. EA noraida control komandas ar neatbilstošu magic.

---

## 17. Pilns komunikācijas protokols starp MT4 un Python

### 17.1. Protokola pamatprincipi

- Komunikācija notiek tikai caur failiem zem `data/clients/{account_id}/`
- JSON strukturētiem ziņojumiem: status, universe, control, ack
- CSV M1 tirgus vēsturei un sensoru laika rindām
- Atomiska rakstīšana no abām pusēm
- Katram ziņojumam ir `schema_version` lauks

### 17.2. Virzienu kopsavilkums

| Virziens | Fails | Formāts | Ražotājs | Patērētājs |
|----------|-------|---------|----------|------------|
| MT4 → Python | `market_{symbol}_{magic}.csv` | CSV | EA | market_loader |
| MT4 → Python | `sensor_{symbol}_{magic}.csv` | CSV | EA | sensor_loader |
| MT4 → Python | `status_{account_id}.json` | JSON | EA | status_loader |
| MT4 → Python | `universe.json` | JSON | EA | universe_loader |
| Python → MT4 | `control_{symbol}_{magic}.json` | JSON | control_writer | EA |
| MT4 → Python | `ack_{symbol}_{magic}.json` | JSON | EA | ack_reader |

### 17.3. Secība control izpildei

1. Python raksta `control_{symbol}_{magic}.json.tmp`
2. Python pārdēvē uz `control_{symbol}_{magic}.json`
3. EA nolasa control
4. EA izpilda darbību
5. EA raksta `ack_{symbol}_{magic}.json`
6. Python nolasa ACK
7. Python arhivē vai atzīmē apstrādātu control

### 17.4. Protokola versija

`schema_version` ir obligāts visos JSON failos. Python un MT4 noraida failus ar neatbalstītu versiju un pieraksta kļūdu.

### 17.5. Laika zīmogi

Visi JSON faili satur `timestamp_utc` ISO 8601 formātā ar milisekundēm. CSV faili satur `time_utc` kolonnu.

### 17.6. Instance identifikācija protokolā

Visos JSON failos obligāti lauki:

- `account_id`
- `symbol`
- `magic`

Ja kāds trūkst, fails ir nederīgs.

---

## 18. Visi izmantotie faili

### 18.1. Konfigurācijas fails

| Fails | Tips |
|-------|------|
| `config/system.json` | Konfigurācija |

### 18.2. Konta līmeņa faili

Ceļš: `data/clients/{account_id}/`

| Fails | Tips |
|-------|------|
| `status_{account_id}.json` | Konta statuss |
| `universe.json` | Tirgus konteksts |

### 18.3. Instance līmeņa faili

Ceļš: `data/clients/{account_id}/`

| Fails | Tips |
|-------|------|
| `market_{symbol}_{magic}.csv` | M1 OHLCV |
| `sensor_{symbol}_{magic}.csv` | Spread un sensori |
| `control_{symbol}_{magic}.json` | Trade komanda |
| `ack_{symbol}_{magic}.json` | Izpildes apstiprinājums |

### 18.4. Journal faili

Ceļš: `data/clients/{account_id}/journal/`

| Fails | Tips |
|-------|------|
| `decision_{symbol}_{magic}.jsonl` | Lēmumu žurnāls |
| `trade_{symbol}_{magic}.jsonl` | Darījumu žurnāls |
| `error_{symbol}_{magic}.jsonl` | Kļūdu žurnāls |

### 18.5. State persistences faili

Ceļš: `data/clients/{account_id}/state/`

| Fails | Tips |
|-------|------|
| `instance_{symbol}_{magic}.json` | Instance stāvoklis |
| `spread_{symbol}_{magic}.json` | Spread vēstures kopsavilkums |

### 18.6. Cache faili

Ceļš: `data/cache/{account_id}/{symbol}_{magic}/`

| Fails | Tips |
|-------|------|
| `last_market.hash` | Pēdējā market faila hash |
| `last_sensor.hash` | Pēdējā sensor faila hash |

### 18.7. History faili

Ceļš: `data/history/{account_id}/{symbol}_{magic}/`

| Fails | Tips |
|-------|------|
| `market_{YYYY-MM-DD}.csv` | Arhivēta M1 vēsture |
| `decision_{YYYY-MM-DD}.jsonl` | Arhivēti lēmumi |

### 18.8. Log faili

Ceļš: `data/logs/`

| Fails | Tips |
|-------|------|
| `system_{YYYY-MM-DD}.log` | Sistēmas logs |
| `account_{account_id}_{YYYY-MM-DD}.log` | Konta logs |

### 18.9. Universe fails

Ceļš: `data/universe/`

| Fails | Tips |
|-------|------|
| `universe.json` | Globāls vai replikēts universuma konteksts |

---

## 19. Visi JSON formāti

### 19.1. `config/system.json`

| Lauks | Tips | Obligāts | Apraksts |
|-------|------|----------|----------|
| `schema_version` | string | jā | Konfigurācijas shēmas versija |
| `system.name` | string | jā | Vienmēr `SYSTEM` |
| `system.root_path` | string | jā | `C:\\Check\\System` |
| `system.timeframe` | string | jā | Vienmēr `M1` |
| `paths.clients` | string | jā | Relatīvs ceļš uz clients |
| `paths.logs` | string | jā | Relatīvs ceļš uz logs |
| `paths.cache` | string | jā | Relatīvs ceļš uz cache |
| `paths.history` | string | jā | Relatīvs ceļš uz history |
| `paths.universe` | string | jā | Relatīvs ceļš uz universe |
| `runtime.cycle_interval_ms` | integer | jā | Galvenā cilpas intervāls |
| `runtime.ack_timeout_ms` | integer | jā | ACK gaidīšanas laiks |
| `runtime.retry_max` | integer | jā | Maksimālais retry skaits |
| `runtime.auto_discover_instances` | boolean | jā | Automātiska instance atklāšana |
| `instances` | array | jā | Instance definīciju masīvs |
| `instances[].account_id` | string | jā | Konta ID |
| `instances[].symbol` | string | jā | Simbols |
| `instances[].magic` | integer | jā | Magic numurs |
| `instances[].enabled` | boolean | jā | Instance aktīva vai nē |
| `risk.max_open_positions_per_instance` | integer | jā | Pozīciju limits instance |
| `risk.max_daily_loss_percent` | number | jā | Dienas zaudējumu limits procentos |
| `risk.max_drawdown_percent` | number | jā | Maksimālais drawdown procents |
| `analysis.lookback_bars` | integer | jā | Analīzes vēstures garums M1 |
| `journal.retention_days` | integer | jā | Žurnālu glabāšanas dienas |
| `dashboard.refresh_interval_ms` | integer | jā | Dashboard atjaunināšana |
| `logging.level` | string | jā | DEBUG, INFO, WARNING, ERROR |
| `logging.format` | string | jā | Log formāta identifikators |

### 19.2. `status_{account_id}.json`

| Lauks | Tips | Obligāts | Apraksts |
|-------|------|----------|----------|
| `schema_version` | string | jā | Protokola versija |
| `timestamp_utc` | string | jā | ISO 8601 UTC |
| `account_id` | string | jā | Konta numurs |
| `connected` | boolean | jā | MT4 savienojums aktīvs |
| `trade_allowed` | boolean | jā | Vai MT4 atļauj trade |
| `balance` | number | jā | Konta bilance |
| `equity` | number | jā | Konta ekvitīte |
| `margin_free` | number | jā | Brīvā marža |
| `last_error` | string | nē | Pēdējā EA kļūda |
| `ea_version` | string | jā | EA versija |
| `open_positions` | array | nē | Atvērtās pozīcijas visā kontā; katrs elements satur `symbol`, `magic`, `ticket`, `side`, `volume`, `entry_price`, `stop_loss`, `take_profit` |

### 19.2.1. `open_positions[]` elements

| Lauks | Tips | Obligāts | Apraksts |
|-------|------|----------|----------|
| `symbol` | string | jā | Simbols |
| `magic` | integer | jā | Magic |
| `ticket` | integer | jā | MT4 ordera tickets |
| `side` | string | jā | BUY vai SELL |
| `volume` | number | jā | Atvērtais apjoms |
| `entry_price` | number | jā | Ieejas cena |
| `stop_loss` | number | jā | Stop loss |
| `take_profit` | number | jā | Take profit |

### 19.3. `universe.json`

| Lauks | Tips | Obligāts | Apraksts |
|-------|------|----------|----------|
| `schema_version` | string | jā | Protokola versija |
| `timestamp_utc` | string | jā | ISO 8601 UTC |
| `session` | string | jā | Pašreizējā tirgus sesija |
| `market_regime` | string | jā | Režīms: trending, ranging, volatile, quiet |
| `news_window_active` | boolean | jā | Vai aktīvs ziņu logs |
| `news_impact_level` | string | nē | low, medium, high |
| `correlation_group` | object | nē | Korrelāciju grupu karte |
| `metadata` | object | nē | Papildu konteksts bez trade signāliem |

Universe JSON nedrīkst saturēt laukus: `signal`, `direction`, `trade`, `buy`, `sell`, `action`.

### 19.4. `control_{symbol}_{magic}.json`

| Lauks | Tips | Obligāts | Apraksts |
|-------|------|----------|----------|
| `schema_version` | string | jā | Protokola versija |
| `timestamp_utc` | string | jā | ISO 8601 UTC |
| `command_id` | string | jā | Unikāls UUID |
| `account_id` | string | jā | Konta numurs |
| `symbol` | string | jā | Simbols |
| `magic` | integer | jā | Magic |
| `action` | string | jā | OPEN, MODIFY, CLOSE, NONE |
| `side` | string | nē | BUY, SELL ja action ir OPEN |
| `volume` | number | nē | Lotes |
| `stop_loss` | number | nē | SL cena |
| `take_profit` | number | nē | TP cena |
| `ticket` | integer | nē | Eksistējošs orderis MODIFY/CLOSE |
| `reason` | string | jā | Lēmuma reason |
| `decision_id` | string | jā | Saite uz decision journal |

### 19.5. `ack_{symbol}_{magic}.json`

| Lauks | Tips | Obligāts | Apraksts |
|-------|------|----------|----------|
| `schema_version` | string | jā | Protokola versija |
| `timestamp_utc` | string | jā | ISO 8601 UTC |
| `command_id` | string | jā | Atbilst control command_id |
| `account_id` | string | jā | Konta numurs |
| `symbol` | string | jā | Simbols |
| `magic` | integer | jā | Magic |
| `status` | string | jā | SUCCESS, FAILED, REJECTED |
| `ticket` | integer | nē | Izveidotā vai modificētā pozīcija |
| `action` | string | nē | OPEN/MODIFY/CLOSE (MODIFY ACK obligāti) |
| `requested_stop_loss` | number | nē | Pieprasītais SL (MODIFY) |
| `applied_stop_loss` | number | nē | Brokera faktiskais SL pēc OrderModify |
| `requested_take_profit` | number | nē | Pieprasītais TP (MODIFY) |
| `applied_take_profit` | number | nē | Brokera faktiskais TP pēc OrderModify |
| `broker_error_code` | integer | nē | MT4 GetLastError / broker kļūdas kods |
| `error_code` | integer | nē | MT4 kļūdas kods |
| `error_message` | string | nē | Kļūdas apraksts |

### 19.6. `instance_{symbol}_{magic}.json`

| Lauks | Tips | Obligāts | Apraksts |
|-------|------|----------|----------|
| `schema_version` | string | jā | State shēmas versija |
| `account_id` | string | jā | Konta numurs |
| `symbol` | string | jā | Simbols |
| `magic` | integer | jā | Magic |
| `last_decision` | string | jā | BUY, SELL, WAIT, BLOCK |
| `last_reason` | string | jā | Pēdējā reason |
| `open_ticket` | integer | nē | Atvērtās pozīcijas tickets |
| `position_side` | string | nē | BUY vai SELL |
| `position_volume` | number | nē | Pozīcijas tilpums |
| `last_cycle_utc` | string | jā | Pēdējā cikla laiks |

### 19.6.1. `monitoring_{symbol}_{magic}.json`

| Lauks | Tips | Obligāts | Apraksts |
|-------|------|----------|----------|
| `schema_version` | string | jā | Protokola versija |
| `account_id` | string | jā | Konta numurs |
| `symbol` | string | jā | Simbols |
| `magic` | integer | jā | Magic |
| `timestamp_utc` | string | jā | Metriku laiks |
| `cycle_latency_ms` | integer | nē | Cikla latentums |
| `ack_latency_ms` | integer | nē | ACK latentums |
| `data_freshness_ms` | integer | nē | Datu vecums |
| `error_count` | integer | jā | Kumulatīvais kļūdu skaits |
| `error_rate_per_min` | number | jā | Kļūdu likme minūtē |
| `instance_health` | string | jā | VALID, BLOCKED vai ERROR |

### 19.7. `spread_{symbol}_{magic}.json`

| Lauks | Tips | Obligāts | Apraksts |
|-------|------|----------|----------|
| `schema_version` | string | jā | Shēmas versija |
| `account_id` | string | jā | Konta numurs |
| `symbol` | string | jā | Simbols |
| `magic` | integer | jā | Magic |
| `sample_count` | integer | jā | Vēstures izmērs |
| `mean_spread` | number | jā | Vidējais spread |
| `std_spread` | number | jā | Standartnovirze |
| `median_spread` | number | jā | Mediāna |
| `current_spread` | number | jā | Pašreizējais spread |
| `relative_spread` | number | jā | Pašreizējais attiecībā pret normu |
| `updated_utc` | string | jā | Atjaunināšanas laiks |

### 19.8. Decision journal ieraksts (`decision_*.jsonl`)

Katrs JSONL ieraksts vienā rindā:

| Lauks | Tips | Obligāts | Apraksts |
|-------|------|----------|----------|
| `decision_id` | string | jā | UUID |
| `timestamp_utc` | string | jā | ISO 8601 |
| `account_id` | string | jā | Konts |
| `symbol` | string | jā | Simbols |
| `magic` | integer | jā | Magic |
| `decision` | string | jā | BUY, SELL, WAIT, BLOCK |
| `reason` | string | jā | Pilns reason |
| `buy_score` | number | nē | BUY scoring vērtība |
| `sell_score` | number | nē | SELL scoring vērtība |
| `risk_result` | string | jā | ALLOW vai BLOCK |
| `risk_reason` | string | nē | Riska reason ja BLOCK |

### 19.9. Trade journal ieraksts (`trade_*.jsonl`)

| Lauks | Tips | Obligāts | Apraksts |
|-------|------|----------|----------|
| `trade_id` | string | jā | UUID |
| `timestamp_utc` | string | jā | ISO 8601 |
| `account_id` | string | jā | Konts |
| `symbol` | string | jā | Simbols |
| `magic` | integer | jā | Magic |
| `event` | string | jā | OPEN, MODIFY, CLOSE |
| `side` | string | nē | BUY, SELL |
| `volume` | number | nē | Lotes |
| `price` | number | nē | Izpildes cena |
| `ticket` | integer | nē | MT4 tickets |
| `command_id` | string | jā | Saite uz control |
| `ack_status` | string | jā | SUCCESS, FAILED, REJECTED |
| `reason` | string | jā | Notikuma reason |

### 19.10. Error journal ieraksts (`error_*.jsonl`)

| Lauks | Tips | Obligāts | Apraksts |
|-------|------|----------|----------|
| `error_id` | string | jā | UUID |
| `timestamp_utc` | string | jā | ISO 8601 |
| `account_id` | string | jā | Konts |
| `symbol` | string | nē | Simbols ja zināms |
| `magic` | integer | nē | Magic ja zināms |
| `module` | string | jā | Moduļa nosaukums |
| `error_type` | string | jā | VALIDATION, IO, PROTOCOL, EXECUTION, RISK |
| `message` | string | jā | Kļūdas apraksts |
| `context` | object | nē | Papildu konteksts |

---

## 20. Visi CSV formāti

### 20.1. `market_{symbol}_{magic}.csv`

M1 tirgus dati. Viena rinda = viena M1 svece.

| Kolonna | Tips | Obligāts | Apraksts |
|---------|------|----------|----------|
| `time_utc` | string | jā | Sveces sākums ISO 8601 UTC |
| `open` | number | jā | Atvēršanas cena |
| `high` | number | jā | Maksimums |
| `low` | number | jā | Minimums |
| `close` | number | jā | Slēgšanas cena |
| `volume` | number | jā | Ticks vai lotes atkarībā no MT4 |
| `symbol` | string | jā | Simbols |
| `timeframe` | string | jā | Vienmēr `M1` |
| `digits` | integer | jā | Ciparu skaits no MT4 |
| `point` | number | jā | Point vērtība no MT4 |

Kolonnu secība ir fiksēta. Papildu kolonnas nav atļautas bez shēmas versijas maiņas.

### 20.2. `sensor_{symbol}_{magic}.csv`

Sensoru un spread laika rinda.

| Kolonna | Tips | Obligāts | Apraksts |
|---------|------|----------|----------|
| `time_utc` | string | jā | Mērījuma laiks ISO 8601 UTC |
| `bid` | number | jā | Bid cena |
| `ask` | number | jā | Ask cena |
| `spread` | number | jā | Ask minus Bid |
| `spread_points` | number | jā | Spread punktos pēc MT4 |
| `symbol` | string | jā | Simbols |
| `digits` | integer | jā | Ciparu skaits |
| `point` | number | jā | Point vērtība |

### 20.3. History market arhīvs

`data/history/{account_id}/{symbol}_{magic}/market_{YYYY-MM-DD}.csv` izmanto identisku shēmu kā 20.1.

---

## 21. Failu nosaukumu standarts

### 21.1. Vispārīgie noteikumi

- Tikai mazie burti failu nosaukumos, izņemot `{symbol}`, kas saglabā MT4 reģistru
- Atdalītājs ir pasvītra `_`
- Bez atstarpēm
- Bez speciālajām zīmēm ārpus MT4 simbola naturālā formāta
- Paplašinājumi: `.json`, `.csv`, `.jsonl`, `.log`, `.tmp`

### 21.2. Nosaukumu šabloni

| Šablons | Nozīme |
|---------|--------|
| `market_{symbol}_{magic}.csv` | M1 tirgus dati |
| `sensor_{symbol}_{magic}.csv` | Sensoru dati |
| `control_{symbol}_{magic}.json` | Control komanda |
| `ack_{symbol}_{magic}.json` | ACK |
| `status_{account_id}.json` | Konta statuss |
| `decision_{symbol}_{magic}.jsonl` | Lēmumu žurnāls |
| `trade_{symbol}_{magic}.jsonl` | Darījumu žurnāls |
| `error_{symbol}_{magic}.jsonl` | Kļūdu žurnāls |
| `instance_{symbol}_{magic}.json` | Instance state |
| `spread_{symbol}_{magic}.json` | Spread state |
| `universe.json` | Universe konteksts |

### 21.3. Pagaidu faili

Rakstīšanas laikā izmanto `.tmp` paplašinājumu. Galīgais nosaukums tiek sasniegts ar atomic rename.

---

## 22. Mapju organizācija

### 22.1. Konta hierarhija

```
data/clients/{account_id}/
├── status_{account_id}.json
├── universe.json
├── market_{symbol}_{magic}.csv
├── sensor_{symbol}_{magic}.csv
├── control_{symbol}_{magic}.json
├── ack_{symbol}_{magic}.json
├── journal/
│   ├── decision_{symbol}_{magic}.jsonl
│   ├── trade_{symbol}_{magic}.jsonl
│   └── error_{symbol}_{magic}.jsonl
└── state/
    ├── instance_{symbol}_{magic}.json
    └── spread_{symbol}_{magic}.json
```

### 22.2. Globālā hierarhija

```
data/
├── clients/
├── logs/
├── cache/
├── history/
└── universe/
```

### 22.3. Mapju izveides noteikums

Mapes tiek izveidotas startup laikā, ja tās neeksistē. Izveidi veic `engine/core/paths.py`.

---

## 23. Failu dzīves cikls

### 23.1. Market un sensor faili

1. EA raksta `.tmp`
2. EA rename uz galīgo CSV
3. Python loader nolasa
4. Python cache atjaunina hash
5. Vecākie history dati tiek arhivēti periodiski

### 23.2. Control fails

1. Python raksta `control_*.json.tmp`
2. Python rename uz `control_*.json`
3. EA nolasa un apstrādā
4. Pēc ACK Python pārvieto uz `data/history/` vai atzīmē kā apstrādātu state

### 23.3. ACK fails

1. EA raksta `ack_*.json`
2. Python ack_reader nolasa
3. Pēc apstrādes ACK tiek arhivēts

### 23.4. Journal faili

Journal faili ir append-only. Rotācija notiek pēc `journal.retention_days`.

### 23.5. State faili

State faili tiek pārrakstīti pilnībā pēc katra veiksmīga cikla vai būtiskas izmaiņas.

---

## 24. Startup process

### 24.1. Secība

1. Pārbauda, ka root ceļš eksistē: `C:\Check\System`
2. Ielādē `config/system.json`
3. Validē konfigurāciju
4. Izveido trūkstošās mapes
5. Inicializē logging
6. Atklāj instances no konfigurācijas un failu sistēmas
7. Ielādē persistēto state katram instance
8. Inicializē spread modeli no spread state
9. Iemācās cache hash
10. Ieej galvenajā cilpā

### 24.2. Startup kļūdas

Jebkura startup kļūda aptur procesu ar exit kodu un ierakstu `data/logs/system_{date}.log`. Sistēma nestartē daļēji.

### 24.3. MT4 startup

EA starta laikā izveido konta mapi, ja tā neeksistē, un raksta sākotnējo status failu.

---

## 25. Shutdown process

### 25.1. Python shutdown

1. Saņem shutdown signālu
2. Pārtrauc jaunu control ģenerēšanu
3. Persistē visu instance state
4. Persistē spread state
5. Pieraksta shutdown notikumu logā
6. Aizver failu deskriptorus
7. Iziet ar kodu 0

### 25.2. MT4 shutdown

EA pirms apstāšanās raksta `connected: false` status failā.

### 25.3. Neparasta apstāšanās

Ja process tiek nogalināts, nākamais startup atjauno state no diska. Nepilnīgs control fails netiek atkārtoti izpildīts pēc `command_id` unikalitātes.

---

## 26. Recovery process

### 26.1. Mērķis

Atjaunot konsekventu darba stāvokli pēc avārijas, restarta vai datu kavēšanās.

### 26.2. Recovery soļi

1. Nolasa pēdējo zināmo instance state
2. Salīdzina ar pēdējo ACK
3. Identificē neapstiprinātas control komandas
4. Ja ACK trūkst pēc timeout, atzīmē komandu kā neizdevušos
5. Sinhronizē atvērtās pozīcijas ar status failu
6. Atjauno spread modeli no sensor vēstures
7. Turpina ciklu

### 26.3. Recovery ierobežojumi

Recovery neveic automātisku orderu atkārtotu izsūtīšanu bez jauna lēmumu cikla un jauna decision journal ieraksta.

---

## 27. Error Recovery

### 27.1. Kļūdu klasifikācija

| Klase | Reakcija |
|-------|----------|
| VALIDATION | Trade nenotiek, error journal, cikls turpinās |
| IO | Retry saskaņā ar retry politiku |
| PROTOCOL | Trade nenotiek, error journal, instance var tikt bloķēta |
| EXECUTION | Trade journal ar FAILED, state atjaunināšana |
| RISK | BLOCK ar risk reason |

### 27.2. Error Recovery principi

- Neviena kļūda netiek ignorēta
- Katrai kļūdai ir `error_id`
- Kļūda neizraisa noklusējuma WAIT
- Kļūda neizraisa noklusējuma trade

### 27.3. Moduļu specifiskā recovery

| Modulis | Recovery |
|---------|----------|
| Loader | Gaida nākamo faila versiju |
| Validator | Atmet bojātu failu |
| Execution | Gaida ACK vai timeout |
| ACK Reader | Atzīmē timeout kā execution kļūdu |

---

## 28. Failu validācija

### 28.1. Validācijas objekts

Fails tiek validēts pirms satura izmantošanas.

### 28.2. Validācijas pārbaudes

- Fails eksistē
- Fails ir nolasāms
- Paplašinājums atbilst tipam
- JSON ir derīgs un parsējams
- CSV satur obligātās kolonnas
- `schema_version` ir atbalzīta
- `timeframe` ir `M1` market datos
- Instance lauki atbilst gaidītajai instance

### 28.3. Validācijas iznākums

| Rezultāts | Nozīme |
|-----------|--------|
| VALID | Fails tiek apstrādāts |
| INVALID | Fails tiek noraidīts, error journal |

### 28.4. Atbildīgie moduļi

Failu līmeņa struktūras validāciju veic atbilstošais validator modulis. Protokola lauku validāciju veic `protocol/parser.py`.

---

## 29. Datu validācija

### 29.1. Market datu validācija

- `high >= max(open, close, low)`
- `low <= min(open, close, high)`
- `time_utc` ir augošs
- Nav dublikātu laiku
- `digits` un `point` ir pozitīvi
- Cenas nav nulles vai negatīvas

### 29.2. Sensor datu validācija

- `ask >= bid`
- `spread == ask - bid` ar pieļaujamo floating point toleranci
- `spread_points` atbilst `spread / point`

### 29.3. Status datu validācija

- `balance` un `equity` nav NaN
- `connected` ir boolean

### 29.4. Universe datu validācija

- Nav aizliegtu lauku, kas ietver trade signālus
- `market_regime` ir no atļautā kopa

### 29.5. Sekas

Nederīgi dati izraisa trade apturēšanu šim ciklam un error journal ierakstu.

---

## 30. Datu normalizācija

### 30.1. Normalizācijas mērķis

Pārveidot validētus ārējos datus uz iekšējiem `protocol/models.py` objektiem ar konsekventām vienībām un precizitāti.

### 30.2. Market normalizācija

- Laiki tiek konvertēti uz UTC datetime
- Cenas tiek saglabātas ar pareizo `digits` precizitāti
- Tiek pievienots iekšējais `bar_index`

### 30.3. Sensor normalizācija

- Spread tiek normalizēts gan cenās, gan punktos
- Tiek aprēķināts `relative_spread` pret spread modeli

### 30.4. Instrumentu parametru ieguve

No pirmā derīgā market ieraksta tiek iegūti `digits` un `point`. Tie tiek atjaunināti, ja MT4 eksportā mainās.

### 30.5. Normalizācijas modulis

`engine/normalizer/market_normalizer.py` atbild par market un sensor normalizāciju. `spread_model.py` atbild par spread statistikas atjaunināšanu.

---

## 31. Market Loader

### 31.1. Atbildība

`engine/loader/market_loader.py` nolasa `market_{symbol}_{magic}.csv` no diska un atgriež neapstrādātu tabulu vai rindu kopu parserim.

### 31.2. Ievade

- `account_id`
- `symbol`
- `magic`
- Ceļš no `paths.py`

### 31.3. Izvade

Neapstrādāts market datu objekts ar faila metadatiem: `file_path`, `modified_utc`, `row_count`.

### 31.4. Noteikumi

- Loader nevalidē saturu
- Loader neanalizē cenas
- Loader izmanto cache hash, lai izvairītos no liekas pārlasīšanas
- IO kļūdas tiek propagētas bez slēpšanas

---

## 32. Sensor Loader

### 32.1. Atbildība

`engine/loader/sensor_loader.py` nolasa `sensor_{symbol}_{magic}.csv`.

### 32.2. Izvade

Neapstrādāts sensor datu objekts ar pēdējo rindu un vēstures rindām.

### 32.3. Noteikumi

Identiski Market Loader principiem: tikai ielāde, bez validācijas un analīzes.

---

## 33. Status Loader

### 33.1. Atbildība

`engine/loader/status_loader.py` nolasa `status_{account_id}.json`.

### 33.2. Izvade

Neapstrādāts JSON teksts vai bytes objekts parserim.

### 33.3. Konta līmeņa raksturs

Status fails ir konta līmenī, ne instance līmenī. Visas konta instances izmanto vienu status ielādi ciklā.

---

## 34. Universe Loader

### 34.1. Atbildība

`engine/loader/universe_loader.py` nolasa `universe.json` no konta mapes vai `data/universe/universe.json` atkarībā no konfigurācijas.

### 34.2. Izvade

Neapstrādāts universe JSON.

### 34.3. Noteikums

Universe loader nekad netiek izsaukts kā trade trigger. Tas tiek ielādēts konteksta papildināšanai pirms analīzes.

---

## 35. Market Validator

### 35.1. Atbildība

`engine/validator/market_validator.py` validē market CSV struktūru un saturu saskaņā ar 20.1 un 29.1.

### 35.2. Izvade

`ValidationResult` ar statusu VALID vai INVALID un kļūdu sarakstu.

### 35.3. Sekas

INVALID rezultāts aptur instance ciklu un izraisa error journal ierakstu.

---

## 36. Sensor Validator

### 36.1. Atbildība

`engine/validator/sensor_validator.py` validē sensor CSV saskaņā ar 20.2 un 29.2.

### 36.2. Saistība ar spread

Sensor validator nodrošina, ka spread vērtības ir matemātiski konsekventas pirms spread modeļa atjaunināšanas.

---

## 37. Universe Validator

### 37.1. Atbildība

`engine/validator/universe_validator.py` validē universe JSON saskaņā ar 19.3 un 29.4.

### 37.2. Trade signālu aizliegums

Ja universe satur jebkuru aizliegtu trade signāla lauku, validators atgriež INVALID un pieraksta PROTOCOL kļūdu.

### 37.3. Status Validator

`engine/validator/status_validator.py` validē status JSON saskaņā ar 19.2 un 29.3. Tas ir konta līmeņa validators, kas darbojas pirms jebkuras instance apstrādes.

---

## 38. Spread modelis

### 38.1. Mērķis

Uzturēt katras instances dinamisko spread normu un aprēķināt pašreizējā spread relatīvo novērtējumu.

### 38.2. Aprēķins

`engine/normalizer/spread_model.py` uztur:

- `mean_spread` — vidējais no vēstures
- `std_spread` — standartnovirze
- `median_spread` — mediāna
- `relative_spread` — `(current_spread - mean_spread) / std_spread`, ja `std_spread > 0`, citādi `0`

### 38.3. Vēstures logs

Spread vēsture tiek uzturēta `SpreadState` ar konfigurējamu izmēru no `analysis.lookback_bars` vai atsevišķa spread parametra.

### 38.4. Aizliegumi

- Nav cietu max spread sliekšņu
- Nav globālu spread limitu vairākiem instrumentiem
- Spread modelis neizraisa trade — tikai nodrošina datus spread filtram un analīzei

### 38.5. Persistēšana

Spread kopsavilkums tiek rakstīts `spread_{symbol}_{magic}.json` pēc katra veiksmīga sensor normalizācijas cikla.

---

## 39. Instrumentu parametru noteikšana

### 39.1. Avoti

Instrumentu parametri nāk tikai no MT4 eksporta:

- `symbol` no faila nosaukuma un rindas lauka
- `digits` no market vai sensor CSV
- `point` no market vai sensor CSV
- `pip` tiek aprēķināts dinamiski

### 39.2. Pip aprēķins

| Digits | Pip definīcija |
|--------|----------------|
| 3 vai 5 | `pip = point * 10` |
| Citi | `pip = point` |

Pip vērtība tiek pārrēķināta, ja mainās `digits`. Sistēma neuzglabā cietu pip vērtību konfigurācijā.

### 39.3. Parametru atjaunināšana

Ja jaunā eksporta datos `digits` vai `point` atšķiras no state, sistēma atjaunina parametrus, pieraksta notikumu error vai system logā atkarībā no būtiskuma, un nepārtrauc darbu, ja dati ir konsekventi validēti.

### 39.4. Atbildīgais modulis

Normalizators iegūst parametrus. State glabā pašreizējās vērtības instance kontekstā.

---

## 40. Analysis Engine

### 40.1. Mērķis

Apvienot analītisko moduļu izvades vienotā analīzes kontekstā bez trade lēmuma.

### 40.2. Ievade

- Normalizēti M1 dati
- Spread modelis
- Universe konteksts
- Instance state

### 40.3. Izvade

`AnalysisContext` objekts ar šādiem komponentiem:

- `momentum`
- `trend`
- `structure`
- `pressure`
- `context`
- `behavior`
- `impact`

### 40.4. Secība

1. Context analīze
2. Structure analīze
3. Momentum un Trend analīze
4. Pressure analīze
5. Behavior analīze
6. Impact analīze

Secība ir fiksēta. Katrs modulis raksta savā apakšobjektā.

### 40.5. Aizliegumi

Analysis Engine neizsauc Decision Engine. Analysis Engine nepiemēro risku.

---

## 41. Momentum analīze

### 41.1. Modulis

`engine/analysis/momentum.py`

### 41.2. Mērķis

Novērtēt īstermiņa cenu impulsu M1 datos.

### 41.3. Ievade

Normalizētas M1 sveces, `lookback_bars` no konfigurācijas.

### 41.4. Izvade

| Lauks | Apraksts |
|-------|----------|
| `momentum_score` | Skalārs impulsa vērtējums no -1 līdz 1 |
| `momentum_direction` | UP, DOWN, NEUTRAL |
| `rate_of_change` | Cenas izmaiņu temps |
| `acceleration` | Impulsa paātrinājums |

### 41.5. Loma lēmumos

Momentum neizdala BUY vai SELL atsevišķi. Tas nodrošina ievadi abu virzienu aprēķinam Decision Engine.

---

## 42. Trend analīze

### 42.1. Modulis

Trend analīze tiek īstenota `engine/analysis/momentum.py` un `engine/analysis/structure.py` sadarbībā, bet loģiski atgriež atsevišķu `trend` objektu Analysis Engine izvadē.

### 42.2. Mērķis

Identificēt dominējošo virzienu M1 ietvaros.

### 42.3. Izvade

| Lauks | Apraksts |
|-------|----------|
| `trend_direction` | UP, DOWN, SIDEWAYS |
| `trend_strength` | Skalārs no 0 līdz 1 |
| `trend_duration_bars` | Ilgums bāros |
| `higher_highs` | boolean |
| `lower_lows` | boolean |

### 42.4. Noteikums

Trend analīze neizslēdz ne BUY, ne SELL. Tā informē scoring.

---

## 43. Structure analīze

### 43.1. Modulis

`engine/analysis/structure.py`

### 43.2. Mērķis

Identificēt cenu struktūru: swing augstumus, zemumus, atbalstu un pretestību.

### 43.3. Izvade

| Lauks | Apraksts |
|-------|----------|
| `swing_high` | Pēdējā swing augstuma cena |
| `swing_low` | Pēdējā swing zemuma cena |
| `structure_bias` | BULLISH, BEARISH, NEUTRAL |
| `break_of_structure` | boolean |
| `support_level` | Cena |
| `resistance_level` | Cena |

---

## 44. Pressure analīze

### 44.1. Modulis

`engine/analysis/pressure.py`

### 44.2. Mērķis

Novērtēt pircēju un pārdevēju spiedienu no M1 sveču ķermeņiem, ēnām un close pozīcijas.

### 44.3. Izvade

| Lauks | Apraksts |
|-------|----------|
| `buy_pressure` | Skalārs 0 līdz 1 |
| `sell_pressure` | Skalārs 0 līdz 1 |
| `pressure_delta` | buy_pressure - sell_pressure |
| `absorption_detected` | boolean |

---

## 45. Context analīze

### 45.1. Modulis

`engine/analysis/context.py`

### 45.2. Mērķis

Apvienot universe kontekstu ar lokālo M1 stāvokli.

### 45.3. Ievade

Universe JSON, session, market_regime, news_window_active.

### 45.4. Izvade

| Lauks | Apraksts |
|-------|----------|
| `session` | Pašreizējā sesija |
| `regime` | Tirgus režīms |
| `news_active` | boolean |
| `context_quality` | Skalārs 0 līdz 1 cik uzticams konteksts |
| `trade_environment` | FAVORABLE, NEUTRAL, HOSTILE |

### 45.5. Noteikums

Context analīze nekad netirgo. `HOSTILE` vide neizraisa automātisku BLOCK — tas tiek nodots risk un filtru moduļiem.

---

## 46. Scoring sistēma

### 46.1. Modulis

`engine/decision/scorer.py`

### 46.2. Mērķis

Salīdzināt BUY un SELL kandidātu vērtības, nevis filtrēt signālus.

### 46.3. Ievade

- BUY kandidāta komponentu vērtības
- SELL kandidāta komponentu vērtības
- Analysis context

### 46.4. Izvade

| Lauks | Apraksts |
|-------|----------|
| `buy_score` | Kopējais BUY vērtējums |
| `sell_score` | Kopējais SELL vērtējums |
| `score_delta` | buy_score - sell_score |
| `preferred_side` | BUY, SELL, NONE |

### 46.5. Scoring svars

Svaru koeficienti nāk no `config/system.json` sadaļas `analysis.weights`:

- momentum
- trend
- structure
- pressure
- behavior
- impact
- context

Svari ir konfigurējami, bet nekad neizslēdz obligāto abu virzienu aprēķinu.

### 46.6. Noteikums

Scoring nav filtrs. Scoring nevar atgriezt BLOCK. Scoring nevar izlaist SELL pārbaudi.

---

## 47. BUY aprēķins

### 47.1. Modulis

`engine/decision/engine.py` — BUY aprēķina funkcija

### 47.2. Mērķis

Noteikt, vai BUY setup ir derīgs un aprēķināt tā komponentes.

### 47.3. Ievade

Analysis context, spread novērtējums, volatility novērtējums, instance state.

### 47.4. Izvade

`BuyCandidate` objekts:

| Lauks | Apraksts |
|-------|----------|
| `valid` | boolean |
| `invalid_reason` | string ja valid ir false |
| `entry_price` | Aprēķinātā ieejas cena |
| `stop_loss` | SL cena |
| `take_profit` | TP cena |
| `component_scores` | Komponentu vērtības |
| `buy_score` | Kopējais BUY score |

### 47.5. Noteikums

Ja `valid` ir false, `invalid_reason` ir obligāts. BUY aprēķins neizraisa automātisku SELL, bet Decision Engine obligāti turpina ar SELL.

---

## 48. SELL aprēķins

### 48.1. Modulis

`engine/decision/engine.py` — SELL aprēķina funkcija

### 48.2. Izvade

`SellCandidate` objekts ar identisku struktūru kā BuyCandidate, bet SELL semantikā.

### 48.3. Noteikums

SELL aprēķins vienmēr tiek veikts pat tad, ja BUY ir derīgs. Ja SELL neder, `invalid_reason` ir obligāts.

---

## 49. BUY pret SELL salīdzināšana

### 49.1. Secība

1. Aprēķina BUY kandidātu
2. Aprēķina SELL kandidātu
3. Ja abi `valid`, Scorer salīdzina `buy_score` un `sell_score`
4. Augstākais score nosaka `preferred_side`
5. Ja tikai viens ir `valid`, `preferred_side` ir derīgais virziens
6. Ja neviens nav `valid`, rezultāts ir WAIT ar abu `invalid_reason` apkopojumu

### 49.2. Neizšķirta situācija

Ja abi ir `valid` un score ir vienāds, `preferred_side` ir NONE un gala lēmums ir WAIT ar reason `EQUAL_SCORES`.

### 49.3. Riska posms

Pēc salīdzināšanas `preferred_side` tiek nodots Risk Engine. Risk Engine nemaina `preferred_side`, tikai ALLOW vai BLOCK.

---

## 50. WAIT loģika

### 50.1. WAIT nosacījumi

WAIT tiek pieņemts tikai šajos gadījumos:

| Nosacījums | Reason kods |
|------------|-------------|
| BUY un SELL abi nederīgi | `BOTH_DIRECTIONS_INVALID` |
| Abi derīgi, vienādi score | `EQUAL_SCORES` |
| Abi derīgi, bet risks bloķē abus virzienus | `RISK_BLOCKED_ALL` netiek izmantots — risks dod BLOCK, ne WAIT |
| Derīgs virziens, bet execution nav iespējams tehnisku iemeslu dēļ | `EXECUTION_NOT_POSSIBLE` |

### 50.2. WAIT aizliegumi

- WAIT nedrīkst būt noklusējums datu trūkuma gadījumā — datu trūkums ir kļūda
- WAIT nedrīkst aizstāt nepārbaudītu SELL vai BUY
- WAIT nedrīkst tikt izvēlēts, ja viens virziens ir derīgs un risks ir ALLOW

### 50.3. WAIT reason

Katrā WAIT ir pilns reason ar vismaz divām daļām: galvenais iemesls un detaļa.

---

## 51. BLOCK loģika

### 51.1. BLOCK avoti

| Avots | Reason piemērs |
|-------|----------------|
| Risk Engine | `RISK_MAX_DRAWDOWN` |
| Risk Engine | `RISK_DAILY_LOSS` |
| Risk Engine | `RISK_MAX_POSITIONS` |
| Spread filtrs | `SPREAD_ABNORMAL` |
| Volatility filtrs | `VOLATILITY_ABNORMAL` |
| News filtrs | `NEWS_WINDOW_ACTIVE` |
| Status | `ACCOUNT_NOT_TRADEABLE` |
| Validācija | `DATA_INVALID` |

### 51.2. BLOCK un Risk Engine

Risk Engine ir galvenais BLOCK avots pēc scoring. Filtri pirms scoring var atzīmēt vidi kā nepiemērotu, bet gala BLOCK riska slānī joprojām ir ALLOW vai BLOCK.

### 51.3. BLOCK sekas

- Trade nenotiek
- Decision journal ieraksta BLOCK ar reason
- Control tiek rakstīts ar `action: NONE` ja nepieciešams MT4 informēšanai

### 51.4. BLOCK un WAIT

BLOCK nav WAIT. Ja risks bloķē, rezultāts ir BLOCK, nevis WAIT.

---

## 52. Decision Engine

### 52.1. Modulis

`engine/decision/engine.py`

### 52.2. Atbildība

Orķestrēt BUY aprēķinu, SELL aprēķinu, scoring, reason ģenerēšanu un gala lēmuma izveidi.

### 52.3. Izvade

`DecisionResult`:

| Lauks | Apraksts |
|-------|----------|
| `decision_id` | UUID |
| `decision` | BUY, SELL, WAIT, BLOCK |
| `reason` | Pilns reason |
| `preferred_side` | BUY, SELL, NONE |
| `buy_candidate` | BuyCandidate |
| `sell_candidate` | SellCandidate |
| `buy_score` | number |
| `sell_score` | number |

### 52.4. Reason modulis

`engine/decision/reason.py` ģenerē standartizētus reason stringus no reason kodiem un parametriem.

### 52.5. Aizliegumi

Decision Engine neizsauc MT4. Decision Engine nepiemēro position sizing — to dara Risk Engine.

---

## 53. Risk Engine

### 53.1. Modulis

`engine/risk/engine.py` un `engine/risk/rules.py`

### 53.2. Atbildība

Piemērot riska noteikumus un atgriezt tikai ALLOW vai BLOCK.

### 53.3. Ievade

- DecisionResult ar preferred_side
- Instance state
- Status dati
- Konfigurācijas risk parametri

### 53.4. Izvade

`RiskResult`:

| Lauks | Apraksts |
|-------|----------|
| `result` | ALLOW vai BLOCK |
| `reason` | Obligāts ja BLOCK |
| `position_size` | Aprēķinātais tilpums ja ALLOW |
| `stop_loss` | Validēts SL |
| `take_profit` | Validēts TP |

### 53.5. Aizliegumi

Risk Engine nedrīkst:

- Pieņemt BUY vai SELL
- Mainīt preferred_side
- Atgriezt WAIT
- Ignorēt status `trade_allowed: false`

---

## 54. Position Sizing

### 54.1. Atbildība

Risk Engine aprēķina pozīcijas lielumu, ja risks ir ALLOW.

### 54.2. Ievade

- Konta `equity` no status
- `risk.max_risk_per_trade_percent` no konfigurācijas
- Attālums līdz stop loss punktos
- `point` un `pip` no instrumenta parametriem

### 54.3. Aprēķins

```
risk_amount = equity * (max_risk_per_trade_percent / 100)
volume = risk_amount / (stop_loss_distance_points * point_value_per_lot)
```

`point_value_per_lot` tiek noteikts dinamiski no MT4 status vai konfigurācijas formula parametriem bez cietiem symbol parametriem.

### 54.4. Normalizācija

Tilpums tiek noapaļots uz MT4 atļauto soli, kas nāk no status vai konfigurācijas `volume_step`, nevis no cietas tabulas.

### 54.5. Aizliegumi

Position sizing nekad nedrīkst ignorēt SL attālumu. Nulles vai negatīvs tilpums izraisa BLOCK.

---

## 55. Stop Loss

### 55.1. Avots

Stop Loss cenu initially nosaka Decision Engine no structure analīzes:

- BUY: zemāk par pēdējo swing low ar konfigurētu buffer
- SELL: augstāk par pēdējo swing high ar buffer

### 55.2. Risk validācija

Risk Engine validē, ka SL attālums nepārsniedz `risk.max_stop_loss_pips` konfigurācijas vērtību, kas ir relatīva pret instrumenta pip, nevis cietu punktu skaitli simbolam.

### 55.3. MODIFY

Atvērtas pozīcijas SL maiņu var veikt Trade Management ciklā caur MODIFY komandu.

---

## 56. Take Profit

### 56.1. Avots

Take Profit tiek noteikts no risk/reward attiecības:

```
take_profit_distance = stop_loss_distance * risk.reward_ratio
```

`risk.reward_ratio` nāk no konfigurācijas.

### 56.2. Virzienu specifika

- BUY: `take_profit = entry_price + take_profit_distance`
- SELL: `take_profit = entry_price - take_profit_distance`

### 56.3. Risk validācija

Risk Engine validē TP esamību pirms ALLOW. Trūkstošs TP izraisa BLOCK ar reason `MISSING_TAKE_PROFIT`.

---

## 57. Trade Management

### 57.1. Mērķis

Pārvaldīt atvērtās pozīcijas pēc izpildes bez jauna virziena lēmuma, ja konfigurācija to atļauj.

### 57.2. Funkcijas

| Funkcija | Apraksts |
|----------|----------|
| Breakeven | SL pārvietošana uz entry pēc konfigurēta progressa |
| Trailing stop | SL seko cenai pēc struktūras noteikumiem |
| Partial close | Daļēja pozīcijas aizvēršana |
| Time stop | Aizvēršana pēc maksimāla M1 bāru skaita |

### 57.3. Moduļa vieta

Trade Management loģika atrodas `engine/risk/trade_management.py` un tiek izsaukta no `engine/core/cycle.py` trade management fāzē. Izpilde notiek caur Execution Engine ar MODIFY vai CLOSE komandām.

### 57.4. Noteikums

Trade Management neveic jaunu BUY/SELL bez pilna lēmumu cikla, izņemot breakeven un trailing, kas ir esošās pozīcijas pārvaldība.

---

## 58. Spread filtrs

### 58.1. Mērķis

Novērtēt, vai pašreizējais spread ir normāls attiecībā pret instances spread modeli.

### 58.2. Aprēķins

```
spread_acceptable = relative_spread <= config.analysis.spread_relative_threshold
```

Slieksnis ir relatīvs pret standartnovirzi, nevis absolūts punktu skaits.

### 58.3. Izvade

Ja spread nav pieņemams, analīzes kontekstā tiek atzīmēts `spread_filter_passed: false`. Decision Engine var atzīmēt virzienu kā nederīgu ar reason `SPREAD_ABNORMAL`.

### 58.4. Aizliegumi

Nav cietu max spread skaitļu. Nav globālu spread tabulu.

---

## 59. Volatility filtrs

### 59.1. Mērķis

Novērtēt M1 volatilitāti attiecībā pret instances vēsturisko volatilitāti.

### 59.2. Aprēķins

Volatilitāte tiek mērīta kā ATR ekvivalents M1 datos no pēdējiem `lookback_bars`. Relatīvā volatilitāte:

```
relative_volatility = current_atr / mean_atr
```

### 59.3. Slieksnis

`config.analysis.volatility_relative_threshold` nosaka augšējo relatīvo robežu. Tā ir konfigurējama, bet nav cieti piesaistīta simbolam.

### 59.4. Sekas

Ja volatilitāte ir pārāk augsta, virziens tiek atzīmēts kā nederīgs ar reason `VOLATILITY_ABNORMAL`. Tas nav automātisks BLOCK, ja otrs virziens joprojām ir derīgs.

---

## 60. News filtrs

### 60.1. Avots

`universe.news_window_active` un `universe.news_impact_level`.

### 60.2. Darbība

Ja `news_window_active` ir true un `news_impact_level` ir `high`, abi virzieni tiek atzīmēti kā nederīgi ar reason `NEWS_WINDOW_ACTIVE`, ja konfigurācija `analysis.block_high_impact_news` ir true.

### 60.3. Noteikums

News filtrs nekad netirgo pretējā virzienā. Tas tikai ietekmē derīgumu. Universe joprojām ir konteksts, ne trade job.

---

## 61. Universe izmantošana

### 61.1. Atļautā izmantošana

- Session un režīma noteikšana context analīzē
- News filtra informācija
- Korrelāciju grupu informācija lēmumu kvalitātes novērtējumā
- `trade_environment` vērtības noteikšana

### 61.2. Aizliegtā izmantošana

- Tieša trade signāla nolasīšana
- Universe kā orderu trigger
- Universe kā scoring aizstājējs
- Universe kā riska aizstājējs

### 61.3. Moduļa plūsma

Universe Loader → Universe Validator → Context analīze → Analysis Engine

---

## 62. Journal sistēma

### 62.1. Mērķis

Nodrošināt pilnīgu auditu visiem lēmumiem, darījumiem un kļūdām.

### 62.2. Journal veidi

| Žurnāls | Fails | Saturs |
|---------|-------|--------|
| Decision | `decision_*.jsonl` | Visi lēmumi |
| Trade | `trade_*.jsonl` | Visi orderu notikumi |
| Error | `error_*.jsonl` | Visas kļūdas |

### 62.3. Obligātums

Katrs lēmumu cikls ar gala rezultātu rada decision journal ierakstu. Katrs execution notikums rada trade journal ierakstu. Katra kļūda rada error journal ierakstu.

### 62.4. Formāts

JSONL — viena JSON rinda uz ierakstu. Append-only.

### 62.5. Rotācija

Pēc `journal.retention_days` vecie ieraksti tiek pārvietoti uz `data/history/`.

---

## 63. Decision Journal

### 63.1. Modulis

`engine/journal/decision_journal.py`

### 63.2. Atbildība

Rakstīt katru `DecisionResult` uz `decision_{symbol}_{magic}.jsonl`.

### 63.3. Obligātie lauki

Definēti 19.8 sadaļā. Papildus ierakstā tiek glabāts pilns `reason` un `risk_result`.

### 63.4. Rakstīšanas moments

Tūlīt pēc Decision Engine un Risk Engine pabeigšanas, pirms Execution.

---

## 64. Trade Journal

### 64.1. Modulis

`engine/journal/trade_journal.py`

### 64.2. Atbildība

Rakstīt visus execution notikumus: OPEN, MODIFY, CLOSE un to ACK rezultātus.

### 64.3. Obligātie lauki

Definēti 19.9 sadaļā.

### 64.4. Rakstīšanas moments

- Pirms control rakstīšanas — OPEN/MODIFY/CLOSE intent
- Pēc ACK nolasīšanas — gala rezultāts ar `ack_status`

---

## 65. Error Journal

### 65.1. Modulis

`engine/journal/error_journal.py`

### 65.2. Atbildība

Rakstīt visas kļūdas ar moduli, tipu un kontekstu.

### 65.3. Obligātie lauki

Definēti 19.10 sadaļā.

### 65.4. Rakstīšanas moments

Tūlīt pēc kļūdas konstatēšanas jebkurā modulī.

---

## 66. Dashboard

### 66.1. Entry point

`dashboard.py` inicializē dashboard procesu.

### 66.2. Modulis

`engine/dashboard/console.py`

### 66.3. Attēlojamie dati

| Datu grupa | Avots |
|------------|-------|
| Aktīvās instances | config + state |
| Pēdējais lēmums | decision journal |
| Pēdējais reason | decision journal |
| Risk status | pēdējais decision journal |
| Spread relatīvais | spread state |
| Atvērtā pozīcija | instance state |
| Pēdējais ACK | ack fails |
| Pēdējās kļūdas | error journal |

### 66.4. Aizliegumi

Dashboard neveic analīzi, scoring, riska aprēķinu vai control rakstīšanu.

---

## 67. Live monitorings

### 67.1. Mērķis

Reāllaika operacionālā pārraudzība bez iejaukšanās lēmumu procesā.

### 67.2. Monitorētie signāli

| Signāls | Apraksts |
|---------|----------|
| Cycle latency | Laiks no market faila līdz decision |
| ACK latency | Laiks no control līdz ACK |
| Error rate | Kļūdu skaits laika vienībā |
| Instance health | VALID/BLOCKED/ERROR stāvoklis |
| Data freshness | Vecums kopš pēdējā market atjauninājuma |

### 67.3. Implementācija

Live monitoring dati tiek rakstīti `data/logs/system_{date}.log` un attēloti dashboard. Atsevišķs monitoring process nav obligāts — tas ir daļa no `run_live.py` metrikām.

### 67.4. Slieksņi

Brīdinājumi tiek ģenerēti, ja `data freshness` pārsniedz `runtime.data_stale_threshold_ms` no konfigurācijas.

---

## 68. Alert sistēma

### 68.1. Mērķis

Informēt operatoru par kritiskiem notikumiem.

### 68.2. Alert līmeņi

| Līmenis | Notikumi |
|---------|----------|
| INFO | Startup, shutdown |
| WARNING | Data stale, retry |
| ERROR | Validation failure, ACK timeout |
| CRITICAL | Account not tradeable, process crash |

### 68.3. Alert kanāli

Sākotnēji alerti tiek rakstīti log failā un attēloti dashboard. Nākotnes paplašinājumi var pievienot ārējos kanālus bez arhitektūras maiņas.

### 68.4. Alert noteikums

Alert neizraisa trade un nemaina lēmumus.

---

## 69. Performance monitorings

### 69.1. Mērķis

Mērīt sistēmas veiktspēju ilgtermiņa stabilītātei.

### 69.2. Metrikas

| Metrika | Apraksts |
|---------|----------|
| `cycle_duration_ms` | Pilna instance cikla ilgums |
| `load_duration_ms` | Loader posma ilgums |
| `analysis_duration_ms` | Analysis posma ilgums |
| `decision_duration_ms` | Decision posma ilgums |
| `io_wait_ms` | Gaidīšana uz failiem |
| `memory_rss_mb` | Procesa atmiņa |

### 69.3. Glabāšana

Metrikas tiek rakstītas periodiski system logā ar konfigurējamu intervālu `runtime.metrics_interval_ms`.

### 69.4. Izmantošana

Performance dati tiek izmantoti tikai novērošanai. Tie neietekmē lēmumus.

---

## 70. Memory pārvaldība

### 70.1. Modulis

`engine/state/memory.py`

### 70.2. Mērķis

Pārvaldīt in-memory cache struktūras instances ietvaros.

### 70.3. Glabātie objekti

- Pēdējās M1 sveces limits `lookback_bars`
- Sensor vēsture spread modelim
- Pēdējais AnalysisContext
- Pēdējais DecisionResult

### 70.4. Atmiņas robežas

Vēstures garums ir konfigurējams un fiksēts. Sistēma neuzkrāj neierobežotu datu daudzumu.

### 70.5. Tīrīšana

Instance deaktivizācijas laikā atmiņa tiek atbrīvota. Globālie objekti netiek izmantoti starp instances.

---

## 71. Cache sistēma

### 71.1. Mērķis

Samazināt liešu diska I/O, izmantojot failu hash salīdzināšanu.

### 71.2. Ceļš

`data/cache/{account_id}/{symbol}_{magic}/`

### 71.3. Faili

- `last_market.hash` — SHA256 no market CSV satura
- `last_sensor.hash` — SHA256 no sensor CSV satura

### 71.4. Darbība

Ja hash nav mainījies, loader izlaiž pārlasīšanu. Ja mainījies, ielādē un atjaunina hash.

### 71.5. Invalidācija

Startup un recovery laikā hash tiek salīdzināts ar faila modified time. Ja konflikts, prioritāte ir faila saturs.

---

## 72. State sistēma

### 72.1. Moduļi

- `engine/state/instance_state.py`
- `engine/state/spread_state.py`
- `engine/state/memory.py`

### 72.2. Mērķis

Uzturēt konsekventu instances operacionālo stāvokli starp cikliem.

### 72.3. Instance state saturs

| Lauks | Apraksts |
|-------|----------|
| `last_decision` | Pēdējais lēmums |
| `last_reason` | Pēdējā reason |
| `open_ticket` | Atvērtais tickets |
| `position_side` | BUY vai SELL |
| `position_volume` | Tilpums |
| `last_command_id` | Pēdējā control komanda |
| `last_ack_status` | Pēdējais ACK |
| `instrument_digits` | Pašreizējie digits |
| `instrument_point` | Pašreizējais point |
| `instrument_pip` | Pašreizējais pip |
| `cycle_count` | Izieto ciklu skaits |

### 72.4. Persistēšana

State tiek rakstīts uz disku pēc katra cikla un shutdown laikā.

---

## 73. Instance Memory

### 73.1. Definīcija

Instance Memory ir in-memory reprezentācija `InstanceState` un `SpreadState` objektiem, ko pārvalda `memory.py`.

### 73.2. Dzīves cikls

1. Izveide startup laikā
2. Atjaunināšana katrā ciklā
3. Persistēšana uz disku
4. Atjaunošana recovery laikā
5. Atbrīvošana deaktivizācijā

### 73.3. Izolācija

Katram `instance_key` ir atsevišķs memory konteiners. Nav globāla koplietota state vārdnīca bez instance atslēgas.

---

## 74. Execution Engine

### 74.1. Modulis

`engine/execution/` — `command.py`, `control_writer.py`, `ack_reader.py`

### 74.2. Mērķis

Pārvērst gala lēmumu par MT4 izpildāmu komandu un apstrādāt ACK.

### 74.3. Secība

1. Saņem `DecisionResult` un `RiskResult`
2. Ja `ALLOW` un lēmums ir BUY vai SELL, `command.py` veido `OrderCommand`
3. `control_writer.py` raksta control failu atomiski
4. Gaida ACK ar timeout
5. `ack_reader.py` nolasa un validē ACK
6. Atjaunina state un trade journal

### 74.4. Aizliegumi

Execution Engine neveic analīzi un nepieņem lēmumus.

---

## 75. Order Command

### 75.1. Modulis

`engine/execution/command.py`

### 75.2. Objekts

`OrderCommand`:

| Lauks | Apraksts |
|-------|----------|
| `command_id` | UUID |
| `action` | OPEN, MODIFY, CLOSE, NONE |
| `side` | BUY, SELL |
| `volume` | Lotes |
| `stop_loss` | SL cena |
| `take_profit` | TP cena |
| `ticket` | Esošais tickets MODIFY/CLOSE |
| `reason` | Lēmuma reason |
| `decision_id` | Saite uz decision |

### 75.3. NONE action

Ja lēmums ir WAIT vai BLOCK, `action` ir NONE. Control fails joprojām var tikt rakstīts informācijas sinhronizācijai ar `reason`.

---

## 76. Control faili

### 76.1. Modulis

`engine/execution/control_writer.py`

### 76.2. Rakstīšanas process

1. Serializē `OrderCommand` uz JSON
2. Pievieno `schema_version`, `timestamp_utc`, instance laukus
3. Raksta uz `control_{symbol}_{magic}.json.tmp`
4. `fsync`
5. Atomic rename uz `control_{symbol}_{magic}.json`

### 76.3. Lasīšana

Tikai MT4 EA lasa control failu. Python to nepārraksta pēc rakstīšanas, izņemot retry scenārijus ar jaunu `command_id`.

---

## 77. ACK sistēma

### 77.1. Modulis

`engine/execution/ack_reader.py`

### 77.2. Mērķis

Apstiprināt, ka MT4 izpildīja vai noraidīja komandu.

### 77.3. Validācija

- `command_id` atbilst gaidītajam
- `account_id`, `symbol`, `magic` atbilst instance
- `status` ir no atļautā kopa

### 77.4. Sekas

| ACK status | Darbība |
|------------|---------|
| SUCCESS | State atjaunināšana, trade journal SUCCESS |
| FAILED | State atjaunināšana, trade journal FAILED, error journal |
| REJECTED | State bez pozīcijas maiņas, error journal |

### 77.5. ACK timeout

Ja ACK nav saņemts `runtime.ack_timeout_ms` laikā, tiek aktivizēta timeout loģika (79. sadaļa).

---

## 78. Retry loģika

### 78.1. Attiecas uz

- IO operācijām
- ACK gaidīšanu
- Īslaicīgiem failu piekļuves konfliktiem

### 78.2. Parametri

- `runtime.retry_max` — maksimālais mēģinājumu skaits
- `runtime.retry_delay_ms` — pauze starp mēģinājumiem

### 78.3. Retry un execution

Control komandas netiek atkārtotas ar vienu un to pašu `command_id`. Ja ACK timeout, jauns execution cikls prasa jaunu lēmumu un jaunu `command_id`.

### 78.4. Retry un kļūdas

Pēc `retry_max` sasniegšanas kļūda tiek pierakstīta error journal un modulis atgriež kļūdu bez silent exception.

---

## 79. Timeout loģika

### 79.1. Timeout veidi

| Timeout | Parametrs |
|---------|-----------|
| ACK gaidīšana | `runtime.ack_timeout_ms` |
| Data stale | `runtime.data_stale_threshold_ms` |
| Cycle maksimums | `runtime.cycle_max_duration_ms` |

### 79.2. ACK timeout sekas

1. Atzīmē komandu kā neapstiprinātu
2. Pieraksta error journal ar `ACK_TIMEOUT`
3. State `last_ack_status` = TIMEOUT
4. Nākamajā recovery cikla sākumā sinhronizē ar MT4 status

### 79.3. Data stale sekas

Instance cikls tiek izlaists ar error journal ierakstu. Trade nenotiek.

### 79.4. Cycle timeout sekas

Cikls tiek pārtraukts, state tiek daļēji persistēts, error journal pieraksta `CYCLE_TIMEOUT`.

---

## 80. Drošības principi

### 80.1. Atbildību sadalījums

Python pieņem lēmumus. MT4 izpilda. Dashboard rāda. Neviens cits ceļš nav atļauts.

### 80.2. Datu integritāte

Atomic write, validācija pirms lietošanas, append-only journal.

### 80.3. Instance izolācija

Kļūda vienā instance neizplatās uz citām.

### 80.4. Failu piekļuve

Tikai `C:\Check\System` koks. Nav ārēju ceļu rakstīšanai.

### 80.5. Konfigurācijas aizsardzība

`system.json` tiek lasīts startup laikā. Runtime izmaiņas prasa procesa restartu.

### 80.6. Kļūdu caurredzamība

Visas kļūdas journal un log. Nav silent exception.

---

## 81. Thread Safety

### 81.1. Sākotnējais modelis

`run_live.py` darbojas vienā galvenajā thread ar secīgu instance apstrādi. Dashboard ir atsevišķs process.

### 81.2. Noteikumi

- Instance state netiek koplietots starp threadiem bez lock
- Ja nākotnē tiek ieviests multi-threading, katram thread jābūt piesaistītam instance kopumam
- Globālie singleton bez lock ir aizliegti mutējamam state

### 81.3. Failu konkurence

Python un MT4 raksta dažādus failus, izņemot ACK/control pāra protokolu, kas ir secīgs.

---

## 82. File Locking

### 82.1. Pieeja

SYSTEM izmanto atomic rename kā primāro sinhronizāciju, nevis obligātu OS file lock ilgstošai turēšanai.

### 82.2. Lasīšana

Lasītājs nolasa failu tikai pēc tam, kad `.tmp` vairs neeksistē un galīgais fails ir stabils.

### 82.3. Konflikti

Ja fails ir daļēji rakstīts, validators to noraida. Retry pēc `retry_delay_ms`.

### 82.4. Windows specifika

`C:\Check\System` darbojas uz Windows. Atomic rename jāimplementē ar `os.replace` ekvivalentu Windows semantikā.

---

## 83. Atomic Write

### 83.1. Process

1. Rakstīt uz `{filename}.tmp`
2. `flush` un `fsync`
3. Atomic rename uz `{filename}`

### 83.2. Attiecas uz

- control JSON
- state JSON
- spread JSON
- status JSON (MT4 puse)
- market/sensor CSV (MT4 puse)

### 83.3. Aizliegums

Tieša rakstīšana galīgajā failā bez tmp ir aizliegta visiem moduļiem.

---

## 84. Atomic Read

### 84.1. Process

1. Pārbauda, ka `.tmp` neeksistē
2. Nolasa galīgo failu
3. Validē saturu
4. Ja invalid, nelieto datus

### 84.2. Dubultā nolasīšana

Kritiskos JSON failos pēc nolasīšanas var atkārtoti pārbaudīt `modified_utc` stabilitāti pirms parsēšanas.

---

## 85. Konfigurācijas noteikumi

### 85.1. Vienots avots

Tikai `config/system.json`.

### 85.2. Validācija startup laikā

- Visi obligātie lauki eksistē
- Tipi atbilst shēmai
- `system.timeframe` ir `M1`
- `system.root_path` atbilst faktiskajam ceļam
- Nav aizliegtu lauku (cieti spread, symbol saraksti)

### 85.3. Konfigurācijas izmaiņas

Izmaiņas stājas spēkā pēc `run_live.py` restarta.

### 85.4. Instance konfigurācija

`instances` masīvs definē aktīvās instances. Ja `auto_discover_instances` ir true, papildus tiek atklātas instances no failu sistēmas.

---

## 86. Dynamic Spread

### 86.1. Definīcija

Spread vērtējums balstās uz instances vēsturisko izkliedi, nevis fiksētu limitu.

### 86.2. Komponentes

- `current_spread` no sensor datiem
- `mean_spread`, `std_spread` no spread modela
- `relative_spread` kā standartizēts novērtējums

### 86.3. Loma

Spread filtrs, analīzes kvalitātes novērtējums, decision invalid reason.

### 86.4. Atjaunināšana

Katrs jauns sensor ieraksts atjaunina modeli, ja validācija ir VALID.

---

## 87. Dynamic Instrument Detection

### 87.1. Process

1. Konfigurācija vai auto-discovery nosaka simbolu
2. Pirmais derīgais market fails apstiprina simbolu
3. digits un point tiek iegūti no datiem
4. Instance tiek reģistrēta state sistēmā

### 87.2. Jauns instruments

Ja MT4 sāk eksportēt jaunu simbolu un konfigurācija to atļauj, sistēma izveido jaunu instance bez koda izmaiņām.

### 87.3. Aizliegums

Nav cietu symbol sarakstu, kas liegtu jaunus instrumentus.

---

## 88. Dynamic Digits

### 88.1. Avots

MT4 eksporta `digits` lauks market un sensor datos.

### 88.2. Glabāšana

`InstanceState.instrument_digits`

### 88.3. Lietošana

Cenu noapaļošana, TP/SL aprēķins, journal formātēšana.

### 88.4. Maiņa

Ja digits mainās, state tiek atjaunināts un notikums tiek žurnalēts.

---

## 89. Dynamic Point

### 89.1. Avots

MT4 eksporta `point` lauks.

### 89.2. Glabāšana

`InstanceState.instrument_point`

### 89.3. Lietošana

Spread punktos, SL/TP attālumi, position sizing.

---

## 90. Dynamic Pip

### 90.1. Aprēķins

Pip tiek noteikts no digits un point saskaņā ar 39.2 tabulu.

### 90.2. Glabāšana

`InstanceState.instrument_pip`

### 90.3. Lietošana

Risk noteikumi, kas izsakāti pip, konfigurācijas `max_stop_loss_pips` interpretācija.

---

## 91. Coding standarts

### 91.1. Valoda

Python 3.11 vai jaunāks. MQL4 MT4 pusē.

### 91.2. Stils

PEP 8 Python kodam. Moduļu garums ir fokuss, ne faila izmērs.

### 91.3. Kļūdu apstrāde

Explicit exception tipi no `protocol/errors.py`. Nav tukšu `except:`. Nav silent pass.

### 91.4. Tipizācija

Type hints visās publiskajās funkcijās.

### 91.5. Imports

Absolūti importi no `engine` pakotnes.

### 91.6. Aizliegumi

- TODO komentāri
- Placeholder implementācijas
- Lieki komentāri
- Pusgatavi faili
- Legacy compatibility kods

### 91.7. Moduļu integritāte

Katrs fails implementē pilnu savu atbildību, nevis stub.

---

## 92. Naming standarts

### 92.1. Python moduļi

`snake_case.py`

### 92.2. Python klases

`PascalCase`

### 92.3. Python funkcijas un mainīgie

`snake_case`

### 92.4. Konstantes

`UPPER_SNAKE_CASE` failā `protocol/constants.py`

### 92.5. Reason kodi

`UPPER_SNAKE_CASE` virknes, piemēram `SPREAD_ABNORMAL`

### 92.6. Failu nosaukumi

Saskaņā ar 21. sadaļu.

### 92.7. Instance atslēga

Tuple `(account_id: str, symbol: str, magic: int)`

---

## 93. Logging standarts

### 93.1. Formāts

Konfigurējams caur `logging.format`. Noklusējuma struktūra:

```
{timestamp_utc} | {level} | {module} | {account_id} | {symbol} | {magic} | {message}
```

Trūkstošie instance lauki tiek aizstāti ar `-`.

### 93.2. Līmeņi

| Līmenis | Lietojums |
|---------|-----------|
| DEBUG | Detalizēta diagnostika |
| INFO | Cikla notikumi, startup, shutdown |
| WARNING | Stale data, retry |
| ERROR | Validation, execution kļūdas |
| CRITICAL | Procesa apturēšana |

### 93.3. Noteikums

Logs neaizstāj journal. Kritiski biznesa notikumi vienmēr journal.

---

## 94. Testēšanas arhitektūra

### 94.1. Mērķis

Nodrošināt, ka katrs modulis darbojas atbilstoši specifikācijai un RULES.

### 94.2. Struktūra

```
tests/
├── protocol/
├── loader/
├── normalizer/
├── decision/
├── risk/
└── execution/
```

### 94.3. Testu dati

Testu dati atrodas testu mapēs kā fiksēti CSV un JSON faili. Tie neizmanto live `data/` mapi.

### 94.4. Testu izpilde

Standarta izpilde ar pytest no projekta saknes.

---

## 95. Unit Test

### 95.1. Mērķis

Testēt vienu moduli izolēti.

### 95.2. Obligātie testu bloki

| Modulis | Testējams |
|---------|-----------|
| protocol/parser | JSON un CSV parsēšana |
| protocol/writer | Serializācija |
| validators | VALID un INVALID scenāriji |
| normalizer | Cenu un spread normalizācija |
| spread_model | relative_spread aprēķins |
| scorer | BUY vs SELL salīdzināšana |
| reason | Reason string ģenerēšana |
| risk/rules | ALLOW un BLOCK |

### 95.3. Mocking

MT4 nav pieejams testos. Izmanto fiksētus failus un mock status datus.

---

## 96. Integration Test

### 96.1. Mērķis

Testēt moduļu ķēdi bez MT4.

### 96.2. Scenāriji

- Load → validate → normalize → analyze
- Decision → risk → journal
- Execution control write → ack read → state update

### 96.3. Datu vide

Pagaidu `tmp` direktorija ar pilnu `data/clients/{account_id}/` struktūru.

---

## 97. End-to-End Test

### 97.1. Mērķis

Testēt pilnu ciklu ar simulētu MT4 failu maiņu.

### 97.2. Process

1. Ievieto market un sensor failus
2. Palaiž vienu `run_live` ciklu
3. Pārbauda decision journal
4. Pārbauda control failu
5. Ievieto ACK
6. Palaiž ACK ciklu
7. Pārbauda trade journal un state

### 97.3. Noteikums

E2E testi neizmanto reālu MT4 termināli. Tie simulē failu sistēmu.

---

## 98. Performance Test

### 98.1. Mērķis

Pārbaudīt, ka instance cikls iekļaujas `runtime.cycle_max_duration_ms`.

### 98.2. Scenāriji

- Viena instance, standarta lookback
- Vairākas instances secīgā apstrādē
- Liels market CSV ar maksimālo lookback

### 98.3. Kritēriji

- `cycle_duration_ms` < `cycle_max_duration_ms`
- Atmiņas patēriņš stabilizējas bez neierobežota auguma

---

## 99. Future Extension Architecture

### 99.1. Principi

Paplašinājumi notiek, nemainot:

- Instance modeli `(account_id, symbol, magic)`
- Failu protokolu versiju politiku
- Lēmumu secību: BUY + SELL → scoring → risk → journal → execution
- Python lēmumu un MT4 izpildes sadalījumu

### 99.2. Atļautie paplašinājumi

| Paplašinājums | Vieta |
|---------------|-------|
| Jauns analīzes modulis | `engine/analysis/` |
| Jauns riska noteikums | `engine/risk/rules.py` |
| Jauns alert kanāls | `tools/` vai `engine/dashboard/` |
| Papildu journal lauki | JSONL shēmas versija |
| MT5 atbalsts | Jauns `mql5/` koks ar identisku protokolu |

### 99.3. Aizliegtie paplašinājumi

- Lēmumu pieņemšana MT4 pusē
- Universe kā trade signāls
- Cieti symbol un spread limiti
- Otrs timeframe bez shēmas major versijas maiņas

### 99.4. Shēmas versiju politika

`schema_version` major increment maina nesaderīgu formātu. Minor increment pievieno laukus ar atpakaļejošu saderību.

---

## 100. Pilns sistēmas darba cikls no pirmā Tick līdz Order Close

### 100.1. Fāze A — MT4 datu eksports

1. MT4 saņem jaunu M1 tick vai sveces aizvēršanu
2. EA apkopo M1 OHLCV
3. EA nolasa bid/ask un aprēķina spread
4. EA atomiski raksta `market_{symbol}_{magic}.csv`
5. EA atomiski raksta `sensor_{symbol}_{magic}.csv`
6. EA atjaunina `status_{account_id}.json`
7. EA atjaunina `universe.json` kontekstu

### 100.2. Fāze B — Python datu ieguve

8. `run_live.py` konstatē market faila izmaiņu caur cache hash
9. `market_loader` ielādē CSV
10. `market_validator` validē struktūru un OHLC
11. `sensor_loader` ielādē sensor CSV
12. `sensor_validator` validē spread konsekvenci
13. `status_loader` ielādē status
14. `status_validator` validē konta stāvokli
15. Ja `trade_allowed` ir false, visas instances saņem BLOCK ar `ACCOUNT_NOT_TRADEABLE`
16. `universe_loader` ielādē universe
17. `universe_validator` validē kontekstu

### 100.3. Fāze C — Normalizācija un state

18. `market_normalizer` pārveido CSV uz iekšējiem M1 objektiem
19. Tiek atjaunināti `instrument_digits`, `instrument_point`, `instrument_pip`
20. `spread_model` atjaunina mean, std, median, relative_spread
21. `spread_state` un `instance_state` tiek atjaunināti atmiņā
22. State tiek persistēts uz disku

### 100.4. Fāze D — Analīze

23. `context.py` novērtē session, regime, news
24. `structure.py` identificē swing, atbalstu, pretestību
25. `momentum.py` aprēķina impulsu un trend komponentus
26. `pressure.py` aprēķina buy/sell spiedienu
27. `behavior.py` novērtē sveču uzvedības patterns
28. `impact.py` novērtē potenciālo ietekmi uz setup kvalitāti
29. Analysis Engine apkopo `AnalysisContext`

### 100.5. Fāze E — Virzienu aprēķins

30. Spread filtrs novērtē `relative_spread`
31. Volatility filtrs novērtē relatīvo ATR
32. News filtrs novērtē universe news logu
33. Decision Engine aprēķina `BuyCandidate` ar entry, SL, TP
34. Ja BUY neder, `invalid_reason` tiek fiksēts
35. Decision Engine aprēķina `SellCandidate` ar entry, SL, TP
36. Ja SELL neder, `invalid_reason` tiek fiksēts

### 100.6. Fāze F — Scoring un lēmums

37. `scorer.py` salīdzina `buy_score` un `sell_score`
38. Nosaka `preferred_side`
39. Ja neviens virziens nav derīgs, sagatavo WAIT ar `BOTH_DIRECTIONS_INVALID`
40. Ja abi derīgi un vienādi score, sagatavo WAIT ar `EQUAL_SCORES`
41. `reason.py` ģenerē pilnu reason string

### 100.7. Fāze G — Risks

42. `risk/engine.py` saņem preferred_side un kandidātu
43. `risk/rules.py` pārbauda max pozīcijas, daily loss, drawdown
44. Aprēķina position sizing, ja ALLOW
45. Validē SL un TP
46. Atgriež ALLOW vai BLOCK ar reason
47. Ja BLOCK, gala lēmums ir BLOCK

### 100.8. Fāze H — Journal

48. `decision_journal.py` raksta `DecisionResult` ar visiem laukiem
49. `decision_id` tiek ģenerēts

### 100.9. Fāze I — Execution OPEN

50. Ja ALLOW un lēmums ir BUY vai SELL, `command.py` veido `OrderCommand` ar OPEN
51. `control_writer.py` atomiski raksta control JSON
52. `trade_journal.py` raksta OPEN intent
53. EA nolasa control
54. EA validē magic, symbol, account
55. EA izsūta MT4 OrderSend
56. EA raksta `ack_{symbol}_{magic}.json` ar SUCCESS vai FAILED
57. `ack_reader.py` nolasa ACK
58. Ja SUCCESS, `instance_state` atjaunina `open_ticket`, `position_side`, `volume`
59. `trade_journal.py` atjaunina ierakstu ar `ack_status`
60. Ja FAILED, `error_journal.py` pieraksta kļūdu

### 100.10. Fāze J — Trade Management

61. Nākamajos ciklos Analysis un Decision darbojas ar atvērtu pozīciju
62. `risk/trade_management.py` novērtē breakeven, trailing, partial close un time stop nosacījumus
63. `core/cycle.py` izsauc trade management fāzi un nodod rezultātu Execution Engine
64. Ja nepieciešams, `command.py` veido MODIFY vai CLOSE ar atbilstošo apjomu
65. Control un ACK cikls atkārtojas
65. `trade_journal.py` pieraksta MODIFY notikumu

### 100.11. Fāze K — Position Close

66. Ja TP vai SL ir trāfīts MT4 pusē, status atspoguļo pozīcijas aizvēršanu
67. Python konstatē, ka `open_ticket` vairs nav aktīvs
68. `trade_journal.py` pieraksta CLOSE notikumu
69. `instance_state` notīra pozīcijas laukus
70. Decision cikls turpinās ar jaunu BUY/SELL izvērtēšanu

### 100.12. Fāze L — Dashboard un monitoring

71. Dashboard nolasa jaunāko decision, trade un error journal
72. Attēlo lēmumu, reason, spread, pozīciju
73. Performance metrikas tiek atjauninātas logā

### 100.13. Cikla beigas un nākamais ticks

74. Instance cikls beidzas
75. `run_live.py` gaida nākamo market faila atjauninājumu vai `cycle_interval_ms`
76. Cikls sākas no 100.1 Fāzes A ar jaunu M1 datu

### 100.14. Kļūdu scenāriji ciklā

| Punktā | Kļūda | Rezultāts |
|--------|-------|-----------|
| 10 | Market invalid | Error journal, trade nenotiek |
| 15 | Account not tradeable | BLOCK visām konta instances |
| 33-36 | Abi virzieni nederīgi | WAIT ar reason |
| 47 | Risk BLOCK | BLOCK ar risk reason |
| 57 timeout | ACK nav | Error journal, recovery 26. sadaļā |
| 56 FAILED | Order noraidīts | Error journal, state bez pozīcijas |

### 100.15. Cikla garantijas

- Katrs veiksmīgs lēmumu cikls ir dokumentēts decision journal
- Katrs execution mēģinājums ir dokumentēts trade journal
- Katra kļūda ir dokumentēta error journal
- Nevienā punktā MT4 nepieņem lēmumu
- Nevienā punktā WAIT nav noklusējums
- BUY un SELL vienmēr tiek izvērtēti pirms gala lēmuma

---

## Dokumenta beigas

Šis dokuments pilnībā definē SYSTEM platformu implementācijai. Implementācijas laikā nav atļauts:

- Mainīt arhitektūras pamatprincipus
- Pievienot otro timeframe bez shēmas major versijas
- Pārvietot lēmumus uz MT4
- Ieviest cietus symbol vai spread limitus
- Izlaist BUY vai SELL izvērtēšanu
- Izmantot WAIT kā noklusējumu
- Slēpt kļūdas
- Atstāt pusgatavus moduļus

Visa implementācija sākas ar šo specifikāciju un `docs/RULES.md`.
