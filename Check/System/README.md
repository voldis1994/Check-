# SYSTEM

Python M1 trading platform. Python decides. MT4 exports data and executes orders.

Deploy root: `C:\Check\System`

## Setup

```bat
cd C:\Check\System
UZSTADIT.bat
PALAID.bat
```

`UZSTADIT.bat` and `PALAID.bat` automatically run `scripts\sync_paths.py` so Python config, MQL4 root, and runtime root stay aligned.

Or install from GitHub:

```bat
powershell -ExecutionPolicy Bypass -File scripts\install_windows.ps1
```

## Run

```bat
python scripts\sync_paths.py
python tools\show_paths.py
python tools\validate_live.py
PALAID.bat
```

MT4 EA `SystemRootPath` must match `config/system.json` `system.root_path`.

## Tests

```bat
pytest
pytest tests/deployment -m deployment
```
