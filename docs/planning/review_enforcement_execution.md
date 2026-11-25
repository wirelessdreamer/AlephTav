# Review enforcement implementation

Date: 2026-11-05. Scope: R1 and R2 from the
[implementation plan](review_enforcement_and_translation_quality_plan.md), including
the CLI proposal-path repair. This adds application controls and isolated regressions;
it creates no real reviewer, canonical, source or release approvals.

## Shared rendering rules

`rendering_service.update_rendering` now has an explicit content-edit allowlist.
Generic updates reject status, signoff/counts, identity/membership IDs, provenance,
source anchors, derived metrics/flags and unknown fields. Canonical edits are refused;
the supported replacement remains a proposed alternate followed by review/promotion.
MCP delegates to the same service instead of maintaining its own different guards.

Explicit alternate acceptance, rejection, request-changes and canonical promotion
remain available. Review targets and canonical transition requests are checked before
recording a decision. An ineligible acceptance cannot persist a partial review.
Creation rejects invalid status names and still forbids accepted/canonical creation.

Rendering creation, editing, moves and promotion load a copy without the former
early no-op save. A refused operation therefore cannot normalize/rewrite a unit on
its way to raising an error. Successful mutations retain audit generation and derived
analysis. Revision-bound approvals and cross-process atomic commits remain later work.

Standalone demotion is disabled for all callers, including HTTP, CLI and assistant
actions. Moving a canonical rendering into another translation is refused. Bundle
transfer preflights canonical selections before any metadata or rollback writes.

## Raw writes and caller compatibility

Raw `PATCH /units/{unit_id}` and `PATCH /project` now reject through one shared
refusal service, returning HTTP 400 with an explicit explanation. The handlers remain
registered and retain their existing MCP exclusions. No mounted caller needed these
generic patches; supported dedicated metadata operations and GET routes remain.

The confirmed assistant `project.patch` action uses the same refusal. Its catalog
description says the action is unavailable; confirmation cannot authorize arbitrary
policy/source overwrites. A future authorized administrative workflow is separate work.

`add-alternate` now emits the same JSON result shape with `status="proposed"`.
Its help text explains that acceptance needs separate review. It no longer asks the
creation service to insert an already accepted alternate.

Rebuild discard uses the explicit alternate transition operation and preflights every
candidate before changing rebuild metadata. Missing or canonical candidates cause a
write-free refusal. Existing verified Codex source-anchor recovery uses an explicit
audited helper limited to proposals without an existing anchor; it cannot overwrite
canonical or existing anchor evidence.

## Regression coverage

New suites:

- `tests/unit/test_rendering_mutation_policy.py`: protected-field/status injection,
  canonical edits, reviewed replacement, positive proposal edits, failed promotion,
  explicit negative decisions and proposal-only anchor recovery.
- `tests/integration/test_rendering_review_boundary.py`: actual HTTP refusal and
  positive review/edit/acceptance paths, unknown targets and incomplete acceptance.
- `tests/integration/test_raw_mutation_policy.py`: raw unit/project and confirmed
  assistant overwrites, preserved existing review/audit history, empty-workspace
  refusal and working read endpoints.
- `tests/integration/test_cli_proposals.py`: audited/listable proposals and byte-exact
  refusal of standalone demotion or unreviewed promotion.
- `tests/unit/test_discard_rebuild_review_policy.py`: promoted/missing rebuild
  candidate refusals before writes, plus successful discard.
- `tests/unit/test_translation_transfer_review_policy.py`: canonical bundle refusal
  before writes and the working proposed bundle path.

The existing forbidden-license export regression now arranges invalid source metadata
inside its isolated fixture instead of depending on an unsafe production project PATCH.
No publication or license gate was removed.

## Executed checks

| Check | Result |
| --- | --- |
| `python -m pytest tests/unit tests/integration tests/golden -m "not corpus_audit" -q` | 795 passed, 1 corpus-audit test deselected, 4 existing jsonschema deprecation warnings |
| Final discard/transfer and affected verse-note unit/API suites | 35 passed after the final preflight changes |
| `python scripts/validate_content.py` on the existing workspace | 2,694 files validated, zero errors |
| `npm run build` | Passed TypeScript and Vite build; existing Vite CJS deprecation warning |
| Configured Ruff lint and format checks on 16 affected files excluding two modules with existing debt | Passed |
| HEAD comparison of lint/type diagnostics in affected modules | No new lint/type findings; configured lint findings decreased from 40 to 32 in the compared files |
| Scoped mypy on the affected modules | Four existing errors remain in rendering inference and missing jsonschema stubs; no new errors relative to HEAD; transfer module passes separately |
| `git diff --check` on application/tests | Passed |
| SHA-256 preservation check for `content/`, `data/raw/`, `schemas/` | All 2,883 files byte-identical to the pre-change baseline |

The broad suite started before the final discard/transfer preflights. The subsequent
35-case run exercises those final changes and their existing callers. Counts are
separate runs, not a claim of 830 distinct tests.

Ruff's full configured checks still report existing style/import findings in
`assistant_service.py` and long lines in `review_service.py`; both already failed
format checking at HEAD. Those unrelated lines were not reformatted or suppressed.
New and changed lines introduce no additional findings. No lint/type rule or content
validation was disabled to obtain the passing checks above.

## Preserved boundaries

Production content, raw sources and schemas are unchanged. Tests mutate authored or
copied isolated workspaces. Existing unrelated working-tree edits are preserved.
No commit or push was performed.

This slice does not authenticate reviewer identities, bind decisions to payload
revisions, repair cached historical approval semantics, add shared deployment auth,
or implement atomic multi-file transactions. Those remain R3–R7 work. Generic raw
project administration and arbitrary manual metric/flag replacement are intentionally
unavailable; future supported operations must preserve the same review boundary.
