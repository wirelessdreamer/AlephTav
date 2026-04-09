Definition of done

The project is done only when all of these are true:

A fresh local install can ingest Psalms and build a working project without cloud services.
Every Hebrew token has a stable ID and a hoverable lexical card.
Every English layer is explicitly aligned back to Hebrew token anchors.
Every unit supports canonical and alternate renderings in parallel.
Contributors can open GitHub issues against exact Psalm, unit, token, span, or alternate IDs.
Contributors can submit PRs that either fix canonical text or add alternates.
CI blocks invalid schema, broken alignments, missing provenance, and forbidden source licenses.
The app can generate literal, phrase, concept, lyric, and constrained lyric layers.
The app can lock earlier layers and rerun later layers only.
The app can export a release bundle with text, sources, audit, notices, and unresolved concerns.
Final architecture to lock now

Use a hybrid file-plus-database design.

Source-of-truth content lives in Git-friendly JSON files.
Derived indexes and caches live in SQLite.
The backend is a local API plus CLI.
The frontend is a local workbench UI.
All generation jobs go through a single orchestrator.
All content mutations create audit records.

Recommended stack:

Backend: Python
API: FastAPI
CLI: Typer
Schemas: Pydantic
DB: SQLite
UI: React + TypeScript
Local state/data fetch: TanStack Query or equivalent
Model adapters: llama.cpp, Ollama, vLLM, and OpenAI-compatible local endpoints
Test stack: pytest for backend, Playwright for UI, schema tests for content
Repository layout

Use this layout exactly:

psalms-copyleft/
  .github/
    ISSUE_TEMPLATE/
      translation_error.yml
      alternate_translation.yml
      alignment_error.yml
      lexical_issue.yml
      provenance_issue.yml
      release_regression.yml
      config.yml
    workflows/
      validate.yml
      test.yml
      audit.yml
      release.yml
    CODEOWNERS
    pull_request_template.md
  app/
    api/
      main.py
      deps.py
      routes/
        projects.py
        psalms.py
        units.py
        tokens.py
        alignments.py
        renderings.py
        alternates.py
        review.py
        audit.py
        export.py
        search.py
        jobs.py
    core/
      config.py
      ids.py
      logging.py
      errors.py
      license_rules.py
    db/
      models.py
      session.py
      migrations/
    services/
      ingest_service.py
      registry_service.py
      lexical_service.py
      concordance_service.py
      alignment_service.py
      rendering_service.py
      generation_service.py
      review_service.py
      audit_service.py
      export_service.py
      report_service.py
      github_link_service.py
    llm/
      base.py
      adapters/
        llamacpp.py
        ollama.py
        vllm.py
        openai_compatible.py
      prompts/
        pass_01_gloss.md
        pass_02_literal.md
        pass_03_phrase.md
        pass_04_concept.md
        pass_05_lyric.md
        pass_06_metered_lyric.md
      contracts/
        generation_input.schema.json
        generation_output.schema.json
    ui/
      src/
        app/
        components/
        pages/
        hooks/
        state/
        types/
  content/
    psalms/
      ps001/
        ps001.meta.json
        ps001.v001.a.json
        ps001.v001.b.json
      ps019/
      ps023/
  data/
    raw/
      uxlc/
      oshb/
      macula/
      sefaria/
    normalized/
    derived/
      indexes/
      caches/
  schemas/
    project.schema.json
    unit.schema.json
    token.schema.json
    alignment.schema.json
    rendering.schema.json
    audit_record.schema.json
    release_report.schema.json
    source_manifest.schema.json
    style_profile.schema.json
  scripts/
    import_psalms.py
    build_indexes.py
    seed_project.py
    generate_reports.py
    validate_content.py
  reports/
    audit/
    release/
    provenance/
  tests/
    fixtures/
    unit/
    integration/
    e2e/
    golden/
  docs/
    README.md
    CONTRIBUTING.md
    TRANSLATION_POLICY.md
    AUDIT_POLICY.md
    REVIEW_POLICY.md
    STYLE_PROFILES.md
    DATA_SOURCES.md
    RELEASE_PROCESS.md
  LICENSE-code
  LICENSE-text-template
  NOTICE-template
  pyproject.toml
  package.json
Canonical ID rules

Freeze IDs before any code is written.

Use these formats:

project_id: proj.main
psalm_id: ps019
unit_id: ps019.v001.a
token_id: ps019.v001.t003
alignment_id: aln.ps019.v001.a.literal.0001
rendering_id: rnd.ps019.v001.a.literal.can.0001
alternate_id: rnd.ps019.v001.a.lyric.alt.0007
span_id: spn.ps019.v001.a.literal.0003
concept_id: cpt.ps019.v001.a.0002
audit_id: aud.ps019.v001.a.0009
issue_link_id: iss.000123
pr_link_id: pr.000456

Rules:

IDs are immutable.
IDs never depend on display text.
IDs never change when a rendering becomes canonical or alternate.
Canonical status is metadata, not identity.
File names must match unit IDs.
Core domain model

Create these primary entities.

5.1 Project
Stores settings:

title
output text license
code license
model backend
default model profile
allowed sources
style profiles
divine-name policy
review policy
release channel

5.2 SourceManifestEntry
Stores:

source_id
name
version
license
upstream_url
imported_at
import_hash
allowed_for_generation
allowed_for_display
allowed_for_export
notes

5.3 PsalmUnit
One record per editable unit.

Required fields:

psalm_id
unit_id
ref
segmentation_type
source_hebrew
source_transliteration
token_ids
concept_ids
status
current_layer_state
canonical_rendering_ids
alternate_rendering_ids
audit_ids
issue_links
pr_links

5.4 HebrewToken
Required fields:

token_id
ref
surface
normalized
transliteration
lemma
strong
morph_code
morph_readable
part_of_speech
syntax_role
semantic_role
referent
word_sense
occurrence_index
corpus_occurrence_refs
psalms_occurrence_refs

5.5 Alignment
Required fields:

alignment_id
unit_id
layer
source_token_ids
target_span_ids
alignment_type
confidence
created_by
created_via
notes

alignment_type enum:

direct
grouped
idiom
conceptual
editorial_expansion
omission_accounted_for
uncertain

5.6 Rendering
Required fields:

rendering_id
unit_id
layer
status
text
style_tags
target_spans
alignment_ids
drift_flags
metrics
rationale
provenance

layer enum:

gloss
literal
phrase
concept
lyric
metered_lyric
parallelism_lyric

status enum:

draft
proposed
under_review
canonical
accepted_as_alternate
rejected
deprecated

5.7 AuditRecord
Required fields:

audit_id
entity_type
entity_id
change_type
before_hash
after_hash
summary
rationale
triggered_by_issue
triggered_by_pr
created_by
created_at
checks
review_signoff

5.8 ReviewDecision
Required fields:

decision_id
target_id
reviewer_role
reviewer
decision
notes
timestamp
File storage strategy

Use a two-layer storage model.

Layer 1: Git source of truth

content/psalms/... contains human-reviewed content JSON.
This is what PRs modify.

Layer 2: local derived DB

SQLite stores fast indexes, search caches, lexical joins, job history, UI state, and generated reports.
The DB can be rebuilt from source JSON plus upstream data.

Rule:

Never store generated cache fields back into canonical content files unless they are intentionally part of the audit trail.
Build sequence from start to finish

Phase 0. Repo bootstrap and governance

Goal:
Create the skeleton repo, enforce contribution hygiene, and stop early schema drift.

Tasks:

Initialize repo with backend, UI, content, schemas, docs, and tests folders.
Add LICENSE-code, LICENSE-text-template, NOTICE-template.
Add CONTRIBUTING.md, TRANSLATION_POLICY.md, AUDIT_POLICY.md, REVIEW_POLICY.md.
Add GitHub issue forms under .github/ISSUE_TEMPLATE.
Add PR template.
Add CODEOWNERS.
Configure branch protection for main.
Add CI workflow skeletons for validate, test, audit, release.
Add pre-commit hooks for JSON formatting, schema validation, and linting.
Add a root README with local dev instructions.

Acceptance:

New issues use structured forms.
PRs auto-populate the required review checklist.
CODEOWNERS is active.
Branch protection requires review and passing checks.

GitHub supports structured issue forms in .github/ISSUE_TEMPLATE, repository PR templates, CODEOWNERS, and protected branches that can require approving reviews and passing checks.

Phase 1. Schema-first domain contracts

Goal:
Lock all canonical data structures before ingest or UI work.

Tasks:

Create JSON schemas for:
project
unit
token
alignment
rendering
audit record
release report
source manifest
style profile
Build a schema validator CLI command: validate-content.
Create fixture content for ps001.v001.a and ps023.v001.a.
Write tests that reject unknown keys, missing required keys, invalid enums, duplicate IDs.
Add content normalization rules:
stable key order
sorted arrays where order is not meaningful
consistent newline strategy
deterministic JSON serialization

Acceptance:

Every sample fixture validates.
CI fails on schema or ID errors.
Team agrees that these are the permanent wire formats for v1.

Phase 2. Source registry and license guardrails

Goal:
Make source usage explicit and auditable before ingestion.

Tasks:

Implement SourceManifestEntry.
Create data/raw/ import manifest files for UXLC, OSHB, MACULA, and optional Sefaria snapshots.
Build audit-licenses command:
lists every source
validates license allowlist
flags unknown sources
Encode source policy:
allowed for canonical source
allowed for lexical display
allowed for witness comparison
forbidden for generation
forbidden for export
Add license warning banners in the UI for any restricted witness text.

Acceptance:

No ingestion can occur until each source has manifest metadata.
The project fails fast on unknown licenses.
Export pipeline refuses to package forbidden source text.

Phase 3. Hebrew ingest and normalization

Goal:
Seed the full Psalms corpus locally.

Tasks:

Write import_psalms.py.
Ingest canonical Hebrew Psalms from UXLC/WLC-derived source.
Normalize references:
book
chapter
verse
colon
Create initial unit segmentation:
verse
colon
Store raw Hebrew text and normalized text.
Generate transliteration field.
Create unit files under content/psalms/psNNN/.

Implementation rule:

Start with verse and colon segmentation only.
Add strophe and concept segmentation later as derived layers, not base source fragmentation.

Acceptance:

Every Psalm has seeded unit JSON files.
All units have stable IDs.
Re-running import produces identical IDs and content hashes.

Phase 4. OSHB and MACULA enrichment

Goal:
Attach lexical and linguistic data to every token.

Tasks:

Tokenize each unit into Hebrew tokens.
Attach OSHB lemma, Strong's, morphology, readable morphology.
Attach MACULA syntax role, semantic role, referent, word sense where available.
Build token-level index tables in SQLite.
Add token occurrence cross references:
same Psalm
whole Psalms corpus
wider corpus if indexed
Build concordance indexes by:
lemma
Strong's
exact form
morphology
stem/binyan
syntax role

Acceptance:

Hover card payload can be built for every token.
Concordance search returns results locally.
Missing enrichments are recorded, not silently dropped.

The source choice is grounded in the upstream datasets: Tanach.us permits copying the Hebrew text, OSHB exposes morphology and readable morphology interpretation, and MACULA documents its WLC, OSHB, syntax, semantic-role, referent, and word-sense layers.

Phase 5. Lexical inspection backend

Goal:
Make the Strong's-like review experience real.

Tasks:

Implement lexical_service.py.
Add API endpoints:
GET /tokens/{token_id}
GET /tokens/{token_id}/occurrences
GET /lexicon/lemma/{lemma}
GET /lexicon/strong/{strong}
GET /search/concordance
Build lexical card payload:
surface
normalized
transliteration
lemma
Strong's
morphology
syntax role
semantic role
referent
gloss list
nearby usage examples
Add "pin lexical card" state endpoint.
Add "copy lexical reference" support.

Acceptance:

Hovering or clicking a token can populate a complete lexical card.
Concordance search works without internet.
Lexical cards show same-Psalms and wider-corpus occurrences.

Phase 6. UI workbench shell

Goal:
Build the actual editor workspace.

Tasks:

Create the main workbench page with:
left pane: Hebrew
right pane: active English layer
right rail: inspector
bottom drawer: concordance / audit / compare
Implement token hover state.
Implement token click and pin state.
Implement synchronized scroll between Hebrew and English panes.
Add layer switcher.
Add granularity switcher.
Add source/license panel.
Add unresolved warning badges.

Acceptance:

Editor can browse Psalms and units.
Hovering a Hebrew token opens lexical info.
Pinned inspector remains visible while editing English.

Phase 7. Alignment engine and bidirectional highlighting

Goal:
Make Hebrew-to-English traceability first-class.

Tasks:

Implement alignment_service.py.
Create alignment schema validators.
Add alignment APIs:
GET /units/{unit_id}/alignments
POST /alignments
PATCH /alignments/{alignment_id}
DELETE /alignments/{alignment_id}
Implement alignment editor UI:
select Hebrew token(s)
select English span(s)
assign alignment type
set confidence
add notes
Add bidirectional highlighting:
Hebrew hover highlights English spans
English hover highlights Hebrew tokens
Add coverage analysis:
uncovered Hebrew tokens
unaligned English spans
low-confidence alignments

Acceptance:

Manual alignments persist.
Hover highlighting works both directions.
Coverage warnings appear in UI and reports.

Phase 8. Rendering layer framework

Goal:
Support all required translation layers.

Tasks:

Create rendering schema and service.
Implement these layers:
gloss
literal
phrase
concept
lyric
metered_lyric
parallelism_lyric
Store one canonical rendering per layer and zero or more alternates.
Add style tags and metrics per rendering.
Add compare mode:
canonical vs alternate
alternate vs alternate
layer vs layer

Acceptance:

Each unit can hold multiple renderings.
Canonical and alternate status are independent of ID.
Compare view renders any two selections side by side.

Phase 9. Alternate translation subsystem

Goal:
Keep multiple valid renderings in parallel without losing auditability.

Tasks:

Implement alternates.py route and service.
Add actions:
add alternate
accept alternate
reject alternate
deprecate alternate
promote alternate to canonical
demote canonical to alternate
Support alternate metadata:
style goal
rationale
metric profile
issue/PR links
Add UI filters:
most literal
best lyric flow
best meter fit
best imagery preservation
formal
contemporary
Add "release-approved only" toggle.

Acceptance:

An editor can preserve multiple parallel choices for the same unit.
Promotion to canonical does not delete the prior canonical rendering.
Alternates can be included or excluded from export.

Sefaria's own documentation explicitly describes support for multiple translations and comparison, which matches the alternate-translation design you want, even though your project will maintain its own data model and governance.

Phase 10. LLM orchestration and pass pipeline

Goal:
Add controlled generation without losing alignment or auditability.

Tasks:

Implement model adapter interface with methods:
health_check()
generate_json()
estimate_context()
Implement adapters for:
llama.cpp
Ollama
vLLM
OpenAI-compatible local endpoints
Create strict JSON-only prompt contracts for each pass.
Add generation job records with:
input hash
model profile
prompt version
seed
runtime metadata
Implement passes:
Pass 1: gloss
Pass 2: literal
Pass 3: phrase
Pass 4: concept
Pass 5: lyric
Pass 6: constrained lyric
Add locking logic:
lock lexical
lock gloss
lock literal
rerun downstream only
Add alternate-generation mode:
generate N candidates
label by style goal
Add low-confidence and drift flag extraction.

Generation contract for each unit should look like this:

{
  "unit_id": "ps019.v001.a",
  "layer": "lyric",
  "locked_inputs": {
    "hebrew_tokens": [],
    "gloss_rendering_id": "rnd....",
    "literal_rendering_id": "rnd....",
    "concept_rendering_id": "rnd...."
  },
  "style_profile": {
    "literalness": 0.55,
    "lyric_freedom": 0.70,
    "target_syllables": 8,
    "rhyme_mode": "off",
    "register": "literary",
    "parallelism_priority": "high"
  }
}

Output contract:

{
  "unit_id": "ps019.v001.a",
  "layer": "lyric",
  "candidates": [
    {
      "text": "",
      "rationale": "",
      "alignment_hints": [],
      "drift_flags": [],
      "metrics": {}
    }
  ]
}

Acceptance:

Jobs can run against a local model only.
Every job is reproducible by input hash, prompt version, model profile, and seed.
Rerunning a downstream layer does not modify locked upstream layers.

Phase 11. Semantic drift and poetic analysis

Goal:
Flag where lyric shaping may have gone too far.

Tasks:

Implement drift detectors for:
negation changes
number changes
speaker/addressee changes
tense/aspect shifts
omitted image
added doctrine
metaphor flattening
parallelism break
semantic overcompression
Implement lyric metrics:
syllable count
stress approximation
line length
repetition score
singability score
parallelism preservation score
Add per-rendering warnings and confidence scores.
Include drift checks in CI for changed canonical text.

Acceptance:

Canonical changes with unresolved high-severity drift flags cannot be release-approved.
Alternates can remain proposed even with warnings.

Phase 12. Review workflow and signoff

Goal:
Make human review the gatekeeper for publication.

Tasks:

Add statuses:
draft
proposed
under_review
canonical
accepted_as_alternate
rejected
deprecated
Add reviewer roles:
lexical reviewer
Hebrew reviewer
alignment reviewer
lyric reviewer
theology reviewer
release reviewer
Add comments and signoff records.
Encode merge policy:
alternate addition needs 1 qualified reviewer
canonical change needs 2 qualified reviewers
release needs release reviewer
Add UI review actions:
approve
request changes
accept as alternate
promote to canonical
reject

Acceptance:

No rendering can become canonical without recorded signoff.
The review trail is visible in UI and export.

Phase 13. GitHub issue and PR integration

Goal:
Make repository collaboration native.

Tasks:

Finalize issue forms:
translation error
alternate translation proposal
alignment error
lexical issue
provenance issue
release regression
Finalize PR template fields:
units changed
layer changed
canonical or alternate
rationale
issue links
evidence
reviewer checklist
Add optional issue/PR link fields in content and audit records.
Build scripts:
link-issue
link-pr
Add docs for contributor workflow:
open issue
branch
edit JSON
run validation
open PR
request review

Acceptance:

A contributor can file a translation error against an exact unit.
A contributor can propose an alternate without overwriting canonical text.
Changed units can be traced to issue and PR identifiers.

Phase 14. Audit subsystem

Goal:
Make every content change explainable.

Tasks:

Implement audit_service.py.
Create audit records on every content mutation.
Add audit queries:
by unit
by Psalm
by layer
by contributor
by release
Generate machine-readable audit reports:
unresolved drift
missing provenance
uncovered tokens
unaligned spans
canonical changes since last release
accepted alternates since last release
Generate human-readable audit reports:
Markdown
HTML

Acceptance:

Any canonical text line can show who changed it, why, and under what evidence.
Release reports summarize exactly what changed.

Phase 15. Export pipeline

Goal:
Produce publishable outputs and repo artifacts.

Tasks:

Build exports:
Markdown
plain text
JSON
HTML
Build supporting files:
LICENSE
NOTICE
SOURCES
AUDIT_REPORT
OPEN_CONCERNS
Add export filters:
canonical only
canonical plus alternates appendix
one style profile only
Add release manifest:
release version
source manifests
render counts
unresolved warnings
signoff summary

Acceptance:

A release folder can be generated locally in one command.
Export includes enough provenance to audit every line.

Phase 16. Sefaria optional context layer

Goal:
Add optional witnesses and linked context without contaminating canonical source discipline.

Tasks:

Implement Sefaria source adapter.
Support exact version retrieval using tref plus explicit version metadata.
Store versionTitle, language, ref, and source URL for every imported witness.
Keep Sefaria data in a separate witness namespace.
Do not use Sefaria "merged" content as canonical source.
If building a local mirror, use a downloaded dump rather than scraping the live API.

Acceptance:

Witness texts are clearly marked and license-tagged.
Exact versions are stored, not fuzzy labels.
Witness text can be displayed, compared, and cited, but not silently blended into canonical output.

Sefaria's v3 Texts API is the current endpoint for versioned retrieval, versions of the same work share the same Ref while differing by versionTitle, and Sefaria recommends using a complete dump from GitHub if you want your own database rather than pulling everything from the live API.

Phase 17. Search and concordance

Goal:
Make the workbench feel like a serious study tool.

Tasks:

Implement search over:
Hebrew surface
normalized Hebrew
lemma
Strong's
morphology
English renderings
audit notes
issue-linked units
Add "show me every occurrence in Psalms" views.
Add "show me all alternates tagged meter-fit" view.
Add "units with unresolved drift" view.
Add "units changed since release X" view.

Acceptance:

Search results can navigate directly into the editor.
Concordance view can pivot from token to all occurrences.

Phase 18. Test suite and CI hardening

Goal:
Make the repo safe for outside contributors.

Tasks:

Unit tests:
ID generator
schema validators
alignment coverage
license rules
drift detectors
Integration tests:
ingest pipeline
lexical payload generation
generation job flow
export flow
Golden tests:
Psalm 1
Psalm 19
Psalm 23
Psalm 51
UI e2e:
hover token
pin inspector
create alignment
add alternate
promote alternate
export release
CI gates:
lint
test
schema validate
content validate
audit report generation

Acceptance:

CI catches schema, audit, and alignment breakage before merge.
Golden fixtures stay stable across refactors.

Phase 19. Release workflow

Goal:
Cut auditable public releases.

Tasks:

Create version tags for content schema and release bundle.
Build generate-release-report.
Generate release artifacts in reports/release/.
Freeze main for release candidate.
Validate:
all canonical files valid
no high-severity unresolved canonical drift
sources manifest complete
licenses clean
reviewer signoff complete
Publish release notes summarizing:
canonical changes
accepted alternates
unresolved concerns
contributor credits

Acceptance:

Every public release has a reproducible report bundle.
A future contributor can diff release N to release N+1.
API surface to implement

Implement these endpoints first.

Project

GET /project
PATCH /project

Content

GET /psalms
GET /psalms/{psalm_id}
GET /units/{unit_id}
PATCH /units/{unit_id}

Lexical

GET /tokens/{token_id}
GET /tokens/{token_id}/occurrences
GET /search/concordance

Alignment

GET /units/{unit_id}/alignments
POST /alignments
PATCH /alignments/{alignment_id}
DELETE /alignments/{alignment_id}

Renderings

GET /units/{unit_id}/renderings
POST /units/{unit_id}/renderings
PATCH /renderings/{rendering_id}
POST /renderings/{rendering_id}/promote
POST /renderings/{rendering_id}/demote

Generation

POST /jobs/generate
GET /jobs/{job_id}
POST /jobs/{job_id}/retry

Review

POST /review/{target_id}/approve
POST /review/{target_id}/request-changes
POST /review/{target_id}/accept-alternate
POST /review/{target_id}/reject

Audit

GET /audit/unit/{unit_id}
GET /audit/release/{release_id}
GET /reports/open-concerns

Export

POST /export/book
POST /export/release
CLI surface to implement

These commands should exist before UI completion:

init-project
import-psalms
attach-annotations
build-indexes
validate-content
audit-licenses
translate-unit
translate-psalm
rerun-layer
list-alternates
add-alternate
promote-alternate
demote-canonical
link-issue
link-pr
generate-audit-report
generate-release-report
export-book
export-release
GitHub artifacts to create immediately

Create these files on day 1:

.github/ISSUE_TEMPLATE/translation_error.yml
Fields:

Psalm
unit_id
token_id optional
layer
current text
proposed correction
severity
rationale
evidence
canonical change or alternate proposal

.github/ISSUE_TEMPLATE/alternate_translation.yml
Fields:

Psalm
unit_id
target layer
proposed text
style goal
expected metric gain
rationale
evidence

.github/pull_request_template.md
Sections:

Summary
Units changed
Layer(s) changed
Canonical or alternate
Linked issues
Evidence
Validation checklist
Reviewer checklist

CODEOWNERS
Suggested ownership:

content/psalms/** -> Hebrew and lyric reviewers
schemas/** -> schema owners
.github/workflows/** -> repo admins
app/llm/** -> model pipeline owners
Reports to generate

Machine-readable:

reports/audit/uncovered_tokens.json
reports/audit/unaligned_spans.json
reports/audit/open_drift_flags.json
reports/audit/provenance_gaps.json
reports/release/release_manifest.json

Human-readable:

reports/audit/open_concerns.md
reports/audit/unit_change_log.md
reports/release/RELEASE_NOTES.md
reports/release/AUDIT_REPORT.md
reports/release/SOURCES.md
Implementation order for an agent

Tell the agent to work in this order and not skip ahead:

Repo skeleton
Schemas
ID rules
Source registry
Hebrew ingest
OSHB and MACULA enrichment
SQLite indexes
Lexical API
Basic workbench UI
Alignment engine
Rendering model
Alternate subsystem
LLM adapters
Pass pipeline
Drift analysis
Review flow
Audit subsystem
Export pipeline
GitHub integration
Release workflow
Hardening and docs
First milestone sequence

Milestone A

Psalm 1 only
ingest
lexical cards
manual alignments
gloss and literal layers

Milestone B

Psalms 1, 19, 23
alternates
compare view
audit trail
basic exports

Milestone C

full Psalms ingest
phrase, concept, lyric layers
issue and PR linking
release reports

Milestone D

constrained lyric layer
drift analysis
full CI policy
public release candidate
Hard rules the agent must follow
Do not invent or auto-import unknown sources.
Do not store canonical content in the DB only.
Do not merge alternate and canonical concepts.
Do not change IDs after initial import.
Do not let the LLM write directly to canonical content without a review state.
Do not allow hidden witness text mixing.
Do not bypass audit record creation.
Do not allow export if source licenses are unresolved.
Do not allow canonical release with failing schema or broken alignment coverage.
The shortest agent handoff