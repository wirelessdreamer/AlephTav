# Greek foundation implementation execution

2026-10-17. This records implemented slices, not production source or expert approval.
The existing dirty working tree was preserved. No live import, rebuild, migration, raw
write, canonical English edit, commit or push was performed.

| Work | Implemented | Remaining gates |
|---|---|---|
| W0 | Pending source lock records proposed decisions, inspected hashes and explicit unavailable activation. No release bytes or approvals were invented. | Immutable Swete release, exact file sizes/license hashes, owner/license/Greek/schema review, intake and bounding-box decisions. |
| W1 | Current component capabilities; source-wide and exact package hash checks; distinct latest owner/license decisions; source policy CAS and mandatory package audit records; no raw manifest writes from project save/bootstrap; immutable audited installation distinct from activation. | Actual source decisions; remaining consumer closure reviewed with root/application agents. |
| W2 | Structured edition/revision identities, MT-compatible storage, legacy Greek locator write rejection, strict source-only Greek schemas and span validation, immutable source-only MT snapshot contract. Existing mandatory audit/alignment fields retained; only ID namespaces extended. | Schema-owner review; all downstream positional parsers inventoried by root. |
| W4 | Explicit offline operational cutover with OS/SQLite writer exclusion, backup, transactional copy/verification/idempotent marker; durable jobs/card routing; staged immutable MT SQLite catalog and pointer CAS; immutable study descriptor binds package closure, MT source snapshot and catalog with current policy on retained reads; explicit audited last-good recovery; summary caches bound to root/catalog revision. | Full multi-process crash/recovery/retention matrix, startup recovery wiring, full-Psalter performance and joined SQL Greek indexing remain pending. Greek reader initially consumes a sealed JSON study catalog. |

Implementation files: `app/core/ids.py`, `app/core/config.py`, `app/db/session.py`,
`app/services/registry_service.py`, `concordance_service.py`, `lexical_service.py`,
`foundation_contract_service.py`, `immutable_file_service.py`,
`source_capability_service.py`, `package_audit_service.py`,
`package_install_service.py`, `mt_source_snapshot_service.py`,
`study_snapshot_service.py`, `scripts/validate_content.py`, new foundation schemas,
and additive namespace changes to existing schemas. Durable local state is ignored.
The coordinated one-line generation-job connection import and fixture operational-state
cleanup were also applied so existing job and UI flows use durable state immediately.

Executed checks:

- `.venv/Scripts/python.exe -m pytest tests/unit/test_greek_foundations.py tests/unit/test_ids.py -q`: **47 passed**, temporary roots, authored Greek fixture, no full raw copies.
- Ruff check/format on owned new modules, IDs/config/session and new tests: passed.
- Targeted mypy on nine foundation source files with silent followed imports: passed.
- Existing MT regression modules `test_registry_summaries.py`, `test_validation.py`,
  `test_strict_schema.py`: **16 passed** in temporary fixture workspace.
- Existing generation and MT regression modules together: **36 passed**; combined
  foundation/identity/summary/validation/strict-schema rerun before the final new
  exact-package negative case: **62 passed**.

Existing long-line/style findings remain in the older concordance, lexical and registry
modules. Newly added foundation modules and IDs/config/session pass their focused gate;
this is not a claim that the entire preexisting dirty tree is lint-clean.

The tests exercise edition collisions and MT compatibility, Greek shape/span rejection,
latest-decision withdrawal, legacy Greek isolation, inactive idempotent installation,
checksum reuse rejection, study predecessor CAS, injected disk-full pointer failure,
retained-revision source revocation, MT source retention, explicit/idempotent migration
and failed catalog build preserving a live Windows reader plus durable UI state.
Migration preserves actual job output payloads and lexical-card state. Last-good
recovery succeeds after pointer corruption and refuses policy revocation fallback.
They do not establish Greek annotation accuracy, source rights, release readiness,
full concurrent-process recovery, accessibility or full corpus performance.

Operational migration deliberately refuses automatic cutover of any old mixed
database. Stop old API/job processes, then call the explicit maintenance service with
writers quiesced. The original mixed database and coherent backup are retained. No
catalog cleanup deletes retained catalog files or `data/local`.

The retained MT source-only snapshot is sufficient to freeze bridge endpoint bytes,
but existing MT units do not establish immutable package/license lineage. W9/W10
Hebrew snapshot display/export therefore remains blocked pending truthful provenance
closure; project-wide metadata is not fabricated into per-token source approvals.

## Critical runtime hardening follow-up

The independent runtime review found that matching a catalog's own hash did not prove
its text/entries/analyses came from the approved package bytes. The shared canonical
projection now validates only manifest-enumerated JSON/JSONL records, requires exact
record equality, edition/revision compatibility and unique identities, and checks
current package capabilities throughout the analysis provenance chain. Publication,
recovery and reader validation all use it before exposing content or replacing the
active pointer. Production descriptors require approved package status and actual
enumerated license bytes matching the declared license hash. The reader binds policy
before its first snapshot permission check and verifies it after projection.

Catalog-only reviewed selections, expression occurrences and invented lexical entry
links remain unavailable. Their specialist evidence/resolver contracts are outstanding;
they are not established merely by a trusted catalog label.

Local generation, composer suggestions, Codex translation/passage prompts and Codex
word-choice prompts now share an ephemeral current-policy projection. Denied MACULA
Greek hints and historical joined Greek witnesses are removed while Hebrew lexical
enrichment remains. The source records are never edited or renamed. Actual model
response/apply boundaries reject Greek-basis candidates until the W11 exact source
resolver exists; deterministic checks of historical Greek script/quality stay pure.
Cached Codex applies and generation reuse cannot supply a new Greek rendering.

Follow-up validation:

- `test_model_source_policy.py`, `test_greek_study_catalog.py` and
  `test_greek_foundations.py`: **34 passed** using authored temporary packages and
  explicit mocked fixture policy decisions. Includes forged text/dictionary/analysis,
  fake reviewed/selected state, unenumerated file, wrong-edition publication,
  policy-revocation race, missing license and pending-release probes.
- Existing generation/composer/Codex translation/passage tests: **63 passed** with
  fake/scripted adapters. Previous expectations that unapproved Greek generation
  succeeds were changed to explicit rejection with no content mutation.
- Ruff check and format pass the ten touched source/new-test files; targeted mypy
  passes the four new/shared foundation helpers. Broader consumer mypy retains
  existing inference and missing-jsonschema-stub findings; it is not claimed clean.

No actual model call, production registry decision, raw/content edit or source
activation occurred during these checks. Full-corpus reader performance remains
unmeasured; strict canonical closure checks are correctness evidence, not a p95 claim.

The first broad run exposed a fixture import-order defect: canonical projection
captured the capability function before the catalog fixture replaced its authority.
The helper now calls the current capability module directly. A regression eagerly
imports projection before fixture setup, then revokes capability afterward. The
foundations → public unit reads → catalog sequence passes **33 tests**.

Four stale consumer assertions were updated after the broad run confirmed they still
expected the disabled Greek generation path. The focused checks pass **4 tests**:
word-choice prompts preserve Hebrew/gloss/elsewhere English while omitting denied
Greek; composer retains the permitted Hebrew candidate and reports blocked Greek;
a Greek-only filter remains unavailable; generation cache reuse preserves the same
permitted output and persists no forbidden Greek rendering. Ruff/format pass for
these changes. No fixture reset or production permission was loosened.
