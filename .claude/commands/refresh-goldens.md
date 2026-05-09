---
description: Regenerate committed golden translations. Only run after deliberate prompt or scoring changes.
allowed-tools: Bash(python scripts/refresh_goldens.py)
---

This **overwrites** committed goldens under `tests/golden/`. Run it
intentionally, after a prompt or scoring change you've already validated.
Confirm the diff is what you expect before committing.

!`python scripts/refresh_goldens.py`
