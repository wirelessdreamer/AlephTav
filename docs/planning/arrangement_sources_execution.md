# Arrangement verse sources correction

Date: 2026-10-17. Backend slice for the user's correction that **each verse block in
the arrangement Sources ribbon needs Hebrew and Greek**. The UI workstream owns rendering.

`arrangement_service.arrangement_view` now supplies `greek_sources` using the existing
`BriefingGreekSources` contract. The current arrangement GET route returns this projection
without a new endpoint or stored content field. Hebrew coverage remains present when Greek
is missing, blocked or unverifiable. Arrangement mutations also return the same updated view.

Greek evidence is keyed by actual MT unit IDs. Only reviewed maps matching the published
Greek edition and text revision supply counterparts. Split/merged/title mappings retain real
Greek references, physical token order and all mapped units. Subverse spans are validated
against source text, retained as `mapped_spans`, and labeled partial while the full Greek
verse is displayed. Explicit edition-absent/MT-only mapping rows remain distinguishable from
an unknown correspondence; no ordinal offsets or Hebrew-order MACULA fallback are used.

The reused `briefing_source_service.greek_evidence` now rechecks manifest and map byte hashes
when reading them after catalog loading. It rechecks current policy identity and release
availability before returning projected text/glosses. Expected missing/policy/corrupt-source
errors yield an explicit empty Greek state, preserving the rest of the arrangement. Error
messages for blocked or corrupt data do not include upstream source text or dictionary glosses.
The provider retains compatibility with the existing briefing UI.

Changed files:

- `app/services/arrangement_service.py`
- `app/api/routes/arrangements.py` (read-route documentation only)
- `app/services/briefing_source_service.py`
- `tests/unit/test_arrangement_sources.py`
- `tests/unit/test_briefing_sources.py`
- `docs/planning/arrangement_sources_execution.md`

Validation performed with authored temporary fixtures, no production activation:

```text
.venv/Scripts/python.exe -m pytest tests/unit/test_arrangement_sources.py tests/unit/test_briefing_sources.py -q
15 passed; 4 pre-existing jsonschema RefResolver deprecation warnings

.venv/Scripts/python.exe -m pytest tests/unit/test_arrangement_sources.py tests/unit/test_briefing_sources.py tests/unit/test_arrangements.py -q
26 passed in the earlier regression run, before adding three final edge cases

python -m ruff check app/services/briefing_source_service.py app/services/arrangement_service.py app/api/routes/arrangements.py tests/unit/test_arrangement_sources.py tests/unit/test_briefing_sources.py
All checks passed

.venv/Scripts/python.exe -m mypy app/services/briefing_source_service.py app/services/arrangement_service.py app/api/routes/arrangements.py --follow-imports=silent
Success: no issues found in 3 source files
```

Tests exercise the actual arrangement GET route, unchanged Hebrew coverage and read-only
source files, correct MT-to-Greek association, missing/revoked/corrupt sources, no joined-hint
fallback, snapshot/policy identity, title/split/merged/absent map semantics, wrong-revision and
invalid-span refusal, tampered map/manifest hashes, and policy/release withdrawal during
evidence projection.

The real workspace still needs an approved and released immutable Greek source/catalog,
edition-specific reviewed mapping, current source capabilities and release/expert evidence.
This change creates no approvals or source availability. No raw or canonical content was
changed, no live import/rebuild was run, and no commit or push was performed.
