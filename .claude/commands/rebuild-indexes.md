---
description: Rebuild the SQLite-backed derived indexes (concordance, lexical, witnesses, jobs).
allowed-tools: Bash(python scripts/build_indexes.py)
---

Rebuild derived indexes. Safe to run any time — overwrites
`data/derived/indexes/workbench.sqlite3`.

!`python scripts/build_indexes.py`
