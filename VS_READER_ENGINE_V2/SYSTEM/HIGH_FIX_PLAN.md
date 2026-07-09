# SYSTEM — High punktu labošanas plāns

**Datums:** 2026-07-07  
**Avots:** `AUDIT_AFTER_CRITICAL.md` (16 atvērtie High punkti pēc PR #76)  
**Mērķis:** Strukturēts, prioritizēts darba plāns visu atlikušo High atradumu novēršanai. **Kods nav labots.**

---

## Kopsavilkums

| Metrika | Vērtība |
|---------|---------|
| Atvērtie High punkti (unikāli) | **14 problēmas** / **16 audita ID** (2 dublikātu pāri) |
| Bug | 5 |
| Missing implementation | 7 |
| Design issue | 1 |
| Recommendation | 1 |
| Ieteicamās grupas | **10** |
| Ieteicamā secība | 10 soļi (skatīt §5) |

---

## 1. Pilns High punktu saraksts

### Unikālās problēmas (14)

| # | Audita ID | Apraksts |
|---|-----------|----------|
| H01 | AUDIT-STATE-001 (+ Critical atlikums) | Trūkst `position_bars_open`, `partial_close_applied`; recovery ceļā trūkst `entry_price` OPEN ACK |
| H02 | AUDIT-MT4-001 | `SYSTEM_ExecuteClose` ignorē `command.volume` — partial close nedarbojas MT4 pusē |
| H03 | AUDIT-SPEC-002 | `build_risk_trade_params()` hardcoded; nav `system.json` risk lauku |
| H04 | AUDIT-ARCH-002 / RECOV-001 / PERF-001 | `run_runtime_recovery` katrā orchestrator iterācijā |
| H05 | AUDIT-RECOV-002 | Late SUCCESS ACK pēc TIMEOUT netiek apstrādāts |
| H06 | AUDIT-SPEC-003 / IO-001 / DEAD-HIGH-001 | `run_with_retry` neintegrēts IO ceļos |
| H07 | AUDIT-SPEC-004 | `cycle_max_duration_ms` nav runtime enforcement |
| H08 | AUDIT-SPEC-005 | Data stale → tikai WARNING, nevis skip cycle (§79.3) |
| H09 | AUDIT-EXEC-003 | `wait_for_ack` poll pārbauda tikai faila eksistenci |
| H10 | AUDIT-EXEC-004 / DEAD-HIGH-002 | `is_control_republish_allowed` neizmantots pirms `publish_control` |
| H11 | AUDIT-TEST-001 | Nav E2E testa: OPEN → MODIFY/CLOSE → state |
| H12 | AUDIT-SEC-001 | `validate_account_id` / `validate_symbol` neaizliedz path traversal |
| H13 | AUDIT-PLAN-001 | P75 ārpus `IMPLEMENTATION_PLAN.md` |
| H14 | — (kategorija Dokumentācija) | Atlikušie doc atjauninājumi (`ARCHITECTURE.md`, `README.md` — nav kritiski, bet High kategorijā iekļauti plānā) |

### Dublikāti (viena problēma, vairāki ID)

| Problēma | ID |
|----------|-----|
| Retry neintegrēts | SPEC-003, IO-001, DEAD-HIGH-001 |
| Recovery katrā ciklā | ARCH-002, RECOV-001, PERF-001 |
| Republish loģika | EXEC-004, DEAD-HIGH-002 |

### Jau novērsti (neiekļauti plānā)

| ID | Iemesls |
|----|---------|
| AUDIT-RISK-001 | Management path integrēts Critical fixes |
| AUDIT-DOC-001 | `ORDER_COMMAND.md` atbilst runtime |

---

## 2. Grupas pa tēmām

---

### G1. State un Trade Management pilnīgums

**Audita punkti:** H01 (AUDIT-STATE-001), daļa no Critical atlikuma (§2 AUDIT_AFTER_CRITICAL)

| Lauks | Vērtība |
|-------|---------|
| **Tips** | Missing implementation |
| **Sarežģītība** | **M** |
| **Faili** | `engine/state/instance_state.py`, `engine/core/cycle.py`, `engine/core/recovery.py`, `engine/execution/engine.py`, `tests/state/test_instance_state.py`, `tests/core/test_cycle.py`, `tests/core/test_recovery.py` |
| **Risks, ja nelabo** | Time stop nekad nestrādā vairākos ciklos; partial close var atkārtoties; pēc restarta/recovery management paliek neaktīvs bez `entry_price`; §100.10–100.11 paliek daļējs |

**Darbi:**
1. Pievienot `position_bars_open`, `partial_close_applied` state shēmā (load/save/to_dict).
2. Inkrementēt `position_bars_open` katrā ciklā ar atvērtu pozīciju; iestatīt `partial_close_applied` pēc partial CLOSE ACK.
3. `resolve_open_position_from_state` — izmantot persistētos laukus, ne `DEFAULT_POSITION_BARS_OPEN = 1`.
4. `recover_pending_ack` — nodot `entry_price` uz `apply_ack_to_instance_state` OPEN gadījumā.

**Atkarības:** Nav (fonds citām grupām).  
**Neizjauc:** G2 (MT4 partial close), G10 (E2E testi).

---

### G2. MT4 integrācija — partial close

**Audita punkti:** H02 (AUDIT-MT4-001)

| Lauks | Vērtība |
|-------|---------|
| **Tips** | **Bug** (§57.2, §75.2) |
| **Sarežģītība** | **S** |
| **Faili** | `mql4/Include/SYSTEM_Execution.mqh`, `tests/mql4/` (contract tests), opcionāli `tools/validate_live.py` |
| **Risks, ja nelabo** | Python `evaluate_partial_close` ģenerē CLOSE ar volume, bet MT4 aizver pilnu pozīciju; state/Python un MT4 pretruna; finansiāls risks |

**Darbi:**
1. `SYSTEM_ExecuteClose`: ja `command.has_volume` — izmantot `command.volume`, citādi `OrderLots()`.
2. Atjaunināt MQL4 contract testus.

**Atkarības:** **G1** (`partial_close_applied` state) — ieteicams pirms vai vienlaikus.  
**Neizjauc:** G10 (E2E partial close scenārijs).

---

### G3. Risk un konfigurācija

**Audita punkti:** H03 (AUDIT-SPEC-002)

| Lauks | Vērtība |
|-------|---------|
| **Tips** | **Bug** (§54.2, §54.4, §55.2) |
| **Sarežģītība** | **M** |
| **Faili** | `config/system.json`, `engine/core/config.py`, `engine/protocol/models.py`, `engine/protocol/parser.py`, `engine/core/cycle.py`, `tests/core/test_config.py`, `tests/core/test_cycle.py` |
| **Risks, ja nelabo** | Nevar pielāgot risku bez koda izmaiņām; neatbilstība specifikācijai; LIVE vidē nepareizs position sizing |

**Darbi:**
1. Pievienot `risk.max_risk_per_trade_percent`, `risk.max_stop_loss_pips`, `volume_step` (vai atsevišķa sekcija) `system.json`.
2. Ielādēt caur `SystemConfig` / `RiskConfig`.
3. `build_risk_trade_params()` — lasīt no config/status, ne hardcoded.

**Atkarības:** Nav.  
**Neizjauc:** G1 (trade management `volume_step` config).

---

### G4. Recovery arhitektūra un performance

**Audita punkti:** H04 (AUDIT-ARCH-002, RECOV-001, PERF-001)

| Lauks | Vērtība |
|-------|---------|
| **Tips** | Design issue / Missing implementation |
| **Sarežģītība** | **M** |
| **Faili** | `engine/core/orchestrator.py`, `engine/core/lifecycle.py`, `engine/core/recovery.py`, `engine/core/cache.py`, `tests/core/test_orchestrator.py`, `tests/core/test_recovery.py`, `tests/performance/` |
| **Risks, ja nelabo** | Cache invalidācija katrā iterācijā; lieks disk IO; pretruna ar P65 un §71; performance regresija ilgstošā LIVE |

**Darbi:**
1. Noņemt `run_runtime_recovery` no `run_runtime_cycles` katras iterācijas.
2. Atstāt pilnu recovery `lifecycle.startup` un pēc konkrētiem signāliem (ACK timeout, restart).
3. Ja §79.2.4 prasa sync cikla sākumā — izdalīt vieglu `sync_instance_state` bez pilnas cache invalidation.
4. Pārbaudīt performance testus.

**Atkarības:** Labāk pēc **G1** (state persist), lai recovery nekonfliktē ar state laukiem.  
**Neizjauc:** G5 (late ACK), G6 (retry), G9 (ACK poll).

---

### G5. Recovery — late ACK un republish

**Audita punkti:** H05 (AUDIT-RECOV-002), H10 (AUDIT-EXEC-004, DEAD-HIGH-002)

| Lauks | Vērtība |
|-------|---------|
| **Tips** | **Bug** (RECOV-002) + Missing implementation (EXEC-004) |
| **Sarežģītība** | **M** |
| **Faili** | `engine/core/recovery.py`, `engine/execution/engine.py`, `engine/execution/control_writer.py`, `tests/core/test_recovery.py`, `tests/execution/test_engine.py` |
| **Risks, ja nelabo** | Vēls ACK pēc timeout netiek piemērots; state/MT4 diverģence; duplicate control scenāriji; §78.3, §79.2, P65 nepilnīgi |

**Darbi:**
1. `recover_pending_ack`: pārbaudīt ACK failu arī pēc `last_ack_status == TIMEOUT`.
2. Integrēt `is_control_republish_allowed` pirms `publish_control` / `run_execution_engine`.
3. Saskaņot ar `validate_control_command_retry`.

**Atkarības:** **G4** (recovery biežums jāstabilizē vispirms).  
**Neizjauc:** G9 (ACK poll loģika).

---

### G6. I/O retry politika

**Audita punkti:** H06 (AUDIT-SPEC-003, IO-001, DEAD-HIGH-001)

| Lauks | Vērtība |
|-------|---------|
| **Tips** | Missing implementation |
| **Sarežģītība** | **M** |
| **Faili** | `engine/core/retry.py`, `engine/core/atomic_io.py`, `engine/loader/*.py`, `engine/execution/control_writer.py`, `engine/execution/ack_reader.py`, `tests/core/test_retry.py`, loader/execution testi |
| **Risks, ja nelabo** | Īslaicīgi IO konflikti izraisa tūlītēju kļūmi; neatbilstība P55 un §78 |

**Darbi:**
1. Integrēt `run_with_retry` kritiskos lasīšanas/rakstīšanas punktos ar `runtime.retry_max` / `retry_delay_ms`.
2. Neietvert retry ap control `command_id` atkārtošanu (§78.3).

**Atkarības:** Nav stingras; labāk pēc **G4** (lai recovery un retry kārtība būtu skaidra).  
**Neizjauc:** G7 (cycle timeout var palielināt IO laiku).

---

### G7. Timeout un data freshness

**Audita punkti:** H07 (AUDIT-SPEC-004), H08 (AUDIT-SPEC-005)

| Lauks | Vērtība |
|-------|---------|
| **Tips** | **Bug** (§79.3, §79.4) |
| **Sarežģītība** | **M** |
| **Faili** | `engine/core/cycle.py`, `engine/core/monitoring.py`, `engine/core/alerts.py`, `engine/protocol/constants.py`, `engine/journal/error_journal.py`, `docs/IMPLEMENTATION_PLAN.md` (P67 vs §79.3 saskaņošana), `tests/core/test_cycle.py`, `tests/core/test_monitoring.py` |
| **Risks, ja nelabo** | Ilgs cikls bloķē orchestratoru; lēmumi ar novecojušiem datiem; trade ar stale M1; neatbilstība §79 |

**Darbi:**
1. Pirms decision fāzes: pārbaudīt market/sensor freshness pret `data_stale_threshold_ms`; ja stale — skip cycle + error journal.
2. Pēc cikla: salīdzināt `cycle_duration_ms` ar `cycle_max_duration_ms`; pārsniegums → abort/partial persist + `CYCLE_TIMEOUT` error journal; izmantot `REASON_CYCLE_TIMEOUT`.
3. Saskaņot P67 testu prasības ar §79.3 (atjaunināt plānu vai implementāciju — izvēlēties vienu avotu).

**Atkarības:** **G4** (cycle struktūra), **G6** (retry var ietekmēt cycle ilgumu).  
**Neizjauc:** G8 (monitoring joprojām drīkst alertēt pēc cikla, bet ne aizstāt skip).

---

### G8. Execution — ACK poll robustums

**Audita punkti:** H09 (AUDIT-EXEC-003)

| Lauks | Vērtība |
|-------|---------|
| **Tips** | Design issue |
| **Sarežģītība** | **S** |
| **Faili** | `engine/execution/engine.py`, `engine/execution/ack_reader.py`, `tests/execution/test_engine.py` |
| **Risks, ja nelabo** | Vecs ACK fails var izraisīt `command_id` mismatch vai nepareizu interpretāciju; reti, bet LIVE edge case |

**Darbi:**
1. Poll laikā validēt `command_id` (lasīt ACK vai ignorēt novecojušu).
2. Vai: dzēst/ignorēt ACK, kas neatbilst gaidītajam `command_id`.

**Atkarības:** **G5** (recovery/ACK loģika stabilizēta).  
**Neizjauc:** G5, G10.

---

### G9. Drošība — identitātes validācija

**Audita punkti:** H12 (AUDIT-SEC-001)

| Lauks | Vērtība |
|-------|---------|
| **Tips** | Recommendation (§80.4 netieša); praktiski drošības gaps |
| **Sarežģītība** | **S** |
| **Faili** | `engine/protocol/identity.py`, `engine/core/lifecycle.py` (`discover_instances_from_account`), `tests/protocol/test_identity.py` (jauns) |
| **Risks, ja nelabo** | Ļaunprātīgs `account_id`/`symbol` var rakstīt ārpus `data/clients/{id}/` |

**Darbi:**
1. Regex whitelist vai explicit rejection: `..`, `/`, `\`, kontroles simboli.
2. Validēt auto-discovered `account_id` startup laikā.

**Atkarības:** Labāk **vēlu** (pēc funkcionāliem labojumiem), lai netraucētu fixture/test kontus.  
**Neizjauc:** G3 (config), G6 (loaders).

---

### G10. Testi — E2E Trade Management

**Audita punkti:** H11 (AUDIT-TEST-001)

| Lauks | Vērtība |
|-------|---------|
| **Tips** | Missing implementation (testa gaps) |
| **Sarežģītība** | **L** |
| **Faili** | `tests/e2e/test_full_cycle.py`, `tests/e2e/simulator/mt4_simulator.py`, iespējams jauns `tests/e2e/test_trade_management_cycle.py` |
| **Risks, ja nelabo** | Regresijas management ceļā netiks uztvertas; P74/P49 uzticamība zema bez E2E |

**Darbi:**
1. E2E: OPEN → pozīcija state → MODIFY ACK → SL atjaunināts.
2. E2E: OPEN → CLOSE ACK → `clear_position`.
3. Opcionāli: partial CLOSE (prasa G1 + G2).

**Atkarības:** **G1**, **G2**, **G5**, **G8** (vispirms funkcionalitāte).  
**Neizjauc:** — (tikai verificē).

---

### G11. Dokumentācija un plāns

**Audita punkti:** H13 (AUDIT-PLAN-001), H14 (doc atlikumi)

| Lauks | Vērtība |
|-------|---------|
| **Tips** | Recommendation |
| **Sarežģītība** | **S** |
| **Faili** | `docs/IMPLEMENTATION_PLAN.md`, `docs/ARCHITECTURE.md`, `README.md`, `docs/IMPLEMENTATION_PLAN.md` failu tabula (`ORDER_COMMAND.md`, `validate_order_command.py`) |
| **Risks, ja nelabo** | Procesa neskaidrība: kas ir “pabeigts”; grūti plānot nākamos posmus |

**Darbi:**
1. Formalizēt P75 (vai P75+ fāzes) plānā.
2. Atjaunināt ARCHITECTURE, README, plāna kopsavilkuma tabulu.
3. Dokumentēt P67 vs §79.3 izvēli pēc G7 implementācijas.

**Atkarības:** **Pēdējā** — pēc funkcionālo grupu pabeigšanas.  
**Neizjauc:** — .

---

## 3. Prioritāšu secība (grupas)

Secība izvēlēta tā, lai:
- zemākā līmeņa izmaiņas (state, config) nenāk pēc atkarīgajām;
- recovery stabilizācija notiek pirms execution/ACK izmaiņām;
- MT4 un E2E seko Python state loģikai;
- dokumentācija atspoguļo faktisko stāvokli.

| Prioritāte | Grupa | Nosaukums | Sarežģītība | Bug/MI |
|------------|-------|-----------|-------------|--------|
| **P1** | G1 | State / Trade Management pilnīgums | M | MI |
| **P2** | G3 | Risk / konfigurācija | M | Bug |
| **P3** | G4 | Recovery arhitektūra / performance | M | Design/MI |
| **P4** | G5 | Recovery late ACK + republish | M | Bug/MI |
| **P5** | G6 | I/O retry | M | MI |
| **P6** | G7 | Timeout + data stale | M | Bug |
| **P7** | G2 | MT4 partial close | S | Bug |
| **P8** | G8 | ACK poll robustums | S | Design |
| **P9** | G10 | E2E Trade Management testi | L | MI |
| **P10** | G9 | Security identitāte | S | Rec |
| **P11** | G11 | Dokumentācija / plāns | S | Rec |

---

## 4. Atkarību diagramma

```
G1 State ──────────────┬──► G2 MT4 partial close ──┐
                       │                           │
G3 Risk config         │                           ├──► G10 E2E testi
                       │                           │
G4 Recovery freq ──► G5 Late ACK/republish ──► G8 ACK poll ──┘
        │
        └──► G6 I/O retry ──► G7 Timeout/stale
                                    │
G9 Security (paralēli, vēlu)        │
G11 Dokumentācija (pēc visiem) ◄────┘
```

**Konfliktu izvairīšanās:**
- **G4 pirms G5/G6/G7:** recovery biežuma maiņa maina cikla uzvedību; jāfiksē vispirms.
- **G1 pirms G2/G10:** partial close state jābūt pareizam pirms MT4 un E2E.
- **G7 pēc G6:** retry var pagarināt ciklu; timeout enforcement jākalibrē ar retry.
- **G11 pēdējā:** lai plāns atspoguļo faktisko P75/P76+ stāvokli.

---

## 5. Ieteicamā labošanas secība (soļi)

| Solis | Grupa | Darbība | Sagaidāmais rezultāts |
|-------|-------|---------|----------------------|
| 1 | **G1** | State: `bars_open`, `partial_close_applied`, recovery `entry_price` | Trade management pilns Python pusē |
| 2 | **G3** | Risk parametri no `system.json` | §54–55 atbilstība |
| 3 | **G4** | Recovery tikai startup + signāli | Performance, P65 atbilstība |
| 4 | **G5** | Late ACK + republish | §79.2, §78.3, P65 |
| 5 | **G6** | `run_with_retry` IO ceļos | P55, §78 |
| 6 | **G7** | Stale skip + cycle timeout | §79.3, §79.4 |
| 7 | **G2** | MT4 `command.volume` close | §57.2 end-to-end partial close |
| 8 | **G8** | ACK poll ar `command_id` | Mazāk ACK edge case |
| 9 | **G10** | E2E MODIFY/CLOSE testi | Regression aizsardzība |
| 10 | **G9** | Path traversal validācija | Drošāka identitāte |
| 11 | **G11** | IMPLEMENTATION_PLAN P75+, doc sync | Procesa skaidrība |

**Paralēli iespējams:** G3 (solis 2) var sākt vienlaikus ar G1; G9 (solis 10) var būt neatkarīgs no G10.

---

## 6. High punktu → grupu kartējums

| Audita ID | Grupa |
|-----------|-------|
| AUDIT-STATE-001 | G1 |
| AUDIT-MT4-001 | G2 |
| AUDIT-SPEC-002 | G3 |
| AUDIT-ARCH-002, RECOV-001, PERF-001 | G4 |
| AUDIT-RECOV-002 | G5 |
| AUDIT-EXEC-004, DEAD-HIGH-002 | G5 |
| AUDIT-SPEC-003, IO-001, DEAD-HIGH-001 | G6 |
| AUDIT-SPEC-004 | G7 |
| AUDIT-SPEC-005 | G7 |
| AUDIT-EXEC-003 | G8 |
| AUDIT-TEST-001 | G10 |
| AUDIT-SEC-001 | G9 |
| AUDIT-PLAN-001 | G11 |

---

## 7. Pēc High fixes sagaidāmais stāvoklis

| Metrika | Tagad | Mērķis pēc plāna |
|---------|-------|------------------|
| Critical | 0 | 0 |
| High | 16 | **0** |
| Medium | 31 | 31 (nav šī plāna apjomā) |
| Low | 17 | 17 (nav šī plāna apjomā) |
| §100.10–100.11 operacionāli | Daļēji | **Pilnīgāk** (ar G1+G2+G10) |
| IMPLEMENTATION_PLAN atbilstība | Daļēja | **Tuvāka** (G11, G7 P67 sync) |

---

*Plāna beigas. Tikai `HIGH_FIX_PLAN.md` izveidots; kods nav labots.*
