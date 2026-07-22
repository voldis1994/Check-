# Legacy delete plan (V2)

Executed only after v2 package installs, tests pass, and MT4 protocol fixtures are green.

## Must preserve until replacement ready

| Path | Until |
|------|-------|
| `.git` / tags / `archive/legacy-v1` | forever |
| `mql4/**` | `mt4/Experts/CHECK_SYSTEM_V2.mq4` protocol tests pass |
| `.github/workflows` | new `ci.yml` present |
| Root / System README | new README written |

## Delete / replace map

| Old path | Action | V2 replacement |
|----------|--------|----------------|
| `engine/` | DELETE | `src/checktrader/` |
| `tests/` (v1 suite) | DELETE | `tests/{unit,integration,protocol,strategy,risk,trailing,state,e2e}/` |
| `run_live.py` | DELETE | `python -m checktrader` |
| `dashboard.py` | DELETE | `src/checktrader/dashboard/` |
| `requirements.txt` | DELETE | `pyproject.toml` extras |
| `pytest.ini` | REPLACE | pyproject `[tool.pytest.ini_options]` |
| `VERSION` | REPLACE | `pyproject.toml` version `2.0.0` |
| `config/system.json` (with live account) | DELETE from git | `config/system.example.json` + ignored `config/local/` |
| `data/` tracked trees | REMOVE from git | `runtime/` + `.gitkeep` |
| Root `*.bat` | DELETE | `scripts/*.ps1` |
| `scripts/install_windows.*`, `LEJUPIELADE_*` | DELETE | `scripts/install.ps1` |
| `tools/*` v1 | DELETE/REWRITE | `tools/{inspect_bridge,validate_config,reconcile_account,export_audit,replay}.py` |
| `mql4/` | DELETE after cutover | `mt4/` |
| Overlapping docs | DELETE/REWRITE | `docs/{ARCHITECTURE,LIVE_OPERATION,MT4_PROTOCOL,STRATEGY,TRAILING,EXIT_PRESSURE,RISK,TROUBLESHOOTING}.md` |

## Intentionally not ported

- BUY/SELL relative score entry
- Mandatory post-trade / post-loss cooldown
- AI advisory veto layer as entry gate
- Universe news as hard WAIT factory
- Silent lot normalization without config flag

## Verification after delete

```
rg "legacy|deprecated|old_engine|run_live|from engine" src tests
```

Only docs/migration hits allowed.
