# LEGACY_DELETE_REPORT.md

Generated during SYSTEM v2.0.0 rewrite.

| Old path | Function | V2 replacement | Status | Not ported |
|----------|----------|----------------|--------|------------|
| `engine` | Legacy Python trading engine (cycle, decision, risk, protocol) | src/checktrader/ | deleted | AI advisory / score entry / cooldown not ported |
| `run_live.py` | Legacy live entrypoint | python -m checktrader | deleted |  |
| `dashboard.py` | Legacy console dashboard | src/checktrader/dashboard/ | deleted |  |
| `mql4` | Legacy SYSTEM_EA and includes | mt4/ | deleted |  |
| `requirements.txt` | pip requirements | pyproject.toml | deleted |  |
| `pytest.ini` | Legacy pytest config conflicting with src layout | pyproject.toml [tool.pytest.ini_options] | deleted |  |
| `RELEASE_NOTES.md` | Legacy release notes | CHANGELOG.md | deleted |  |
| `config/system.json` | Live account config (secrets) | config/system.example.json + config/local/system.json (gitignored) | deleted |  |
| `ANALIZE_SERIJA.bat` | Legacy Windows launcher | scripts/*.ps1 | deleted |  |
| `DASHBOARD.bat` | Legacy Windows launcher | scripts/*.ps1 | deleted |  |
| `FIX_MT4.bat` | Legacy Windows launcher | scripts/*.ps1 | deleted |  |
| `KONTI.bat` | Legacy Windows launcher | scripts/*.ps1 | deleted |  |
| `PALAID.bat` | Legacy Windows launcher | scripts/*.ps1 | deleted |  |
| `PARBAUDI.bat` | Legacy Windows launcher | scripts/*.ps1 | deleted |  |
| `START.bat` | Legacy Windows launcher | scripts/*.ps1 | deleted |  |
| `UZSTADIT.bat` | Legacy Windows launcher | scripts/*.ps1 | deleted |  |
| `scripts/copy_mql4_to_mt4.bat` | Legacy install/sync scripts | scripts/install.ps1, start_live.ps1, ... | deleted |  |
| `scripts/generate_mql4_root.ps1` | Legacy install/sync scripts | scripts/install.ps1, start_live.ps1, ... | deleted |  |
| `scripts/install_linux.sh` | Legacy install/sync scripts | scripts/install.ps1, start_live.ps1, ... | deleted |  |
| `scripts/install_windows.bat` | Legacy install/sync scripts | scripts/install.ps1, start_live.ps1, ... | deleted |  |
| `scripts/install_windows.ps1` | Legacy install/sync scripts | scripts/install.ps1, start_live.ps1, ... | deleted |  |
| `scripts/LEJUPIELADE_UZREIZ.bat` | Legacy install/sync scripts | scripts/install.ps1, start_live.ps1, ... | deleted |  |
| `scripts/lejupielade_uzreiz.ps1` | Legacy install/sync scripts | scripts/install.ps1, start_live.ps1, ... | deleted |  |
| `scripts/start_live.bat` | Legacy install/sync scripts | scripts/install.ps1, start_live.ps1, ... | deleted |  |
| `scripts/sync_paths.py` | Legacy install/sync scripts | scripts/install.ps1, start_live.ps1, ... | deleted |  |
| `tools/analyze_trade_series.py` | Legacy tooling | tools/inspect_bridge.py, validate_config.py, reconcile_account.py, export_audit.py, replay.py | deleted |  |
| `tools/diagnose_skip.py` | Legacy tooling | tools/inspect_bridge.py, validate_config.py, reconcile_account.py, export_audit.py, replay.py | deleted |  |
| `tools/replay_signals.py` | Legacy tooling | tools/inspect_bridge.py, validate_config.py, reconcile_account.py, export_audit.py, replay.py | deleted |  |
| `tools/show_paths.py` | Legacy tooling | tools/inspect_bridge.py, validate_config.py, reconcile_account.py, export_audit.py, replay.py | deleted |  |
| `tools/validate_live.py` | Legacy tooling | tools/inspect_bridge.py, validate_config.py, reconcile_account.py, export_audit.py, replay.py | deleted |  |
| `tools/validate_order_command.py` | Legacy tooling | tools/inspect_bridge.py, validate_config.py, reconcile_account.py, export_audit.py, replay.py | deleted |  |
| `tools/__init__.py` | Legacy tooling | tools/inspect_bridge.py, validate_config.py, reconcile_account.py, export_audit.py, replay.py | deleted |  |
| `docs/ARCHITECTURE.md.bak` | Legacy documentation | docs/{ARCHITECTURE,LIVE_OPERATION,MT4_PROTOCOL,STRATEGY,TRAILING,EXIT_PRESSURE,RISK,TROUBLESHOOTING}.md | already_absent |  |
| `docs/IMPLEMENTATION_PLAN.md` | Legacy documentation | docs/{ARCHITECTURE,LIVE_OPERATION,MT4_PROTOCOL,STRATEGY,TRAILING,EXIT_PRESSURE,RISK,TROUBLESHOOTING}.md | deleted |  |
| `docs/ORDER_COMMAND.md` | Legacy documentation | docs/{ARCHITECTURE,LIVE_OPERATION,MT4_PROTOCOL,STRATEGY,TRAILING,EXIT_PRESSURE,RISK,TROUBLESHOOTING}.md | deleted |  |
| `docs/PROTOCOL.md` | Legacy documentation | docs/{ARCHITECTURE,LIVE_OPERATION,MT4_PROTOCOL,STRATEGY,TRAILING,EXIT_PRESSURE,RISK,TROUBLESHOOTING}.md | deleted |  |
| `docs/RULES.md` | Legacy documentation | docs/{ARCHITECTURE,LIVE_OPERATION,MT4_PROTOCOL,STRATEGY,TRAILING,EXIT_PRESSURE,RISK,TROUBLESHOOTING}.md | deleted |  |
| `docs/SIGNAL_QUALITY.md` | Legacy documentation | docs/{ARCHITECTURE,LIVE_OPERATION,MT4_PROTOCOL,STRATEGY,TRAILING,EXIT_PRESSURE,RISK,TROUBLESHOOTING}.md | deleted |  |
| `docs/SYSTEM_SPECIFICATION.md` | Legacy documentation | docs/{ARCHITECTURE,LIVE_OPERATION,MT4_PROTOCOL,STRATEGY,TRAILING,EXIT_PRESSURE,RISK,TROUBLESHOOTING}.md | deleted |  |
| `data` | Legacy runtime data trees | runtime/ | deleted |  |
| `tests/ai` | Legacy test suite / fixtures for engine/ | tests/{unit,integration,protocol,strategy,risk,trailing,state,e2e} | deleted |  |
| `tests/analysis` | Legacy test suite / fixtures for engine/ | tests/{unit,integration,protocol,strategy,risk,trailing,state,e2e} | deleted |  |
| `tests/audit` | Legacy test suite / fixtures for engine/ | tests/{unit,integration,protocol,strategy,risk,trailing,state,e2e} | deleted |  |
| `tests/core` | Legacy test suite / fixtures for engine/ | tests/{unit,integration,protocol,strategy,risk,trailing,state,e2e} | deleted |  |
| `tests/dashboard` | Legacy test suite / fixtures for engine/ | tests/{unit,integration,protocol,strategy,risk,trailing,state,e2e} | deleted |  |
| `tests/decision` | Legacy test suite / fixtures for engine/ | tests/{unit,integration,protocol,strategy,risk,trailing,state,e2e} | deleted |  |
| `tests/deployment` | Legacy test suite / fixtures for engine/ | tests/{unit,integration,protocol,strategy,risk,trailing,state,e2e} | deleted |  |
| `tests/execution` | Legacy test suite / fixtures for engine/ | tests/{unit,integration,protocol,strategy,risk,trailing,state,e2e} | deleted |  |
| `tests/hardening` | Legacy test suite / fixtures for engine/ | tests/{unit,integration,protocol,strategy,risk,trailing,state,e2e} | deleted |  |
| `tests/journal` | Legacy test suite / fixtures for engine/ | tests/{unit,integration,protocol,strategy,risk,trailing,state,e2e} | deleted |  |
| `tests/loader` | Legacy test suite / fixtures for engine/ | tests/{unit,integration,protocol,strategy,risk,trailing,state,e2e} | deleted |  |
| `tests/mql4` | Legacy test suite / fixtures for engine/ | tests/{unit,integration,protocol,strategy,risk,trailing,state,e2e} | deleted |  |
| `tests/normalizer` | Legacy test suite / fixtures for engine/ | tests/{unit,integration,protocol,strategy,risk,trailing,state,e2e} | deleted |  |
| `tests/performance` | Legacy test suite / fixtures for engine/ | tests/{unit,integration,protocol,strategy,risk,trailing,state,e2e} | deleted |  |
| `tests/replay` | Legacy test suite / fixtures for engine/ | tests/{unit,integration,protocol,strategy,risk,trailing,state,e2e} | deleted |  |
| `tests/tools` | Legacy test suite / fixtures for engine/ | tests/{unit,integration,protocol,strategy,risk,trailing,state,e2e} | deleted |  |
| `tests/conftest.py` | Legacy test suite / fixtures for engine/ | tests/{unit,integration,protocol,strategy,risk,trailing,state,e2e} | deleted |  |
| `tests/e2e/test_full_cycle.py` | Legacy test targeting engine/ | v2 tests under same category | deleted |  |
| `tests/e2e/test_trade_management_cycle.py` | Legacy test targeting engine/ | v2 tests under same category | deleted |  |
| `tests/e2e/simulator/mt4_simulator.py` | Legacy test targeting engine/ | v2 tests under same category | deleted |  |
| `tests/integration/test_decision_pipeline.py` | Legacy test targeting engine/ | v2 tests under same category | deleted |  |
| `tests/integration/test_ai_decision_pipeline.py` | Legacy test targeting engine/ | v2 tests under same category | deleted |  |
| `tests/protocol/test_constants.py` | Legacy test targeting engine/ | v2 tests under same category | deleted |  |
| `tests/risk/test_be_plus_pip_trailing.py` | Legacy test targeting engine/ | v2 tests under same category | deleted |  |
| `tests/risk/test_trade_management.py` | Legacy test targeting engine/ | v2 tests under same category | deleted |  |
| `tests/risk/test_sl_tp.py` | Legacy test targeting engine/ | v2 tests under same category | deleted |  |
| `tests/risk/test_rules.py` | Legacy test targeting engine/ | v2 tests under same category | deleted |  |
| `tests/risk/test_position_sizing.py` | Legacy test targeting engine/ | v2 tests under same category | deleted |  |
| `tests/risk/test_metrics.py` | Legacy test targeting engine/ | v2 tests under same category | deleted |  |
| `tests/risk/test_layering.py` | Legacy test targeting engine/ | v2 tests under same category | deleted |  |
| `tests/risk/test_engine.py` | Legacy test targeting engine/ | v2 tests under same category | deleted |  |
| `tests/state/test_spread_state.py` | Legacy test targeting engine/ | v2 tests under same category | deleted |  |
| `tests/state/test_memory.py` | Legacy test targeting engine/ | v2 tests under same category | deleted |  |
| `tests/state/test_instance_state.py` | Legacy test targeting engine/ | v2 tests under same category | deleted |  |

## Intentionally not ported

- Relative BUY/SELL score entry
- Mandatory post-trade / post-loss cooldown
- AI advisory as hard entry gate
- Universe/news WAIT factory
- Silent lot normalization without config flag

## Verification

```
rg "legacy|deprecated|old_engine|run_live|from engine" src tests
```
