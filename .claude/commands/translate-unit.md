---
description: Run a single translation pass for a unit at a given layer.
argument-hint: <unit_id> <layer> [style_profile]
allowed-tools: Bash(psalms-workbench translate-unit:*)
---

Translate unit `$1` at layer `$2` (style profile defaults to `study_literal`
if omitted).

Layers: `gloss`, `literal`, `phrase`, `concept`, `lyric`, `metered_lyric`,
`parallelism_lyric`.

!`psalms-workbench translate-unit $1 $2`
