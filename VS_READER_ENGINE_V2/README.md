# SYSTEM

Pilnīgi jauna, daudzkontu un daudzinstrumentu M1 tirdzniecības platforma. Python pieņem visus lēmumus. MT4 eksportē datus un izpilda orderus. Dashboard tikai attēlo stāvokli.

Projekta sakne: `C:\SYSTEM`

## Prasības

| Komponents | Versija |
|------------|---------|
| Python | 3.11 vai jaunāks |
| MetaTrader 4 | Ar `SYSTEM_EA.mq4` |
| OS | Windows (MT4 datu ceļi) |

## Uzstādīšana

### Automātiski (Windows — viens fails)

**Vienkāršākais:** lejupielādējiet un dubultklikšķiniet:

https://github.com/voldis1994/VS_READER_ENGINE_V2/raw/main/SYSTEM/scripts/LEJUPIELADE_UZREIZ.bat

Viss tiks uzstādīts mapē `C:\SYSTEM` automātiski.

**PowerShell (viena komanda):**

```powershell
Set-ExecutionPolicy Bypass -Scope Process -Force; iex ((New-Object Net.WebClient).DownloadString('https://raw.githubusercontent.com/voldis1994/VS_READER_ENGINE_V2/main/SYSTEM/scripts/lejupielade_uzreiz.ps1'))
```

Papildu instrukcijas: `scripts/LEJUPIELADE.txt`

### Manuāli

```bash
cd C:\SYSTEM
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Linux/macOS izstrādes vidē:

```bash
cd /path/to/SYSTEM
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Pārbaude

```bash
python --version
pip install -r requirements.txt
pytest
```

`python --version` jābūt 3.11 vai jaunākam.

## AI lēmumu slānis (OpenAI)

SYSTEM pēc pamata signāla (BUY/SELL/WAIT/BLOCK) var izsaukt OpenAI konsultatīvo slāni.

1. Uzstādiet API atslēgu Windows vidē pirms `run_live.py` palaišanas:

```powershell
setx OPENAI_API_KEY "sk-..."
```

Jaunā konsolē pārbaudiet: `echo %OPENAI_API_KEY%`

2. Konfigurācija `config/system.json` sadaļā `ai`:

| Lauks | Noklusējums | Apraksts |
|-------|-------------|----------|
| `mode` | `advisory` | `advisory` — AI kļūda atgriež SYSTEM signālu; `required` — AI kļūda = BLOCK |
| `fail_closed` | `false` | `true` uzvedas kā obligāts AI pat advisory režīmā |
| `reject_action` | `BLOCK` | Kad AI noraida BUY/SELL: `BLOCK` vai `WAIT` |
| `timeout_ms` | `10000` | OpenAI pieprasījuma timeouts ms |
| `retry_max` | `2` | HTTP kļūdu/timeout mēģinājumu skaits |
| `retry_delay_ms` | `500` | Pauze starp mēģinājumiem ms |

**Advisory režīmā** (noklusējums): ja OpenAI nav pieejams, SYSTEM turpina ar savu signālu. **Required režīmā** vai `fail_closed: true`: bez AI atbildes viss kļūst par BLOCK.

**Pilna plūsma:** `decide → AI → risk → journal → trade management → execution`

## MT4 (MetaEditor) uzstādīšana

Kompilācijas kļūda `can't open ... SYSTEM_Execution.mqh` nozīmē, ka **`.mqh` faili nav MT4 `Include` mapē**. Visas 11 kļūdas pazudīs pēc pareizas kopēšanas.

1. Atver MT4: **File → Open Data Folder** — iekšā ir `MQL4\Include` un `MQL4\Experts`.
2. No `C:\SYSTEM\mql4\Include\` (vai repo `SYSTEM/mql4/Include/`) **nokopē visus** failus uz savu `MQL4\Include\`:

   - `SYSTEM_Execution.mqh`
   - `SYSTEM_Control.mqh`
   - `SYSTEM_Status.mqh`
   - `SYSTEM_Export.mqh`
   - `SYSTEM_IO.mqh`
   - `SYSTEM_Paths.mqh`
   - `SYSTEM_Universe.mqh`

3. `SYSTEM_EA.mq4` nokopē uz `MQL4\Experts\` (vai pārsauc uz `VS.mq4`, ja vēlies).
4. EA kodā obligāti: `input int MagicNumber = 100001;` un `#include <SYSTEM_Universe.mqh>` (pēc `SYSTEM_Execution.mqh`).
5. MetaEditor: **Compile** (F7). Chart: timeframe **M1**.

**Svarīgi:** ja atjaunini kodu, **nokopē visus** `Include\SYSTEM_*.mqh` no jauna — daļēja kopēšana rada `function not defined` / `wrong parameters count`.

Tavs ceļš no ekrānšāviena: `C:\VS1\VS_STAGE_02_MT4_MANAGER\mt4_template\MQL4\Include\` — tieši tur jābūt visiem `.mqh` failiem.

## Projekta struktūra

```
SYSTEM/
├── config/system.json      Vienīgā konfigurācija
├── data/                   Visi runtime dati
├── docs/                   Noteikumi, specifikācija, plāns
├── engine/                 Python loģika
├── mql4/                   MT4 EA
├── tests/                  Automatizētie testi
├── run_live.py             Live engine
└── dashboard.py            Dashboard
```

## Dokumentācija

| Dokuments | Mērķis |
|-----------|--------|
| `docs/RULES.md` | Obligātie sistēmas noteikumi |
| `docs/SYSTEM_SPECIFICATION.md` | Tehniskā specifikācija |
| `docs/IMPLEMENTATION_PLAN.md` | Izstrādes plāns (P01–P75) |

## Palaišana

```bash
cd C:\VS_READER_ENGINE_V2\SYSTEM
scripts\start_live.bat
```

Vai manuāli:

```bash
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python run_live.py
python dashboard.py
```

`run_live.py` automātiski izmanto savu mapi kā sakni un, ja vajag, atjaunina `config/system.json` → `system.root_path`.

Pilna LIVE palaišana prasa pabeigtu `docs/IMPLEMENTATION_PLAN.md` līdz P74 un P75 audit fix posmu.

## Instance modelis

Katra izolēta instance ir definēta kā:

```
Account + Symbol + Magic
```

Katrai instancei ir savs state, spread modelis, journal, risks un execution kanāls.
