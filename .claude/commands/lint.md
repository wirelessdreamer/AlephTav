---
description: Check lint, format, and types. Read-only — does not fix.
allowed-tools: Bash(ruff:*), Bash(mypy:*)
---

!`ruff check . && ruff format --check . && mypy app`
