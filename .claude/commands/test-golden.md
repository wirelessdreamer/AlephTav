---
description: Run golden tests under tests/golden/. Slower; runs translation/quality goldens.
allowed-tools: Bash(python -m pytest tests/golden:*)
---

!`python -m pytest tests/golden -q`
