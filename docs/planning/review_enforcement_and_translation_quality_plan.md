# AlephTav review enforcement and translation quality implementation plan

Date: 2026-11-05. Status: proposed backlog, with no implementation or editorial
approvals implied. Target: the existing trusted local Psalms workbench.

R1 and R2 implementation and verification are recorded in
[Review enforcement implementation](review_enforcement_execution.md). The remaining
backlog and human approval requirements below still apply.

R3 implementation, compatibility boundaries and verification are recorded in
[Review-evidence implementation](review_evidence_execution.md). Versioned evidence
remains non-authoritative pending R4/R5 authentication and eligibility activation.

The requested companion workflow for intentional translation choices and unknown
supporting context is recorded in
[Intentional-choice audit implementation](intentional_translation_choices_execution.md).
These statements preserve editorial intent separately from approval evidence.

Build one dependable path from a proposed translation to a reviewed, recoverable,
permitted release before expanding the corpus or research feature set. Start by
closing every way to change publication authority without review. In parallel,
prepare a small human quality pilot using the existing rubric and benchmark tools.
The first product milestone is **three complete reviewed Psalms, one reviewed song
arrangement, and a reproducible permitted release**.

The [comparative report](../../output/research/logos_and_aleph_tav_research_report.html)
and its [read-only corpus inventory](../../output/research/aleph_tav_evidence_inventory_2026-11-05.json)
provide the baseline. At the inspected working tree, HEAD
`add49270186b16d5d077b54c355f1c17594fe8b2`, 200 of 2,527 units contain
426 proposed renderings, with no persisted unit review decisions or formal
alignments. These are inventory counts, not accuracy scores. Recheck the baseline
when implementation begins; preserve the existing unrelated working-tree changes.

## Delivery order

| Order | Priority and milestone | Work | Exit gate |
| --- | --- | --- | --- |
| 1 | P0 Close mutation bypasses | R1, R2 and the immediate containment parts of R8 | HTTP, service, CLI and MCP cannot directly rewrite canonical content, inject approval state, or lower review requirements through ordinary edits |
| 2 | P0 Make review evidence authoritative | R3 through R8 | Current decisions from distinct qualified reviewers are verified against the GitHub publication and exact reviewed revision; stale, agent and forged evidence cannot count |
| Parallel preparation | P1 Prepare real quality validation | Q1 and the design of Q2; recruit reviewers immediately | Frozen scope, scoring rules, source identities and reviewer assignments; no generated template counts as completed review |
| 3 | P1 Collect and assess real evidence | Q2 through Q5 | Immutable candidates, independent human ratings, valid candidate-scoped source accounting and a completed small heldout evaluation |
| 4 | P1 Complete the editorial pilot | D1 through D3 | Three whole Psalms and one arrangement meet policy, restore correctly and produce the exact approved permitted output |
| 5 | P2 Expand after evidence | E1 through E4 | Expansion follows measured review capacity and actual user needs |

R1/R2 can start while R3 is being designed. Q1, source inventory, backup preparation
and reviewer scheduling can run alongside them. Human research scores may be
collected against frozen study candidates once Q2/Q3 are ready, but must not become
publication approvals automatically. Canonical promotion and release wait for the
P0 gate, valid content-specific human decisions and current source permissions.

For one developer familiar with the code, reserve roughly **30–50 engineering
days** for the core path, including regression coverage, integration and pilot
support. This is an initial planning allowance, not a delivery commitment. Reestimate
after R1's reproductions and R3's contract review. Specialist recruitment, translation,
human review, adjudication and required owner approvals add elapsed time. A second
engineer can take quality infrastructure after the shared contracts settle; splitting
authority code before that point is likely to create inconsistent rules.

## Ownership and decisions needed early

Use role owners until people are assigned: engineering owner, project owner,
Hebrew or lexical review lead, lyric or musical reviewer, and release reviewer.
One person may hold several qualified roles but cannot count as two independent
people. Assign actual people before a real review session.

The project owner and review lead need to ratify these concrete choices while
unaffected implementation proceeds:

1. GitHub account-to-role mapping, qualifications, independence and author self-review rules.
   Default: two distinct qualified humans for canonical acceptance; the author
   does not supply an independent quality rating of their own work. Decide whether
   release signoff must come from an additional person; do not infer that rule.
2. The versioned review-evidence contract and legacy migration in R3. The current
   unit schema forbids extra review-decision fields, so new authority fields cannot
   simply be inserted without the required schema review.
3. The pilot audience, literal and lyric briefs, scoring instructions, serious-error
   definitions and treatment of disagreements. Start from the existing rubric.
4. Three contrasting pilot Psalms. Suggested starting points are Psalms 13 and 23,
   plus a third selected for a materially different genre or interpretive challenge.
   These are editorial choices, not an already approved sample.
5. A specified tune, meter or performance brief for the arrangement. Without one,
   assess lyric fitness and leave musical singability unassessed.

This plan does not authorize changes to production canonical renderings, raw
sources, schemas, protected license/notice files, CODEOWNERS or repository settings.
Implementation must follow the approvals already required by `CLAUDE.md`.
No real reviewer, source, canonical or release approval may be created as a fixture
or inferred from completion of a software ticket.

## P0 Enforce the existing review policy

### R1 Enforce rendering edits and transitions in the shared service

**Owner:** engineering. **Start:** first. **Dependency:** none.

Characterize and then close the current mismatch between the guarded MCP edit
wrapper and `rendering_service.update_rendering`. Generic editing must accept a
defined set of editable fields. Status, review signoff, cached approval counts,
identity/membership IDs and publication authority are server-owned. Derived metrics
and concern resolution need explicit trusted operations rather than arbitrary
replacement from a request body.

Reject direct edits of canonical text. The supported change path is a new proposed
alternate followed by fresh review and promotion, preserving the previous canonical
as appropriate. Put accept, reject, promote and other transitions behind shared
service rules; interfaces should translate requests, not maintain different policies.

**Acceptance:** service, HTTP, MCP and CLI refuse direct canonical changes, status
injection, forged signoff/counts and ID replacement. Refusal leaves persisted bytes
and content audit history unchanged. Valid proposed-text edits continue to work.
Approved replacement preserves stable rendering IDs and leaves at most one canonical
per unit/layer. Explicit human resolution of an incorrect drift concern remains
possible and audited.

**Touchpoints:** `app/services/rendering_service.py`,
`app/api/routes/renderings.py`, `app/api/mcp_server.py`, `app/cli.py`,
`tests/integration/test_review_and_export.py`, `tests/integration/test_mcp_server.py`.
Add adversarial route/service tests before the fix, using isolated fixture content.

### R2 Close raw unit and project writes and control demotion

**Owner:** engineering. **Dependency:** R1 transition rules.

Replace the generic `unit.update(payload)` and `project.update(payload)` HTTP paths
with narrow service operations or reject them until a supported replacement exists.
Ordinary metadata edits must not alter source tokens, renderings, decisions, audits,
canonical membership, source permissions or review policy. Remove or restrict the
standalone unreviewed canonical demotion paths in HTTP and CLI.

Keep review-policy administration separate from ordinary project editing. Until an
authorized, audited administrative contract exists, reject sensitive policy changes;
do not create another raw admin overwrite endpoint. Changing the permitted review
threshold must not be a shortcut around the existing two-approval rule.

**Acceptance:** every identified unit/project overwrite attempt is rejected before
any write; the legitimate metadata actions still needed by the mounted UI have a
narrow audited path. Demotion or replacement cannot evade canonical-change policy.
Tests set up fixtures through test helpers rather than retaining production bypasses.

**Touchpoints:** `app/api/routes/units.py`, `app/api/routes/project.py`,
`app/services/registry_service.py`, `app/services/rendering_service.py`, `app/cli.py`.
Inventory other writers, imports, rebuilds, assistant actions and arrangement updates
so R1/R2's invariant is not limited to the routes identified in the report.

### R3 Define review evidence and a conservative migration

**Owner:** engineering and project/schema owner. **Start:** alongside R1.

Approve a versioned contract for stable principal ID and kind, granted role,
submission channel, decision, exact target digest, applicable policy revision and
immutable decision ID/time. Define a deterministic digest over review-relevant
content: text, layer, target spans, actual alignment/source-accounting revision,
source edition/snapshot, translation basis and substantive style constraints.
Exclude audit history, cached summaries and review records themselves to avoid
circular hashes. Specify which metadata edits do not invalidate review.

`schemas/unit.schema.json` currently sets `additionalProperties: false` for review
decisions. Produce examples, migration rules and a schema-review proposal before
adding fields. Keep mandatory audit/alignment contracts intact. Do not hide identity
or digest evidence in free-form notes or fabricate a past digest from today's text.

**Acceptance:** examples cover text, span, alignment, source and policy changes;
the contract distinguishes historical evidence from current eligibility. A read-only
migration preview reports affected records. Legacy approvals remain inspectable but
do not satisfy the new gate until explicitly reattested. No automatic reapproval,
canonical text/status rewrite or weakening of validation occurs during migration.
Test fixtures demonstrate both legacy refusal and explicit reattestation.

**Touchpoints:** `schemas/unit.schema.json`, `app/services/review_service.py`,
`app/services/rendering_service.py`, `app/services/audit_service.py`,
`docs/REVIEW_POLICY.md` and versioned migration tests. Schema edits are a future
approval gate, not work performed by this plan.

### R4 Use GitHub publications for author and reviewer identity

**Owner:** engineering and project owner. **Dependency:** R3.

Draft and record intentional choices locally. Start with the existing pull request
workflow for publication. When a proposal is linked, read the publication from the
configured GitHub repository and link its publisher account, pull request and
commit to the audit trail. Use GitHub's durable account ID for attribution and the
handle for display. The pull request establishes who submitted it. Credit for an
individual contribution should point to the publication that supports it.
[GitHub account IDs](https://docs.github.com/en/rest/users/users#get-a-user-using-their-id)

Use the same pull request for required sign-off. The author publishes the wording
and any rationale or footnotes they choose to share. A qualified reviewer can review
the proposal in GitHub, and the workbench imports the decision and shows it beside
the candidate. One review can cover the target list in the published snapshot, with
any departure-specific judgments the policy calls for. The project owner maps GitHub
account IDs to the existing qualified roles. People use their GitHub accounts for
this workflow.
[GitHub pull request reviews](https://docs.github.com/en/rest/pulls/reviews#list-reviews-for-a-pull-request)

Verify the repository, review event, reviewed commit and covered targets before
binding a decision to the R3 payload and policy. Record the GitHub evidence in a
structured source reference through an approved contract. Treat manually entered
names and PR links as pointers for verification. Keep known bots, MCP and assistant
observations advisory. Fetch evidence with read-only access and keep any access
credential out of content, logs, tool output and Git.

**Acceptance.** The workbench imports a genuine scoped review once and attributes
it by account ID even after a handle change. An unqualified account, bot, dismissed
review, wrong repository, or mismatched commit or scope supplies no authority.
Local UI, CLI and MCP submissions cannot manufacture GitHub-backed sign-off.
GitHub establishes account attribution. Reviewers are responsible for keeping
control of the accounts they use to make decisions.

**Touchpoints.** Extend existing PR linking, review services and audit views.

### R5 Derive eligibility from current decisions rather than cached counts

**Owner:** engineering. **Dependencies:** R3 and R4.

Replace the present maximum of stored counts and observed approvals with evidence
derived for the current digest. Use each stable reviewer's latest applicable
decision, with deterministic ordering. Define withdrawal, rejection and
request-changes behavior, including how unresolved objections block promotion.
Bind release approval to the same candidate and policy revision.

Invalidate eligibility when reviewed text, source identity, spans or accepted
alignment/accounting changes. Current permission revocation must block the affected
use even when the historical review remains intact. Apply equivalent rules to
arrangement departures and omitted material.

Run these checks in the background when accepting, promoting or releasing content.
When a required approval is missing or stale, identify the affected item and what
needs review. Keep historical decisions visible. Import fresh GitHub review evidence
for an older rendering when it is needed for the current acceptance or release scope,
including its dependencies. Leave draft history available without assigning a
corpus-wide reapproval task.

**Acceptance:** two approvals followed by a substantive edit cannot promote/export;
approve then reject/request-changes/withdraw no longer counts as a positive decision;
duplicates count once; cached counts cannot restore readiness. An unrelated later
approval cannot conceal an unresolved objection under the ratified policy. Reapproval
of the corrected exact revision works and retains prior evidence.

**Touchpoints:** `app/services/review_service.py`, `rendering_service.py`,
`arrangement_service.py`, `report_service.py`, `export_service.py`.
Existing export already hydrates review state: strengthen that resolver rather than
adding a second competing approval calculation.

### R6 Commit revisions and audit records consistently

**Owner:** engineering. **Dependencies:** R1 and R3; integrate with R5.

Use a small shared commit boundary: load under lock, check expected revision,
work on a copy, validate/mutate, derive current review state, append a matching
AuditRecord, then atomically persist. `registry_service.update_unit` presently saves
before its caller finishes validation, and ordinary JSON writes are direct.
Remove that early write from governed paths.

Define and version the audit hash projection before implementing this boundary:
which ledger/self-referential fields are excluded from `before_hash`/`after_hash`,
and how legacy records retain their original interpretation. Keep this calculation
distinct from the review-payload digest and final release-file hashes. A regression
must independently verify the documented audit calculation; do not silently
reinterpret old audit hashes or try to hash a record containing its own hash.

Reuse `immutable_file_service.atomic_write` and `workspace_lock`. Define lock scope
and ordering with the existing `study-publication.lock`; do not add an unrelated
transaction system. Promotion must update target, previous canonical, membership,
signoff and audit together. Do not hold a workspace lock while waiting for a model;
compare expected source/candidate revision when accepting its result.

**Acceptance:** simultaneous reviews are retained; concurrent edits conflict instead
of silently overwriting; failed validation does not write; interrupted replacement
leaves valid old or complete new JSON. A committed content mutation and its audit
cannot diverge. Cross-process tests cover the Windows path and the POSIX lock path,
including export competing with a content/policy edit. Resolve nested-lock deadlock
risks before converting callers broadly.

### R7 Publish the exact snapshot that passed review

**Owner:** engineering and release reviewer. **Dependencies:** R5 and R6.

Keep the existing license, drift, review and source-closure gates. Capture one
consistent content/source/policy snapshot, recompute eligibility from its valid
evidence and serialize that snapshot. Export already holds a publication lock;
ordinary governed writers must participate in the same consistency design.

Stage bundle files and verify their manifest before marking a release complete.
An interrupted attempt must not replace the last good bundle with a partial one.
Bind release evidence to selected content and permission identities; apply D1's
explicit pilot scope before a real partial-Psalter release. Freeze release snapshot
time, serialization and file ordering. Keep variable execution timestamps in a
separate receipt so re-export does not change the deterministic publication payload.

**Acceptance:** stale or revoked decisions, forged summaries and changed source
permissions cannot yield a ready release. A concurrent edit either conflicts or
leaves the captured approved snapshot consistent. Repeated export of the same
approved snapshot produces identical release bytes/hashes. HTTP/MCP/CLI agree.
Existing blocked Greek/history exclusions stay in force.

### R8 Repair the operator journey and complete the P0 regression gate

**Owner:** engineering. **Dependencies:** integrate throughout R1–R7.

Keep the `add-alternate` proposal path delivered with R1/R2. Remove hardcoded CLI
release identity. In the workbench, show which GitHub reviews apply to the current
version and surface expired approvals, unresolved objections and agent observations.
Link to the publication next to the wording it covers.

Add a compact interface parity suite around shared policy cases. In an isolated
fixture workspace, prove proposal → verified reviews from distinct qualified
accounts → authorized promotion/signoff → permitted export. Exercise edit-after-review,
revoked approval, agent impersonation and recovery. Preserve MCP route coverage or
explicit exclusions.

**P0 exit gate:** all identified production write paths obey the shared rules;
failed operations leave content unchanged; successful mutations have valid audit
records; reviewers cannot approve through arbitrary name strings; the complete
fixture journey and affected integration tests pass. Passing this gate authorizes
neither actual human signoff nor publication of the current proposed corpus.

## P1 Validate translation quality with real human evidence

### Q1 Freeze a small protocol and source packet

**Owner:** Hebrew/lexical lead and engineering. **Start:** parallel with P0.

Create a versioned study manifest using the existing
`docs/research/reviewer_signoff_rubric.json`, contextual rubric, benchmark seed and
selection helpers. Start with **30 target-unit packets**: six calibration, twelve
development and twelve locked heldout. Each has enough whole-Psalm context to judge
its target. Group by Psalm and known refrain/near-duplicate family; neither
calibration nor development families may cross into heldout.

Use the exposed 23-unit seed and known goldens for calibration/development. Select
heldout targets outside known project tuning/saved-output exposure where feasible,
record prior exposure, and have a human check sampling strata. Include routine
language, grammatical ambiguity, speaker/negation traps, image/parallelism pressure,
witness-sensitive decisions and reception-sensitive passages. Adversarial provenance
fixtures belong in software tests, not natural-language quality averages.

Freeze source editions, tokenization/versification, permitted context, target brief,
rubric version, model/runtime/prompt configuration, candidate-selection rule, attempt
budget and failure definitions. The primary first outcome is expert-rated literal
fidelity of AlephTav output; this is not yet a Logos superiority experiment. Begin
with one configured generator and one declared final candidate per target, retaining
every attempt. Existing runners support gloss/literal; do not start all models,
all candidates and all seven layers.

**Acceptance:** the manifest reproduces selection, detects split leakage and records
all input hashes. Required human assignments and scoring instructions are complete
before the scored sessions. Changes after heldout unblinding require a new protocol
revision and an unused heldout set. Prior project exposure tracking does not assert
that a pretrained model has never seen a verse.

### Q2 Capture immutable candidates and produce blind review packets

**Owner:** engineering. **Dependencies:** Q1 and the R3 evidence contract.

Add one small study service and CLI, reusing source snapshots, translation-context
capture and immutable-file primitives. A candidate snapshot includes exact output,
spans, context, source/policy identities, briefing/guidance, prompt/model or human
workflow provenance, attempt/failure records and hashes. A live rendering ID alone
is insufficient because it can later change.

Store durable candidates, review records and the restricted blinding map under an
explicit backed-up `data/local/quality_studies/<study_id>/`. Keep protocol examples
and contracts in versioned project documentation; derived summaries belong under
`reports/quality/`. Do not put irreplaceable human decisions only in rebuildable
caches/reports, and do not depend on regenerating the absent research-dashboard tree.

Blind packets use opaque randomized IDs and identical formatting. Exclude author,
provider, model, arm, run IDs and generated rationale from the first fidelity pass.
Permit a separate traceability/rationale pass after independent ratings are saved.

**Acceptance:** conflicting overwrite is refused; old revisions remain readable;
packets contain no revealing metadata or unauthorized source text; any candidate or
input change invalidates applicability. Source permission changes are rechecked
before packet distribution; display or generation permission alone does not grant
export/sharing rights. Backup/restore preserves the restricted mapping.

### Q3 Ingest genuine reviews and preserve adjudication

**Owner:** engineering and review lead. **Dependencies:** Q2 and R4/R5.

Extend the current review-template generator with opaque candidate IDs and validated
CSV/JSON ingestion. Do not build a large new reviewer UI first. Record assignment,
human principal, role, candidate digest, rubric version, dimensions, gate failures,
corrections, confidence, time and notes. Map rubric roles such as `Hebrew` explicitly
to application roles such as `Hebrew reviewer`.

Keep automated checks, model critiques, human research scores and publication
approvals as distinct evidence. The existing generated workbooks are pending
templates; their creation cannot increment completed human review counts. Preserve
independent ratings before discussion; append corrections/superseding reviews and
adjudication rather than overwriting disagreement.

Accept a review file through the authenticated reviewer's channel, or require an
explicitly verified human attestation imported by an authorized operator. Preserve
the attesting reviewer and `imported_by` separately. An assigned reviewer ID written
in a CSV is not evidence of authorship, and an operator's import permission cannot
substitute for the human attestation.

**Acceptance:** unknown or unassigned reviewers, wrong roles, stale candidate/rubric
identities, duplicates and agent submissions cannot count as human scores. Missing
reviews remain missing, not zero or passing. No numerical score or imported study
review automatically promotes a rendering or creates canonical/release approval.
Any later publication decision uses R5 against the final content revision.
Include a forged-file test that uses a real assigned reviewer's ID but lacks their
verified submission or attestation.

### Q4 Make source accounting specific to the candidate

**Owner:** engineering and alignment reviewer. **Dependencies:** R3, Q2; design early.

Correct two current alignment limitations before using coverage as a quality gate:
target IDs must refer to actual spans, not merely have a plausible prefix; coverage
must be scoped to the exact rendering, layer and source revision rather than unioned
across every alignment in a unit.

Keep proposed hints, lexical estimates, formal links and human-accepted accounting
visibly distinct. Validate span ownership, boundaries, exact source membership and
applicable review evidence. An alignment edit that changes reviewed meaning must
invalidate the relevant approval even if the English text is unchanged.

**Acceptance:** another alternate/layer cannot supply this candidate's coverage;
nonexistent spans and stale source IDs fail; a real unresolved/uncertain link remains
uncertain. Reports distinguish directly rendered, grouped/idiomatic, explicitly
omitted, added and unresolved material. A numerical confidence value alone never
makes a link human-reviewed.

`schemas/alignment.schema.json` requires both source and target members. Represent
true omissions and unanchored additions through the existing arrangement departure
records or a separately approved accounting contract, not invented links. Do not
loosen the mandatory schema to obtain 100 percent coverage.

### Q5 Execute the pilot and report outcomes without hiding failures

**Owner:** review lead; engineering supports execution. **Dependencies:** Q1–Q4.

Use two independent qualified fidelity reviewers per scored output; role coverage
may require additional people on particular passages. Calibrate using the first
six packets, improve the workflow on development material, then freeze configuration
before the heldout run. Preserve initial output, corrected output and review cost
separately. Log retries, malformed outputs, timeouts and abandoned attempts.

Retain the baseline 0–5 rubric, candidate mean of at least 4.0 and no gate failures
as the starting proposal for calibration. Before heldout review, ratify dimensional
floors and serious-error rules so a high average cannot hide a wrong subject,
negation, speaker, lexical sense, omitted source claim or unsupported interpretation.
Keep reviewer disagreement and required corrections visible; unresolved serious
issues prevent acceptance regardless of the average. A score is evidence for a
human decision, not an automatic publication command.

Produce one result summary directly from durable records: attempts, valid outputs,
review completion, dimensional scores, serious failures, disagreement, corrections
and review time, with exact denominators. Exclude dry runs from real-output rates.
Use descriptive pilot results; twelve heldout targets do not establish general
translation superiority.

**Acceptance:** all required heldout ratings exist and refer to frozen outputs;
every claimed accepted result has resolved critical issues and independent re-review
of corrections. Failed outputs and incomplete cases remain in the results. A pilot
can finish with a negative outcome, but cannot pass the acceptance gate through a
summary-label change.

For the initial single-workflow study, 30 outputs with two ratings each means
60 rating forms. At an illustrative 15–25 minutes per form, allow **15–25 reviewer
hours**, plus source preparation, calibration discussion, adjudication and the
separate whole-Psalm work. Reestimate after calibration; the arithmetic is not a
claim about actual reviewer speed.

## P1 Complete and recover a small publication

### D1 Define the pilot release scope without bypassing global validation

**Owner:** engineering and release reviewer. **Dependencies:** R7 design; finish
before releasing pilot material.

Current release reporting iterates all units and expects release-reviewer signoff
across the corpus. A three-Psalm pilot cannot legitimately satisfy that requirement
by creating 2,527 artificial approvals.

Implement an immutable selection of included Psalm/unit/rendering revisions and
their source, alignment and review dependencies. Validate and serialize that exact
selection, using the same eligibility rules as full releases. Retain full-corpus
validation as a separate explicit mode. Every included unit/rendering and declared
omission needs the appropriate evidence; unselected drafts are identified as outside
scope rather than silently marked approved.

The legacy exporter serializes renderings, not the arrangement model. Deliver the
reviewed song as an explicitly verified permitted artifact alongside the text
bundle, with cross-referenced manifests. Freeze its arrangement revision, sections,
line/repeat order, source anchors, omitted-token accounting and applicable departure
approvals. Apply source-closure filtering to that artifact too; do not assume the
legacy text files preserve arrangement structure or unrestricted review notes.

**Acceptance:** unrelated draft units cannot be accidentally published or require
fabricated signoff; an invalid included dependency blocks the scoped release.
Selection, arrangement and dependency changes invalidate release approval. The song
artifact reproduces the approved performance order and source accounting.
Full-corpus mode retains its existing policy. If contract approval delays scoped publication, an
isolated pilot workspace with an honestly selected corpus may be used for rehearsal;
do not prune the production corpus or disable its release checks.

**Touchpoints:** `app/services/report_service.py`, `export_service.py`,
`tests/integration/test_review_and_export.py` and existing source-closure tests.

### D2 Review three whole Psalms and one actual arrangement

**Owner:** Hebrew/lexical lead, lyric/musical reviewer and release reviewer.
**Dependencies:** P0, Q3/Q4 and D1; Q5 informs readiness.

Move the selected Psalms through literal and lyric drafting, qualified review,
correction, accepted source accounting and explicit publication decisions. Add
other layers only when the editorial brief needs them. Check whole-Psalm speaker
movement, recurring imagery, refrains and progression that isolated units miss.
If the whole-Psalm work overlaps development material, do not count it as heldout
evidence. Record inherited prior exposure.

For one complete song setting, use the ratified tune/meter/performance brief.
Assess natural stress, breath, diction and singer-rated difficulty in performance.
Review compression, expansion, repeats, additions and omitted Hebrew using existing
departure policy. Vowel-group, word-overlap and heuristic singability scores remain
diagnostics; they cannot substitute for linguistic or musical review.

**Acceptance:** final exact revisions have the required distinct human approvals,
release signoff, resolved critical concerns and permitted source dependencies.
Every source token is accounted for by accepted rendering or explicit permitted
departure; added material is labeled rather than given fictitious source anchors.
Canonical decisions are applied through the review service, never by bulk status
edits. If reviewers are unavailable, drafts remain proposed and this gate stays open.

Keep the initial release Hebrew/English and within its actual permissions. Greek
preview/generation can remain supplemental where authorized, but must not be
treated as reviewed/exportable. Greek-derived drafts cannot be relabeled Hebrew-only
to get through the existing legacy export filter.

### D3 Prove backup restoration and reproducible output

**Owner:** engineering and a second operator where available. **Start backup
preparation early; final dependency:** R7, D1 and D2.

Document the minimum durable project state: canonical/project JSON, applicable
source/package snapshots and permission evidence, local operational state, study
candidates/reviews, GitHub publication and review references, account-to-role mappings,
revocations, authority-contract/policy versions, and necessary settings. Back up
before migration and real editorial sessions; exclude secrets and do not assume
caches are the backup. Recover credentials through a separate protected process.

Restore into a fresh temporary workspace or second machine, rebuild derived indexes,
and reproduce approved text plus deterministic release hashes. Verify review
applicability, current permission handling and the restricted study ledger. A restore
must not revive revoked authority through stale cached summaries or old backed-up
role grants. Require current authority and permission reconciliation before restored
content can be published; if current revocation information cannot be established,
publication remains blocked pending explicit owner reconciliation.

Reuse existing export projections and source-closure work. Free-form local audit
histories currently omitted from public exports remain local; describe those
omissions explicitly. The private recovery archive and the publicly distributable
release are different artifacts. Full forensic archival reconstruction is later work,
not a reason to copy restricted quotations into a public bundle.

**Pilot exit gate:** three reviewed Psalms, one reviewed arrangement, an honest
scoped release, recoverable durable evidence and reproducible permitted output.
Keep software correctness, editorial quality, source permission and recovery status
as four separate pass/fail records. None can substitute for another.

## P2 Expand after the pilot

| Item | Next investment | Start only when |
| --- | --- | --- |
| E1 Workflow improvements | Candidate-specific status and evidence views, exact lemma/morphology filters, reliable occurrence counts and focused reviewer navigation | Pilot users identify the costly steps; authority/status clarity needed for P0 remains in R8 |
| E2 Controlled Logos comparison | Logos-assisted human plus ordinary editor, AlephTav workflow, and combined workflow; same briefs/source identities/time budgets, balanced translator assignments and blinded assessment | Core human evaluation works, qualified participants have lawful Logos access, and a comparative claim is actually needed |
| E3 Operational maturity | Installation packaging, documented support, wider accessibility testing and targeted CI/documentation reconciliation | Restore/release path is dependable; address real pilot failures first |
| E4 Broader data and publication | Expand to the existing 100-unit program, then larger Psalms tranches; follow existing Greek execution gates for Greek release | Qualified review capacity, permitted sources and pilot outcomes support the next tranche |

For E2, each translator should encounter a passage only once, with matched passages
balanced across arms and order. With a single translator, call the result an
exploratory workflow study rather than evidence of a causal accuracy advantage.
Unequal reference access measures whole workflows, not a model or interface alone.
Use manual authorized Logos consultation and permitted citations/excerpts, not an
assumed library-extraction API or external-model license.

At 30 targets and one output per arm, three arms would mean 90 outputs and at least
180 rating forms: an illustrative 45–75 rating hours at the same assumed pace,
before adjudication. Literal and lyric outputs would increase that workload again.
This larger study is not a blocker for the first honest, reviewed local release.

Defer a commentary catalog, full-Bible authoring, native mobile clients, enterprise
identity/SSO, all-seven-layer generation, and a DOCX-to-Logos bridge until evidence
justifies them. Address the MIT/Apache metadata inconsistency before distribution
claims through the required owner process; do not edit protected license/notice
files as routine cleanup.

## Verification and completion records

Implement each ticket with focused regression tests, then run the affected existing
integration/golden and browser checks. Use fixture workspaces via the test harness;
do not run corpus-mutating bootstrap or audit commands against production content
to validate a code change.

The P0 boundary suite must include direct service, HTTP, MCP and CLI cases for
canonical-edit refusal, unreviewed acceptance/demotion, forged authority, agent
approvals, stale revisions, revoked decisions, concurrent edits, failed writes and
export consistency. Quality tests cover split leakage, blind-packet metadata,
immutable candidates, stale/invalid review imports, dry-run exclusion, strict span
ownership and candidate-scoped coverage. Test positive recovery and valid reapproval
alongside refusal cases.

Before merging implementation, run the repository's required validation, relevant
tests, configured lint/format/type checks and UI build where touched. Add focused
governance/quality checks to the existing workflows. CI already exists; reconcile
the stale documentation and limited `npm run lint` scope without bundling an
unrelated repository-wide cleanup. Never bypass `validate_content.py` or weaken
schemas to obtain a green run.

Each ticket's execution entry should record owner, status, changed files, exact
checks and results, unresolved defects, required human decisions and links to
durable evidence. Use `not run`, `pending human review` and `blocked by permission`
truthfully. A generated report, a projected reviewer workload or a passing fixture
test must not be recorded as completed expert review.

## First implementation handoff

Start with a small R1/R2 PR: add failing fixture-only regressions for direct HTTP
canonical edit, status/signoff injection, raw unit/project overwrite and unreviewed
demotion; put shared edit rules in the service; close the unsafe routes; repair the
CLI proposal path. Keep R3's evidence-contract proposal and Q1's pilot preparation
in parallel. This first PR must preserve valid proposal editing and add-alternate
behavior, not merely remove user capabilities without a supported path.

After those regressions pass, implement revision/identity/atomicity work, followed
by actual review ingestion and candidate-scoped alignment. Do not expand generation
to the rest of the Psalter while these gates remain unresolved.

## Existing implementation to reuse

- [Review and export policy](../REVIEW_POLICY.md) and [release process](../RELEASE_PROCESS.md).
- [Review eligibility](../../app/services/review_service.py), [rendering transitions](../../app/services/rendering_service.py)
  and [MCP adapters](../../app/api/mcp_server.py).
- [Atomic files and publication locks](../../app/services/immutable_file_service.py).
- [Human scoring rubric](../research/reviewer_signoff_rubric.json),
  [contextual rubric](../research/psalms_contextual_evaluation_rubric.json),
  [benchmark seed](../research/local_translation_benchmark_seed.json),
  [runner](../../scripts/run_local_model_benchmark_suite.py),
  [structural scorer](../../scripts/score_local_model_benchmark_results.py)
  and [review templates](../../scripts/generate_review_signoff_plan.py).
- [Alignment validation and coverage](../../app/services/alignment_service.py),
  [source flow estimates](../../app/services/source_translation_map_service.py)
  and [arrangement departures](../../app/services/arrangement_service.py).
- [Export source closure execution](export_source_closure_execution.md) and
  [arrangement source execution](arrangement_sources_execution.md): retain completed
  implementation and its remaining gates rather than rebuilding them.
- [Greek application execution](greek_application_execution.md): follow actual
  source, expert, availability and reconstruction gates; it is not a prerequisite
  for the permitted Hebrew/English pilot.
