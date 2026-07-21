# SYSTEM v1.1.4

Hotfix (2026-07-21): MetaEditor `can't open ...\Include\SYSTEM_...` / function not defined.

## Root cause
MQL4 `#include "file.mqh"` meklē **Experts\** (kompilējamā faila mape), nevis Include\.
v1.1.3 nested quote-includes lauza ķēdi → Paths/Status/Control netika ielādēti.

## Hotfix
- Visi `SYSTEM_*.mqh` nested includes atpakaļ uz `#include <SYSTEM_*.mqh>` (Include\)
- `FIX_MT4.bat` bez argumentiem kopē uz **visām** `%APPDATA%\MetaQuotes\Terminal\*\MQL4`
- EA `#property version` = `1.1.4`

## Deploy

```bat
cd C:\Check\System
git pull
UZSTADIT.bat
FIX_MT4.bat
```

1. **Aizver MetaEditor** (lai atbrīvotu .mqh)
2. Palaid `FIX_MT4.bat` — jābūt OK visām Terminal mapēm
3. MT4 → File → Open Data Folder → `MQL4\Experts\SYSTEM_EA.mq4`
4. F7 → **0 errors**
5. Attach EURUSD M1 → `PALAID.bat`

Ja kļūda rāda HASH `C879C699...`, var arī:
```bat
FIX_MT4.bat "%APPDATA%\MetaQuotes\Terminal\C879C699A2AEBE2E45B5D3054ECC35E8\MQL4"
```
