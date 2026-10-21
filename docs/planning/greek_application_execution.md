# Greek application execution (W7–W11)

Date: 2026-10-17. Software implementation slice; no source, specialist, schema-owner,
release, or generation approval is implied. No real source package was imported or
activated. Existing dirty Hebrew content and translation ownership were preserved.

| Package | Implemented slice | Remaining gates |
| --- | --- | --- |
| W7 | Immutable catalog view adapter; exact typed lexical/surface/identifier queries; candidate deduplication; 1–200 bounded pages; query/snapshot/policy-bound cursors; dictionary entry and exact identifier routes; typed stale/unavailable results | Catalog validation/review and full approved-source coverage/performance; central MCP/CLI wiring owned by root; Extra High critical-boundary review requested |
| W8 | `ComparisonPage` mounts MT/LXX/parallel source picker/reader/card; MT remains default; independent source psalm navigation including 151; native token buttons; dictionary constrained-tree rendering, attribution/citation baseline; first occurrence page bound to card; stale async discard and project/edition reset; MT9+10 membership preservation tested | Actual approved catalog, edition-aware parallel maps and source attribution completeness; full outside-project mapping journey; 200% zoom/full-shell accessibility; no full-source acceptance claim |
| W9 | Pure immutable MT/Greek endpoint validation and accepted-group multiset distribution, including repeated lexemes, many-to-many and minus observations | No acceptance/publication route; no specialist eligibility implementation here; actual MT snapshot capture, reviewed gold set, distinct Greek/alignment reviewers, approved applicable decisions and supersession required |
| W10 | Fail-closed, read-only export preparation and default-off source picker availability; package closure/hash/provenance/license/export checks; explicit refusal of MT/bridge export pending Hebrew package lineage | Availability record design/critical review, source/expert/owner/release approvals, reconstruction/failure rollback and full provenance evidence; no bundle published and no rollout enabled |
| W11 | Deliberately no generation activation or speculative edits to existing model services | W9/W10 and explicit generation capability; every generation/composer/Codex/briefing path must resolve immutable source/token membership/span text and enforce applicable specialist review |

## Contracts and integration

`app.services.greek_study_service.load_view(snapshot_id, policy_id)` resolves the
foundation `study_snapshot_service.active_snapshot` and rechecks current policy.
The immutable JSON catalog contains `units`, flat `analyses` or per-token
`annotations`, `entries`, and optional `expressions`. Greek identity is parsed with
`parse_unit_id`; project membership never changes source navigation. Analyses and
entries must belong to package/source closure and retain candidate status.

Root must register `app.api.routes.greek_study.router` in `app/api/main.py` and add
MCP wrappers or reasoned coverage exclusions. Read routes:

- `/lxx/editions`, `/lxx/psalms`, `/lxx/reader`, `/lxx/units/{unit_id}`
- `/greek/tokens/{token_id}/card`
- `/greek/lexicon/entries/{entry_id}`, `/greek/lexicon/identifiers`
- `/greek/concordance`

Card, entry, unit, psalm and concordance calls carry both `study_snapshot_id` and
`policy_revision_id`; this includes the first dependent occurrence page. Stale
responses use HTTP 409 with `study_stale` and restart action. Current denied sources
return HTTP 403 with `source_unavailable` and no text/count payload. The edition
picker returns no editions until explicit release availability gates are present.

## Executed checks

- `.venv/Scripts/python.exe -m pytest tests/unit/test_greek_study_service.py tests/unit/test_greek_study_catalog.py tests/unit/test_greek_bridge_service.py tests/unit/test_greek_study_export.py tests/integration/test_greek_study_routes.py -q`: **15 passed** (four `RefResolver` deprecation warnings).
- `npm run build`: TypeScript and Vite **passed**.
- Focused `ruff check` for all new Python services/routes/tests: **passed**.
- Targeted `mypy` for the four new Python service/route modules with `--follow-imports=silent`: **passed**.
- `$env:ALEPHTAV_PLAYWRIGHT_CHANNEL='msedge'; npx playwright test --config playwright.greek.config.ts --reporter=line`: **3 passed**, using authored mocked HTTP fixtures on the real mounted route, 430px layout, Enter/Space/Escape focus, dictionary safe text, attribution/baseline, pagination, Ps151 navigation, project reset, stale first page and both MT9+MT10 members surviving Greek navigation.

Default Playwright's expected headless-shell revision is absent on this machine;
the installed Edge channel was used. Browser fixtures start with the supported
assistant-closed preference: the existing open footer assistant's failed-settings
panel can intercept clicks at 430px. These tests do not establish full-shell or
full-Psalter accessibility/performance or expert annotation accuracy.

## Changed files owned by this package

- New `app/services/greek_study_service.py`, `greek_bridge_service.py`, `greek_study_export_service.py`
- New `app/api/routes/greek_study.py`
- New `app/ui/src/hooks/useGreekStudy.ts`, `components/GreekStudyPanel.tsx`, `components/GreekStudyPanel.css`
- Surgical mounted `app/ui/src/pages/ComparisonPage.tsx` and `app/ui/vite.config.ts`
- New `tests/unit/test_greek_study_service.py`, `tests/unit/test_greek_study_catalog.py`, `tests/unit/test_greek_bridge_service.py`, `tests/unit/test_greek_study_export.py`, `tests/integration/test_greek_study_routes.py`
- New `tests/e2e/greek-study.spec.ts` and `playwright.greek.config.ts`

No commit/push, real content mutation, raw write, destructive rebuild, full importer,
canonical English change or new generation path was performed.

## Critical boundaries still requiring integration review

The current availability-record check is a fail-closed scaffold based on a local
snapshot-bound record; a missing record disables the picker. Its signoff/report
presence checks are **not** a completed auditable release-decision workflow. No
record was created. Review applicability must be implemented before production
availability can be asserted. The export service is deliberately unexposed.

Catalog analysis `reviewed` status and `selected_analysis_id` must acquire a
payload/revision-bound latest-review eligibility resolver before any reviewed
analysis set is activated; current adapters produce proposed analyses only.
The pure query engine's reviewed/selected predicates do not supply those approvals.

MT source snapshots currently retain source/token bytes for anchor stability,
without immutable Hebrew source-package license/provenance closure. Foundation
confirmed that projecting current project-wide metadata would invent stronger
provenance. New bridge text/count routes remain unexposed, and export refuses a
descriptor containing an MT snapshot until a truthful lineage contract exists.

## W11 guarded integration proposal

The future integration boundary should be one service resolver taking a complete
study snapshot, immutable MT snapshot, accepted bridge set and analysis-set revision,
Greek unit/token IDs and exact source spans. It should return generation input only
after current package-level `generation` permission, applicable expert decisions,
unit membership, ordered token membership and source-text/span equality all pass.
Unversioned legacy locators and joined MACULA hints must fail this resolver.

`generation_service`, `composer_suggestion_service`, `codex_translation_service`,
`codex_briefing_service`, source-anchor validation and every rebuild path must call
that same boundary before prompt construction and again before accepting anchors.
The caller must persist the exact source/bridge/analysis identity and retain old
packages; a source switch must never retag an existing rendering. Schema-owner
approval, source generation approval, specialist rendering reviews and W9/W10
completion remain prerequisites. No speculative prompt/model changes were made.

## Arrangement Sources screenshot correction

The mounted Sources ribbon pane now renders Hebrew (MT) and the explicit mapped
Greek (LXX) source inside **every** verse block. Collapsing a verse hides lexical
and literal aids while retaining both source texts. Greek source references retain
the exact edition/revision, nonmatching numbering, merged units and partial/full-
verse labels. Absent, unmapped and unavailable Greek evidence remains visible as a
state; no same-number correspondence is inferred. Verse and song-line hover cards
also include both languages. Ribbon colours continue to describe Hebrew coverage.

`ArrangementView.greek_sources` reuses `BriefingGreekSources` from the existing
evidence provider. Greek token buttons preserve actual source punctuation and use
snapshot/policy-bound word cards, with native keyboard/touch activation, Escape and
focus return. Each source block and sung row is observed for resize, so new Greek
content, collapse and font/viewport changes remeasure the ribbons. A dedicated narrow
layout reduces the gutter without hiding either source.

Additional changed files: `ArrangementSources.tsx`, `ArrangementWorkspace.tsx`, new
`ArrangementGreekSource.tsx` and `ArrangementSources.css`, one optional field in
`types/index.ts`, new `tests/e2e/arrangement-sources.spec.ts`, and the Greek Playwright
config's test match list. Existing dirty shared content was preserved.

Verification: `npm run build` passed; the full authored mounted Greek/arrangement
suite passed **5 tests** on installed Edge, including both new arrangement cases.
Cases cover each verse's two source labels, RTL/LTR, merged/different numbering,
partial/absent/unmapped/blocked evidence, collapsed source visibility, verse/song
hover cards, Greek keyboard word study/focus return, actual punctuation, 430px
layout and ribbon path changes after collapse and Greek font-height changes.
Desktop and narrow screenshots were saved under
`test-results/arrangement-sources-arrang-d7d41--Greek-inline-and-collapsed/` and
visually inspected. These are authored software fixtures, not source/expert approval.

The runtime review's P2 long-card access finding was repaired: source previews now
accept pointer scrolling and remain open while the pointer crosses into the card;
native per-verse “Read sources” controls and song-line click/Enter/Space open a
persistent, focusable nonmodal dialog. Close/Escape restore trigger focus, and
long content supports mouse-wheel, keyboard and native touch scrolling. Placement
uses actual viewport space and clamps both dimensions even when a tall source
block spans above and below the viewport. The close control remains sticky.

Verification after that repair: `npm run build` passed; **3/3 relevant arrangement
browser tests passed**, including a 40-word Hebrew/121-token Greek fixture, four-
verse song source card, 430×640 and 430×320 viewports, pointer wheel, keyboard End,
an actual touch swipe and late-content visibility/focus-return assertions. The
clamped long-card screenshot is retained in
`test-results/arrangement-sources-long-s-ac6cb--pointer-keyboard-and-touch/long-source-details-clamped.png`.

Final shared-control regression check after the P2 repair and accessibility
attributes: the complete `playwright.greek.config.ts` authored suite passed **6/6**
(3 arrangement source cases and 3 Greek study cases), and `npm run build` passed.
Only these relevant browser/build checks were rerun; no backend files changed.
