# SYSTEM — Sistēmas noteikumi

Šis dokuments ir SYSTEM tirdzniecības platformas obligāto noteikumu pilns saraksts. Visi moduļi, konfigurācija, MT4 komponents un operacionālā loģika šos noteikumus ievēro bez izņēmumiem.

SYSTEM ir pilnīgi jauna platforma, kas būvēta no nulles. Šie noteikumi neattiecas uz nekādu iepriekšēju sistēmu un neparedz saderību ar veco kodu.

---

## 1. Sistēmas robežas

| Komponents | Atbildība |
|------------|-----------|
| **Python** | Pieņem visus tirdzniecības lēmumus |
| **MT4** | Eksportē datus, lasa control, izpilda orderus |
| **Dashboard** | Rāda stāvokli; neanalizē un nepieņem lēmumus |

MT4 nekad neanalizē tirgu. MT4 nekad neizlemj BUY, SELL, WAIT vai BLOCK.

---

## 2. Projekta vieta un dati

- Visa sistēma dzīvo tikai zem `C:\Check\System`.
- Viena konfigurācija: `config/system.json`.
- Visi dati dzīvo zem `data/`.
- Konfigurācija un dati netiek glabāti ārpus SYSTEM saknes.

---

## 3. Timeframe

- **M1** ir vienīgais atļautais timeframe.
- Neviens modulis neizmanto, neaprēķina un negaida citus timeframes.
- Visi tirgus dati, analīze un lēmumi balstās uz M1.

---

## 4. Multi-account un multi-symbol

- Sistēma atbalsta vairākus kontus vienlaikus.
- Sistēma atbalsta vairākus instrumentus vienlaikus.
- Katrs konts un katrs instruments tiek apstrādāts atsevišķi saskaņā ar instance noteikumiem (5. sadaļa).

---

## 5. Instance izolācija

**Account + Symbol + Magic = viena pilnīgi izolēta instance.**

Katrai instancei ir savi, nesadalīti resursi:

- state
- spread model
- journal
- risk
- control

Instances nedalās starpā stāvoklī, žurnālos, riska vērtējumos vai kontroles komandās. Viena instance kļūda vai bloķēšana neietekmē citu instanču izolēto darbu.

---

## 6. Universe

- Universe ir tikai tirgus konteksts.
- Universe sniedz informāciju par vidi, kuru analīze un lēmumi var izmantot.
- Universe **nekad** nedrīkst kļūt par trade job.
- Universe neizraisa orderus, neaktivizē execution un nepieņem lēmumus.

---

## 7. Lēmumu pieņemšana

### 7.1. Obligātais secības princips

1. Aprēķini **BUY** setup.
2. Aprēķini **SELL** setup.
3. Salīdzini abus ar scoring.
4. Piemēro risk (ALLOW vai BLOCK).
5. Pieņem gala lēmumu ar reason.
6. Pieraksti lēmumu journal.

### 7.2. BUY un SELL

- BUY un SELL **vienmēr** tiek aprēķināti abi katrā lēmumu ciklā.
- Ja BUY setup neder, **obligāti** pārbaudi SELL.
- Ja SELL setup neder, **obligāti** pārbaudi BUY.
- Neviens modulis nedrīkst izlaist vienu virzienu, neanalizējot otru.

### 7.3. WAIT

- WAIT **nekad** nav noklusējuma lēmums.
- WAIT tiek pieņemts tikai tad, ja pēc pilnas BUY un SELL izvērtēšanas neviens virziens nav pieņemams, un tam ir skaidrs, konkrēts reason.
- WAIT nedrīkst aizstāt neizpildītu SELL pārbaudi vai neizpildītu BUY pārbaudi.

### 7.4. Scoring

- Scoring **nav** filtrs.
- Scoring **salīdzina** BUY pret SELL.
- Scoring neizslēdz virzienus pirms to pilnas izvērtēšanas; tas nosaka relatīvo pārsvaru starp jau izvērtētiem setup.

### 7.5. Risk

- Risk **nedod** WAIT.
- Risk dod tikai **ALLOW** vai **BLOCK**.
- Ja risk ir BLOCK, trade nenotiek neatkarīgi no scoring rezultāta.
- Katram BLOCK ir jābūt reason.

### 7.6. Gala lēmumu veidi

Katrs lēmumu cikls beidzas ar vienu no:

| Lēmums | Nozīme |
|--------|--------|
| **BUY** | Atļauts un izvēlēts pirkšanas virziens |
| **SELL** | Atļauts un izvēlēts pārdošanas virziens |
| **WAIT** | Neviens virziens nav pieņemams pēc pilnas izvērtēšanas |
| **BLOCK** | Risks vai cits obligāts šķērslis aizliedz trade |

Katram BUY, SELL, WAIT un BLOCK **obligāti** ir reason.

---

## 8. Spread

- Spread **nav** ciets skaitlis.
- Spread tiek vērtēts **dinamiski** pret konkrētā instrumenta normālo spread vēsturi.
- Katram instrumentam ir savs spread model (saistīts ar instance izolāciju).
- Aizliegti cieti max spread skaitļi konfigurācijā vai kodā.
- Spread vērtējums balstās uz instrumenta paša vēsturisko normu, nevis uz globāliem limitiem.

---

## 9. Instrumentu parametri

- Aizliegti cieti symbol saraksti.
- Aizliegtas cietas digits, point vai pip vērtības.
- Instrumenta parametri nāk no tirgus datiem un MT4 eksporta, nevis no iepriekš definētiem sarakstiem.
- Sistēma pielāgojas instrumentam, nevis filtrē instrumentus pēc fiksēta saraksta.

---

## 10. Journal

- Katrs lēmums **obligāti** jāieraksta journal.
- Journal ierakstā ir lēmums, reason un instance identifikators (Account + Symbol + Magic).
- Journal ir instance līmeņa resurss; instances nedalās žurnālos ar citām instancēm.

---

## 11. Dashboard

- Dashboard **neko neanalizē**.
- Dashboard **tikai rāda** esošo stāvokli, lēmumus, reason un operacionālos datus.
- Dashboard nepieņem lēmumus, nemaina control un neietekmē risk.

---

## 12. Moduļu atbildība

- Katrs modulis dara **tikai vienu** konkrētu darbu.
- Modulis nedublē cita moduļa atbildību.
- Modulis neapiet noteikumus, pievienojot blakus loģiku citam modulim paredzētajam darbam.

---

## 13. Kļūdu apstrāde

- Kļūdas **nedrīkst** slēpt ar silent exception.
- Ja dati ir bojāti vai trūkst, **trade nenotiek**.
- Kļūda **obligāti** tiek pierakstīta.
- Kļūdas pierakstā ir pietiekama informācija, lai identificētu instance, datu avotu un cēloni.
- Daļēji bojāti dati nevar izraisīt noklusējuma WAIT vai noklusējuma trade.

---

## 14. Obligāto noteikumu kopsavilkums

| # | Noteikums |
|---|-----------|
| 1 | M1 ir vienīgais timeframe |
| 2 | Sistēma ir multi-account |
| 3 | Sistēma ir multi-symbol |
| 4 | Account + Symbol + Magic = viena pilnīgi izolēta instance |
| 5 | Katram instrumentam ir savs state, spread model, journal, risk un control |
| 6 | Python pieņem visus tirdzniecības lēmumus |
| 7 | MT4 tikai eksportē datus, lasa control un izpilda orderus |
| 8 | MT4 nekad neanalizē tirgu |
| 9 | Universe ir tikai tirgus konteksts |
| 10 | Universe nekad nedrīkst kļūt par trade job |
| 11 | BUY un SELL vienmēr tiek aprēķināti abi |
| 12 | WAIT nekad nav noklusējuma lēmums |
| 13 | Ja BUY setup neder, obligāti pārbaudi SELL |
| 14 | Ja SELL setup neder, obligāti pārbaudi BUY |
| 15 | Scoring nav filtrs; scoring salīdzina BUY pret SELL |
| 16 | Risk nedod WAIT; risk dod tikai ALLOW vai BLOCK |
| 17 | Spread nav ciets skaitlis |
| 18 | Spread tiek vērtēts dinamiski pret konkrētā instrumenta normālo spread vēsturi |
| 19 | Nekādu cietu max spread skaitļu |
| 20 | Nekādu cietu symbol sarakstu |
| 21 | Nekādu cietu digits, point vai pip vērtību |
| 22 | Katram BUY, SELL, WAIT un BLOCK ir jābūt reason |
| 23 | Katrs lēmums jāieraksta journal |
| 24 | Dashboard neko neanalizē; dashboard tikai rāda |
| 25 | Visi moduļi dara tikai vienu konkrētu darbu |
| 26 | Kļūdas nedrīkst slēpt ar silent exception |
| 27 | Ja dati ir bojāti vai trūkst, trade nenotiek un kļūda tiek pierakstīta |
| 28 | Viena konfigurācija: `config/system.json` |
| 29 | Visi dati dzīvo zem `data/` |
| 30 | Visa sistēma dzīvo tikai zem `C:\Check\System` |

---

## 15. Izstrādes principi

Šie principi attiecas uz visu SYSTEM izstrādi:

- Neizmanto veco kodu.
- Neizmanto patch pieeju.
- Neizdomā legacy compatibility.
- Neraksta TODO.
- Neraksta placeholder.
- Neraksta liekus komentārus kodā.
- Neraksta pusgatavus failus.

Jauzstrādāts modulis ir pabeigts, noteikumus ievērojošs un gatavs integrācijai — ne starpposma melnraksts.

---

*Šis dokuments ir obligāts avots visai SYSTEM loģikai. Pretrunā starp moduļu implementāciju un šiem noteikumiem pareizi ir noteikumi.*
