# Changelog

## v3.0.0

- Full rebuild from zero for CHECK SYSTEM v3.
- Python owns regime detection, strategy routing, risk checks, trade management, state, audit, and command generation.
- MT4 is reduced to a transport bridge that exports MARKET/STATUS JSON and applies COMMAND JSON with ACK output.
- Protocol version is `3.0.0`.
- v2 is preserved in git tag `system-v2-final-backup` and branch `backup/system-v2-before-v3-rebuild`.
