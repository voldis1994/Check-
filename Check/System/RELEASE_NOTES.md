# SYSTEM v1.1.5

Hotfix (2026-07-21): false `stale market bar blocks new OPEN` + `ENTRY_DEFERRED` eating bars.

## What you saw
- `bar_content_freshness_ms=108720` + `market_file_freshness_ms=12849` → file live, closed M1 bar open-time ~1.8 min old (normal)
- `ENTRY_DEFERRED` after HOLD cycles on the same bar
- Trailing `MODIFY` working (good)

## Fix
- Closed-bar mode measures bar staleness from **bar close** (open+60s), not open time — 108s open age is not stale
- `ENTRY_DEFERRED` only after an actual ALLOW OPEN on that bar; HOLD/BLOCK no longer consumes the bar
- OPEN blockers (stale/status/pending) run **before** closed-bar stamp

## Deploy

```bat
cd C:\Check\System
git pull
UZSTADIT.bat
PALAID.bat
```

EA compile only needed if MetaEditor still broken (v1.1.4 Include fix).
