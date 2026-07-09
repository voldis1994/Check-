# P31–P45 arhitektūras audits

**Datums:** 2026-07-07  
**Apjoms:** P31–P45 (analysis, decision, risk/rules)  
**Avoti:** `docs/SYSTEM_SPECIFICATION.md`, `docs/IMPLEMENTATION_PLAN.md`  
**Metode:** Statiska koda un atkarību pārbaude, sekota ar labojumiem A1–A8.

---

## Kopsavilkums

P31–P45 audits **ir pilnībā iziets**. Funkcionalitāte, testi (350) un BUY/SELL/WAIT/EDGE arhitektūra atbilst SYSTEM kā edge discovery platformai. Visi konstatētie audita punkti A1–A8 ir laboti.

---

## Kas ir kārtībā

### Atbilstība IMPLEMENTATION_PLAN.md (fāžu apjoms)

| Fāze | Modulis | Statuss |
|------|---------|---------|
| P31 | `analysis/momentum.py` | Ieviests |
| P32 | `analysis/pressure.py` | Ieviests |
| P33 | `analysis/behavior.py` | Ieviests |
| P34 | `analysis/impact.py` | Ieviests |
| P35 | `analysis/engine.py` | Ieviests, fiksēta secība |
| P36 | `decision/reason.py` | Ieviests |
| P37–P39 | `decision/filters/*` | Ieviesti |
| P40–P41 | `decision/buy.py`, `sell.py` | Ieviesti |
| P42 | `decision/scorer.py` | Ieviests |
| P43 | `decision/wait_block.py` | Ieviests |
| P44 | `decision/engine.py` | Ieviests |
| P45 | `risk/rules.py` | Ieviests |

### BUY/SELL/WAIT/EDGE arhitektūra

- **Virzienu simetrija:** `run_decision_engine()` vienmēr aprēķina gan `buy_candidate`, gan `sell_candidate` pirms lēmuma.
- **Edge salīdzināšana, ne filtrēšana:** `scorer.compare_candidates()` salīdzina `buy_score` un `sell_score`; augstākais nosaka `preferred_side`.
- **WAIT nav noklusējums:** `evaluate_wait_decision()` atgriež WAIT tikai ierobežotos gadījumos.
- **Risks nav bailīgs WAIT-bots:** P45 `risk/rules.py` atgriež tikai `allowed=True/False` ar BLOCK reason kodiem.
- **Analysis slānis netirgo:** `analysis/*` neimportē `decision`, `risk` vai `execution`.

### Atkarības un cikli

```
normalizer/protocol/state
        ↓
    analysis (P29–P35)
        ↓
    decision (P36–P44)  ← journal (error log)
        ↓
    risk/rules (P45)    ← engine.reason (build_reason)
```

- **Cikliskas atkarības:** Nav.
- **Slāņu virziens:** `risk` vairs neimportē `decision`.

---

## A1. `AnalysisContext` trūkst `spread_filter_passed` — **LABOTS**

**Statuss:** **A1 fixed** (2026-07-07)

- `AnalysisContext.spread_filter_passed` pievienots ar serializāciju.
- Decision engine aizpilda lauku uzreiz pēc spread filtra.
- `buy.py`/`sell.py` lasa no konteksta.

---

## A2. Lēmumu parametri ārpus `config/system.json` — **LABOTS**

**Statuss:** **A2 fixed** (2026-07-07)

- `AnalysisConfig` / `RiskConfig` paplašināti ar spec parametriem.
- `run_decision_engine()` lasa no `system_config` caur unified loader.

---

## A3. `buy.py` un `sell.py` masīva koda dublēšanās — **LABOTS**

**Statuss:** **A3 fixed** (2026-07-07)

### Labojums

- Kopīga implementācija `engine/decision/candidate.py`: `build_component_scores`, `calculate_weighted_score`, `evaluate_filter_chain`, `calculate_trade_levels`.
- `buy.py` un `sell.py` saglabā publisko API, bet delegē kopīgajam modulim.

---

## A4. `risk` slānis importē `decision.reason` — **LABOTS**

**Statuss:** **A4 fixed** (2026-07-07)

### Labojums

- `build_reason` pārvietots uz `engine/reason.py`.
- `engine/decision/reason.py` re-eksportē (publiskais API nemainīts).
- `risk/rules.py` importē no `engine.reason`.

---

## A5. `TrendAnalysis` dublē `MomentumAnalysis` trend laukus — **LABOTS**

**Statuss:** **A5 fixed** (2026-07-07)

### Labojums

- `AnalysisEngineResult.trend` ir `@property`, kas atgriež `TrendAnalysis.from_momentum(self.momentum)`.
- Trend dati netiek glabāti dublēti rezultātā.

---

## A6. `resolve_preferred_side` un `compare_candidates` score avoti — **LABOTS**

**Statuss:** **A6 fixed** (2026-07-07)

### Labojums

- `resolve_preferred_side()` delegē uz `compare_candidates()` ar vienotu `_context_adjusted_scores` helper.
- Neobligāts `context` parametrs ļauj izmantot to pašu score avotu.

---

## A7. `RiskContext` metrikas bez persistēta avota — **LABOTS**

**Statuss:** **A7 fixed** (2026-07-07)

### Labojums

- `engine/risk/metrics.py`: `build_risk_context()`, `compute_daily_loss_percent()`, `compute_drawdown_percent()`.
- `InstanceState` paplašināts ar `day_start_balance` un `peak_equity` (persistēti state failā).
- P48 integrācijai metrikas nāk no `status` + `instance_state`, nevis ad-hoc argumentiem.

---

## A8. Testa faila nosaukums atšķiras no plāna — **LABOTS**

**Statuss:** **A8 fixed** (2026-07-07)

### Labojums

- `tests/analysis/test_engine.py` → `tests/analysis/test_analysis_engine.py`
- `tests/decision/test_decision_engine.py` → `tests/decision/test_engine.py` (atbilst P44 plānam)
- Pytest importa konflikts novērsts.

---

## Pārbaudes, kas **nav** problēmas

| Jautājums | Secinājums |
|-----------|------------|
| Vai sistēma ir kļuvusi par bailīgu WAIT-default botu? | **Nē.** |
| Vai Decision Engine dod vienpusēju signālu? | **Nē.** |
| Vai ir dead code P31–P45? | **Nav būtiska.** |
| Vai P45 risk rules integrētas decision engine? | **Vēl ne** — paredzēts P48. |
| Vai filtri izraisa BLOCK tieši decision engine? | **Nē** — atbilst spec. |

---

## Testu stāvoklis

```
350 passed (P01–P45, A1–A8)
```

---

## Kopējais secinājums

**P31–P45 audits pilnībā iziets.** Visi punkti A1–A8 ir laboti.

Arhitektūras virziens — simetriska BUY/SELL edge discovery ar atsevišķu riska BLOCK slāni — ir saglabāts un atbilst SYSTEM filozofijai. Sistēma ir gatava P46–P48 integrācijai bez zināmiem audita parādiem.
