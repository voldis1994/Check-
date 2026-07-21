# SYSTEM v1.1.3

Hotfix (2026-07-21): MetaEditor compile — `function not defined`.

## Hotfix
- Explicit `#include <SYSTEM_Status.mqh>` EA failā
- Include ķēde izmanto `"SYSTEM_*.mqh"` (same-folder), lai neņemtu vecus headerus
- `FIX_MT4` / copy script pārbauda `SYSTEM_LoadProcessedCommandId` + `SYSTEM_ExportClosedTrade`
- Print warning: `IntegerToString(magic)`

## Deploy

```bat
cd C:\Check\System
git pull
UZSTADIT.bat
FIX_MT4.bat
```

1. Aizver MetaEditor
2. Palaid `FIX_MT4.bat` (jābūt OK abām funkcijām)
3. Atver **tikait** `Experts\SYSTEM_EA.mq4` no MT4 Data Folder
4. F7 → **0 errors**
5. Attach EURUSD M1 → `PALAID.bat`
