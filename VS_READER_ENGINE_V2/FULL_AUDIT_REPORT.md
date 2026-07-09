# Pilns audits — SYSTEM (no sākuma līdz galam)

**Datums:** 2026-07-08  
**Veids:** Neatkarīgs audits no nulles (kods + testi + dokumentācija + protokols)  
**Nav veiktas koda izmaiņas** — tikai analīze un atklājumi

---

## 1. Metodoloģija

| Pārbaude | Rezultāts |
|----------|-----------|
| `python3 -m pytest tests -q` | **886 passed** (~146s) |
| Importi | `import engine`, `run_execution_engine`, `run_instance_cycle` — OK |
| Avoti | `engine/`, `mql4/`, `config/`, `docs/`, `tests/`, `tools/` |
| Salīdzinājums | `COMPLIANCE_AUDIT.md`, `FINAL_AUDIT.md`, `TRADING_BEHAVIOR_AUDIT.md`, `docs/PROTOCOL.md` |

---

## 2. Kopsavilkums

| Severity | Skaits | Būtība |
|----------|--------|--------|
| **Critical** | 3 | Live tirdzniecība bloķēta bez API atslēgas; AI kļūda pārraksta pat WAIT uz BLOCK |
| **High** | 5 | Nav advisory režīma; orchestrator metrikas kļūda; AI nav dokumentēts; nav E2E AI testu |
| **Medium** | 10 | Protokola/doc drift; journal bez AI laukiem; AI secība/latency; globāls socket timeout |
| **Low** | 4 | Agrīns spread modelis; novecojuši audit doc; testu maskēšana |

**Galvenais secinājums:** Kodu bāze ir stabilā (886 testi), bet **AI decision slānis live vidē darbojas kā obligāts fail-closed slānis**, kas **bloķē visu tirdzniecību**, ja nav `OPENAI_API_KEY` vai API kavējas. Tas ir **operacionāla kļūda** attiecībā pret advisory modeli, ko lietotājs gribēja.

---

## 3. Critical

### C-01 — Bez `OPENAI_API_KEY` viss BUY/SELL kļūst par BLOCK

| Lauks | Vērtība |
|-------|---------|
| **Fails** | `engine/ai_decision_layer.py` |
| **Rindas** | L149-L151, L182-L183 |
| **Apraksts** | Ja `OPENAI_API_KEY` nav iestatīts, `get_ai_decision()` atgriež `None`. `decide_final_decision()` to interpretē kā `BLOCK` ar `"AI_ERROR: no response/timeout"`. Live vidē **nav iespējams tirgot**, pat ja SYSTEM + risk ir OK. |
| **Pierādījums** | Simulācija: `OPENAI_API_KEY=` → `get_ai_decision` = `None` → `apply_ai_to_decision_result` → `BLOCK` |
| **Ietekme** | Produkcijā bez atslēgas sistēma **nekad neatvērs pozīciju** |

```python
# engine/ai_decision_layer.py L149-L151, L182-L183
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    return None
...
if ai_decision is None:
    return Decision.BLOCK.value, "AI_ERROR: no response/timeout"
```

---

### C-02 — AI timeout/API kļūda pārraksta arī SYSTEM=WAIT uz BLOCK

| Lauks | Vērtība |
|-------|---------|
| **Fails** | `engine/ai_decision_layer.py` |
| **Rindas** | L182-L183 |
| **Apraksts** | Kad `ai_decision is None`, funkcija **vienmēr** atgriež `BLOCK` — neatkarīgi no `system_signal`. Pat `WAIT` un sākotnējais `BLOCK` tiek pārrakstīts uz `AI_ERROR` BLOCK. |
| **Pierādījums** | `decide_final_decision(system_signal="WAIT", ai_decision=None)` → `BLOCK` |

```
BUY  -> BLOCK AI_ERROR: no response/timeout
SELL -> BLOCK AI_ERROR: no response/timeout
WAIT -> BLOCK AI_ERROR: no response/timeout   ← loģikas kļūda
BLOCK-> BLOCK AI_ERROR: no response/timeout
```

**Sagaidāmā uzvedība advisory režīmā:** `WAIT`/`BLOCK` paliek nemainīgi; tikai `BUY`/`SELL` var tikt bloķēti vai atstāti.

---

### C-03 — Nav advisory fallback režīma (prasītais, bet neimplementētais)

| Lauks | Vērtība |
|-------|---------|
| **Fails** | `engine/ai_decision_layer.py`, `engine/core/config.py`, `config/system.json` |
| **Apraksts** | Nav `apply_ai_advisory_decision`, `AIDecisionConfig`, `ai.mode`, `fail_closed`. Viss kods ir **mandatory fail-closed**. AI kļūda = BLOCK. |
| **Meklēšana** | `apply_ai_advisory_decision`, `ai_mode` — **0 atbilstību** repozitorijā |
| **Ietekme** | Live tirdzniecība apstājas pie jebkuras OpenAI problēmas (tīkls, timeout 10s, rate limit, invalid JSON) |

---

## 4. High

### H-01 — Invalid status ceļš atgriež `completed=True` (orchestrator kļūdaini skaita “veiksmīgu” ciklu)

| Lauks | Vērtība |
|-------|---------|
| **Fails** | `engine/core/cycle.py` |
| **Rindas** | L694-L702 (kļūda), L760-L764 (`completed=True`) |
| **Apraksts** | Kad `status` validācija neiziet, tiek logots error, bet `InstanceCycleResult.completed=True`. Orchestrator skaita to kā `completed_count++` (`orchestrator.py` L185-L186), lai gan `monitoring.resolve_instance_health` dod `ERROR` (`monitoring.py` L70-L71). |
| **Ietekme** | Runtime metrikas “completed/failed” ir **maldinošas**; monitoring un orchestrator nesaskan |

---

### H-02 — AI slānis nav dokumentēts specifikācijā / README

| Lauks | Vērtība |
|-------|---------|
| **Faili** | `docs/SYSTEM_SPECIFICATION.md`, `docs/IMPLEMENTATION_PLAN.md`, `README.md`, `config/system.json` |
| **Apraksts** | Nav nevienas atsauces uz OpenAI, `OPENAI_API_KEY`, AI decision flow. `README.md` nepiemin atslēgas iestatīšanu Windows. `system.json` nav `ai` sekcijas. |
| **Ietekme** | Live uzstādītājs nezina, ka bez atslēgas sistēma **bloķē visu** |

---

### H-03 — E2E un integration testi neiet cauri AI slānim reālā ciklā

| Lauks | Vērtība |
|-------|---------|
| **Faili** | `tests/conftest.py` (autouse mock), `tests/integration/test_decision_pipeline.py`, `tests/e2e/test_full_cycle.py` |
| **Apraksts** | `conftest.py` autouse fixture **vienmēr** mockē `_call_openai` un iestata dummy `OPENAI_API_KEY`. Integration pipeline izsauc tikai `run_instance_decision_phase` + `run_instance_risk_phase` — **bez** `get_ai_decision` / `apply_ai_to_decision_result`. E2E failos nav `ai_decision` atsauču. |
| **Ietekme** | 886 testi **nemaskē** production scenāriju “nav API / timeout”; regressija advisory režīmā netiks noķerta |

---

### H-04 — Risk engine tiek palaists uz **pre-AI** lēmuma, bet žurnāls/logi rāda **post-AI** lēmumu

| Lauks | Vērtība |
|-------|---------|
| **Fails** | `engine/core/cycle.py` |
| **Rindas** | L801-L834 |
| **Secība** | `decision` → `get_ai_decision` → `run_instance_risk_phase(decision_result=...)` → `apply_ai_to_decision_result` |
| **Apraksts** | Risk aprēķins balstās uz SYSTEM signālu pirms AI korekcijas. Ja AI vēlāk bloķē, žurnālā būs `risk_result=ALLOW` bet `decision=BLOCK`. |
| **Ietekme** | Audita takā grūti saprast, kāpēc nebija izpildes; risk/AI secība nav loģiski tīra |

---

### H-05 — `decide_final_decision` dublē risk pārbaudi AI slānī (bet risk jau ir atsevišķā fāzē)

| Lauks | Vērtība |
|-------|---------|
| **Fails** | `engine/ai_decision_layer.py` |
| **Rindas** | L187-L201 |
| **Apraksts** | AI slānis pats pārbauda `risk_pass` un atgriež BLOCK. Risk engine tiek izsaukts atsevišķi cycle. Dubultā loģika apgrūtina advisory/refactor. |

---

## 5. Medium

### M-01 — `docs/PROTOCOL.md` vs `is_valid_ack_status` — TIMEOUT pretruna

| Lauks | Vērtība |
|-------|---------|
| **Faili** | `docs/PROTOCOL.md` L68, `engine/protocol/constants.py` L273-L279, `mql4/Include/SYSTEM_Execution.mqh` |
| **Apraksts** | Dokumentācija saka ACK `status` var būt `TIMEOUT`. Python `is_valid_ack_status()` un MQL4 `SYSTEM_IsSupportedAckStatus` **neatļauj** `TIMEOUT` ārējā ACK JSON. `TIMEOUT` tiek izmantots tikai iekšēji (`InstanceState.last_ack_status`, trade journal reason). |
| **Ietekme** | Integrācijas/doc neskaidrība; nav kritiska runtime kļūda (kods apzināti atdalīts), bet audits atzīmē **doc drift** |

---

### M-02 — `TRADING_BEHAVIOR_AUDIT.md` kļūdaini apgalvo, ka spread ekonomiskā konsistence netiek validēta

| Lauks | Vērtība |
|-------|---------|
| **Faili** | `TRADING_BEHAVIOR_AUDIT.md` L588-L590, `engine/validator/sensor_validator.py` L53-L67 |
| **Apraksts** | Audits saka “does not enforce economic consistency”. Kods **validē** `spread == ask - bid` un `spread_points == spread / point`. |
| **Ietekme** | Dokumentācija maldina par datu drošību |

---

### M-03 — `COMPLIANCE_AUDIT.md` novecojis (877 vs 886 testi; nav AI slāņa)

| Lauks | Vērtība |
|-------|---------|
| **Fails** | `COMPLIANCE_AUDIT.md` |
| **Apraksts** | Norāda 877 testus; faktiski 886. Neņem vērā AI decision slāni un tā live riskus. |

---

### M-04 — `FINAL_AUDIT.md` novecojis (HIGH/MED atradumi daļēji jau salaboti)

| Lauks | Vērtība |
|-------|---------|
| **Fails** | `FINAL_AUDIT.md` |
| **Apraksts** | HIGH-001 (ārēja aizvēršana) — tagad ir `reconcile_position_with_status` + `log_external_position_close` (`position_sync.py`). MED-001 (journal rotācija) — tagad ir `rotate_account_journals` (`orchestrator.py` L210). MED-002 (cycle timeout) — daļēji: `CycleTimeoutGuard` + `test_run_instance_cycle_aborts_on_cycle_timeout`. |
| **Ietekme** | Vecais audits **vairs nav uzticams** kā pašreizējais stāvoklis |

---

### M-05 — AI timeout fiksēts 10s, nav konfigurējams

| Lauks | Vērtība |
|-------|---------|
| **Fails** | `engine/ai_decision_layer.py` L155-L157 |
| **Apraksts** | `timeout_s=10` hardcoded. `config/system.json` `runtime` satur `ack_timeout_ms`, bet ne AI timeout. |
| **Ietekme** | Ar `cycle_max_duration_ms=30000` viens lēns AI zvans var patērēt trešdaļu cikla budžeta |

---

### M-06 — AI tiek izsaukts pirms risk fāzes (lieks latency/cost)

| Lauks | Vērtība |
|-------|---------|
| **Fails** | `engine/core/cycle.py` L809-L829 |
| **Apraksts** | `get_ai_decision()` pirms `run_instance_risk_phase()`. Ja risk jau būtu BLOCK (piem., max positions), AI zvans joprojām notiek. |

---

### M-07 — Decision journal bez AI metadatiem

| Lauks | Vērtība |
|-------|---------|
| **Faili** | `engine/protocol/models.py` (`DecisionJournalEntry`), `engine/journal/decision_journal.py` |
| **Apraksts** | Nav lauku: `ai_mode`, `ai_available`, `ai_error_type`, `ai_fallback_used`, `ai_reason`, `system_decision_before_ai`, `decision_after_ai`. |
| **Ietekme** | Nevar auditēt AI ietekmi no žurnāliem |

---

### M-08 — `socket.setdefaulttimeout()` globālais blāķis

| Lauks | Vērtība |
|-------|---------|
| **Fails** | `engine/ai_decision_layer.py` L128-L135 |
| **Apraksts** | Maina procesa globālo socket timeout, pēc tam reset uz `None`. Potenciāls race, ja citi threadi lieto socket. |

---

### M-09 — `allow_close` no AI JSON netiek izmantots

| Lauks | Vērtība |
|-------|---------|
| **Fails** | `engine/ai_decision_layer.py` |
| **Apraksts** | `AIDecision.allow_close` tiek parsēts, bet `decide_final_decision` to neizmanto trade management vai CLOSE veto. |

---

### M-10 — `tests/conftest.py` autouse mock slēpj mandatory AI uzvedību visā testu komplektā

| Lauks | Vērtība |
|-------|---------|
| **Fails** | `tests/conftest.py` L9-L69 |
| **Apraksts** | Katrs tests automātiski mockē OpenAI. Reālā “mandatory AI” uzvedība tiek pārbaudīta tikai `tests/ai/test_ai_decision_layer.py` (9 testi). |

---

## 6. Low

### L-01 — Agrīnā spread vēsture dod `relative_spread=0.0` (filtrs vienmēr “OK”)

| Lauks | Vērtība |
|-------|---------|
| **Fails** | `engine/normalizer/spread_model.py` L49-L50 |
| **Apraksts** | Ja `std_spread <= 0` (1 paraugs vēsturē), `relative_spread = 0.0` → spread filtrs vienmēr iziet. |
| **Ietekme** | Pirmajos ciklos pēc starta spread anomālijas var netikt filtrētas |

---

### L-02 — `engine/core/cycle.py` `_abort_cycle_timeout` return bloka atkāpe (stils, ne funkcionalitāte)

| Lauks | Vērtība |
|-------|---------|
| **Rindas** | L885-L890 |
| **Apraksts** | `return _abort_cycle_timeout(` argumenti ar neparastu atkāpi; Python der, bet grūti lasāms. |

---

### L-03 — Nav `openai` pakotnes / retry / circuit breaker

| Lauks | Vērtība |
|-------|---------|
| **Fails** | `requirements.txt`, `ai_decision_layer.py` |
| **Apraksts** | Tīrs `urllib` bez retry, bez exponential backoff, bez circuit breaker pēc N kļūdām. |

---

### L-04 — Specifikācijā nav AI decision plūsmas (§ nav atjaunināts pēc AI integrācijas)

| Lauks | Vērtība |
|-------|---------|
| **Apraksts** | `IMPLEMENTATION_PLAN.md` un `SYSTEM_SPECIFICATION.md` neapraksta SYSTEM→AI→RISK→Execution plūsmu. |

---

## 7. Kas darbojas pareizi (pozitīvi)

| Apgabals | Stāvoklis |
|----------|-----------|
| Testu komplekts | 886 passed |
| Circular imports | Nav atklātas (imports OK) |
| Windows `resource` | `performance.py` lazy import + psutil fallback |
| Path normalization | Loader testi izmanto `Path.as_posix()` |
| Position sync | `reconcile_position_with_status` — ārēja aizvēršana/daļēja |
| Journal rotācija | `rotate_account_journals` orchestratorā |
| Cycle timeout | `CycleTimeoutGuard` + tests |
| Spread validācija | `spread == ask - bid` (`sensor_validator.py`) |
| Risk pēdējā drošība | `should_execute_trade` + `build_order_command` neļauj OPEN pie BLOCK |
| CI | `.github/workflows/tests.yml` — Python 3.11, pytest |
| API key drošība | Nav hardcoded atslēgu repozitorijā; tikai env var |

---

## 8. Pilns lēmumu ceļš (pašreizējais kods)

```
MT4 export (market/sensor/status/universe)
    → load + validate
    → spread model (relative_spread)
    → run_decision_engine (SYSTEM signal)
    → get_ai_decision (OpenAI)          ← mandatory; kļūda = None
    → run_risk_engine (uz PRE-AI decision)
    → apply_ai_to_decision_result       ← None => BLOCK (visiem signāliem)
    → trade management
    → execution (OPEN/MODIFY/CLOSE/NONE)
    → ACK / recovery
```

**Problēmas šajā ceļā:** AI kļūda nogalina SYSTEM signālu; nav advisory fallback; risk secība apgriezta attiecībā pret AI.

---

## 9. Prioritātes — ko labot vispirms

| Prioritāte | ID | Darbība |
|------------|-----|---------|
| 1 | C-01, C-02, C-03 | Implementēt **advisory** režīmu: AI kļūda → SYSTEM fallback; valid AI → veto/allow |
| 2 | H-02 | Dokumentēt `OPENAI_API_KEY` + `ai` config `README` / `system.json` |
| 3 | H-01 | Invalid status → `completed=False` |
| 4 | H-03 | E2E tests: AI timeout advisory fallback pilnā ciklā (bez autouse mock) |
| 5 | H-04 | Apsvērt secību: risk pēc AI vai risk tikai uz gala lēmumu |
| 6 | M-07 | Decision journal AI lauki |
| 7 | M-02, M-03, M-04 | Atjaunināt audit/spec dokumentus |

---

## 10. Nezināms / nav pārbaudīts šajā vidē

| Punkts | Iemesls |
|--------|---------|
| P74 LIVE MT4 validācija | Nav reāla MT4 šajā cloud vidē |
| OpenAI API reāls latency | Tikai mock testi |
| Windows produkcijas `run_live.py` ilgtermiņa stabilitāte | Nav long-run testa |

---

## 11. Secinājums

Projekts **tehniski stabilā** (886 testi, imports, cross-platform labojumi). Tomēr pēc **AI decision slāņa integrācijas** ir **kritiskas operacionālās kļūdas**:

1. **Bez OpenAI atslēgas vai pie API kļūdas sistēma bloķē visu**, nevis turpina ar SYSTEM.
2. **Pat WAIT signāls** tiek pārrakstīts uz BLOCK pie AI kļūdas.
3. **Advisory režīms nav implementēts**, lai gan tas ir nepieciešams live drošībai.

`COMPLIANCE_AUDIT.md` (0 atradumi) **vairs neatspoguļo** AI slāņa riskus un ir jāatjaunina pēc advisory implementācijas.

---

*Audits sagatavots automātiski no koda, testu izpildes un dokumentu salīdzinājuma. Nav veiktas koda izmaiņas.*

---

## 12. Resolution status (2026-07-08)

Visi šajā dokumentā minētie atradumi ir **novērsti**:

| ID | Statuss | Labojums |
|----|---------|----------|
| C-01..C-03 | ✅ | Advisory/required AI (`engine/ai_decision_layer.py`, `config/system.json`) |
| H-01 | ✅ | Invalid status → `completed=False` |
| H-02 | ✅ | README, SYSTEM_SPECIFICATION §10.3.1, IMPLEMENTATION_PLAN P76 |
| H-03 | ✅ | `tests/integration/test_ai_decision_pipeline.py`, E2E AI metadata |
| H-04 | ✅ | `run_instance_ai_risk_pipeline`: AI pirms risk |
| H-05 | ✅ | `decide_ai_decision` + `apply_risk_block_to_decision_result` |
| M-01 | ✅ | PROTOCOL.md — TIMEOUT tikai iekšēji |
| M-02 | ✅ | TRADING_BEHAVIOR_AUDIT.md spread validācija |
| M-03, M-04 | ✅ | COMPLIANCE_AUDIT.md, FINAL_AUDIT.md atjaunināti |
| M-05 | ✅ | `ai.timeout_ms` konfigurējams |
| M-06 | ✅ | `should_call_ai_layer` — skip AI kad risk rules bloķē BUY/SELL |
| M-07 | ✅ | Decision journal AI lauki |
| M-08 | ✅ | Noņemts `socket.setdefaulttimeout` |
| M-09 | ✅ | `allow_close` → trade management |
| M-10 | ✅ | `@pytest.mark.no_ai_mock` + AI integration testi |
| L-01 | ✅ | Viena parauga spread → `relative_spread=1.0` |
| L-02 | ✅ | `cycle.py` `_abort_cycle_timeout` atkāpe |
| L-03 | ✅ | `ai.retry_max`, `ai.retry_delay_ms` |
| L-04 | ✅ | SYSTEM_SPECIFICATION §10.3.1 |

**Testi:** 900 passed (`python3 -m pytest`)

**Atvērtais punkts ārpus šīs vides:** P74 LIVE MT4 validācija ar reālu termināli.
