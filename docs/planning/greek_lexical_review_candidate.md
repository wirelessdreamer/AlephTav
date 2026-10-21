# Greek lexical and reference integration implementation plan

Date: 2026-10-17. Status: candidate for adversarial review. This is an implementation
design, not a statement that the Greek feature or its acceptance tests already pass.

## 1 Purpose and delivery boundary

Deliver this journey in the mounted application: select a Greek Psalter edition, click
a Greek word, inspect its dictionary form and grammatical analysis, follow its lexical
identifiers to attributed dictionary entries, browse every matching occurrence in that
edition, and inspect the reviewed Hebrew correspondence where one exists.

The first release covers **Greek Psalms 1–151 in one approved Swete edition**, alongside
MT Psalms 1–150. “All occurrences” means all token occurrences in the selected edition
and text revision of this Psalter, including the current verse and psalm. It does not
mean the entire Greek Bible. Dictionary citations to other books remain labeled external
references; they do not imply those books have been imported.

Keep three reference types distinct: corpus occurrences, dictionary cross-references,
and bibliographic citations. A G-number is an identifier, not a definition, sense,
morphological analysis, or proof of a Hebrew correspondence.

Release the reader and lexical tools before enabling Greek translation generation.
Reviewed cross-corpus study is the next release. Greek English layers, divergence dossiers,
translator-technique heatmaps and full NT alignment remain subsequent work under
[the broader requirements](SEPTUAGINT_GREEK_REQUIREMENTS.md). Their storage and policy
dependencies are included here so the study release does not make them unsafe later.

## 2 Verified starting point

These findings concern the current working tree, including earlier uncommitted repairs.
File hashes and directly executed planning probes are recorded in
[the validation evidence](planning/greek_lexical_validation.json). The previous test run
is background evidence; it does not validate the future features in this plan.

| Area | Verified behavior | Required change |
|---|---|---|
| Mounted UI | `app/ui/src/main.tsx` imports `app/ui/src/app/App.tsx`, which mounts `ComparisonPage` | Deliver through that page, `TranslationComparisonTable` and `VerseDetail`; legacy `WorkbenchPage` work alone is insufficient |
| Current Greek | MACULA strings and scalar `greek_strong` are attached to Hebrew tokens; the joined witness uses Hebrew word order | Separate hints from actual Greek source tokens; preserve every ordered source component |
| Current dictionaries | `lexical_service._lexicon_entry` returns corpus token matches | Add dictionary packages and entries; do not relabel the occurrence query as a dictionary |
| IDs and storage | `lxx.ps023.v001.a` passes `ensure_id`, but its current runtime path is `content/psalms/lxx/lxx.ps023.v001.a.json` | Add corpus-aware storage and revision-aware identity before Greek import |
| Unit schema | Greek `source_greek` is rejected; `source_hebrew` remains required | Define a Greek contract without filling Hebrew fields with Greek data |
| Index safety | A temporary failed Greek rebuild raised `KeyError('source_hebrew')` and left the previous unit count at zero | Stage and publish indexes; preserve operational state and the last usable index |
| Source enforcement | Prompt builders can include the old joined witness without checking its capability flags | Enforce source permissions at consumers; changing manifest booleans alone is insufficient |
| Anchors | Unrelated Greek plus nonexistent token IDs passes the current script check | Resolve actual source snapshot, unit membership and text spans before accepting a Greek anchor |
| Occurrences | Existing arrays are capped unique verse references; the SQL concordance uses unbounded substring matching | Query complete token counts, distinguish verse counts and paginate exact matches |
| Prior fixes | Greek script checking, deterministic flag severity, anchor persistence, and the double-G display repair already exist | Retain their regressions; do not schedule them as new capabilities |

Do not run the existing full importer as a migration. It bootstraps project settings,
rewrites raw manifests through `save_project`, and can replace tokens while preserving old
alignments. Its behavior conflicts with the raw immutability and audited-mutation policies.

## 3 Proposed decisions and implementation gates

The choices below make the implementation concrete. They are recommendations for the
feature, not retroactive approval to alter existing canonical English or raw sources.

| Decision | Proposed choice | Gate and consequence |
|---|---|---|
| Source text | Corrected Swete 1896 as the first Greek source, from an immutable released package | Package must have license and notices, checksums, edition metadata, provenance and the required owner sample sign-off. Current sibling outputs alone are not that release |
| Source intake | Inspect downloads in staging outside `data/raw`; register only verified immutable packages | Resolve the documented raw-write conflict with an explicit owner-authorized intake procedure before creating any new raw snapshot. No tooling exception is assumed |
| MACULA Greek | Keep as labeled, unconfirmed alignment hints; disable its Greek generation/export use | Implement effective component permissions, not a blanket ban on legitimate MACULA Hebrew enrichment. Do not rename historical `lxx` claims to Swete |
| Greek identity | Edition- and text-revision-qualified unit/token IDs | Schema-owner review must approve this amendment to FR-V0.2 and all dependent parsers; earlier prefix-only repairs are insufficient |
| Lexical identity | Local lexeme IDs, source-entry IDs and external ID crosswalks are separate | No unique primary key on bare Strong or on a normalized lemma string |
| Morphology | QuantForge supplies proposed analyses only; retain ambiguity and unresolved fields | Review a stratified sample before promoting an analysis set; never turn a fallback proper-noun guess into an accepted analysis |
| Annotation review | Greek specialists review lexical/morphological selections; accepted bridges require distinct Greek and alignment reviewers | Implement role combinations and revision-bound approvals, not just another role string |
| Existing projects | Preserve current MT translation ownership and both MT 9 and MT 10 entries | A correspondence group is navigation metadata, not a new uniqueness constraint that collapses translations |
| Rahlfs | A future separate edition and package | Preserve the sibling project's no-access-before-2027-01-01 boundary. No in-place replacement of Swete or independent legal conclusion is implied |

Amend the relevant requirements explicitly before implementation: FR-V0.2 identity;
FR-D morphology/lexical cardinality; FR-S source lineage and intake; FR-R package audits;
and D6 project/group ownership. The base requirements' claim that Psalm 151 exists only
in Greek should read “absent from the MT 150-psalm corpus”; Hebrew Psalm 151 material is
outside this implementation's source set.

## 4 Source packages and feasibility checks

Use commit-addressed URLs and SHA-256 for each imported file. Preserve the upstream
declared license, full attribution text, derivative sources and effective capability
decision separately. A repository badge is not the complete provenance chain.

| Source | Verified pinned artifact | Adapter and release condition |
|---|---|---|
| Corrected Swete | Current sibling text: 151 psalms, 2,527 verse lines and 34,614 word rows; 61 joined-word span records | Adopt only a released package matching inspected hashes. Include punctuation, titles, edition exceptions and fragment provenance. Current HEAD alone does not identify the modified exports |
| STEPBible TBESG | Commit `94802ced31e63882ab42a86d79eb0017df4545e3`; 11,035 data rows, 10,847 distinct eStrong values | BOM/documentary preamble followed by eight TSV fields. Preserve eStrong, dStrong and uStrong expressions. Review Middle Liddell lineage as well as the declared CC BY license |
| STEPBible TFLSJ | Same commit; both `0-5624` and `extra` files | The extra file supplies LXX vocabulary missing from the first file. Review Perseus lineage; transform markup into a constrained representation |
| STEPBible TEGMC | Same commit | Lexical POS descriptions are not occurrence parsing. Keep the source scheme and raw code; do not treat TBESG POS as a word's inflection |
| QuantForge | Commit `46258f8bde173998ef0633d79eff3067b9041575`, `data/morph-morpheus/024-Ps.txt`: 34,243 rows | Nine space-separated fields, MorphGNT POS/eight-character parsing, no Strong IDs. 728 rows use synthetic `morpheus-proper` fallback. Align by verse and surface evidence, never ordinal position against Swete's 34,614 words |
| Abbott-Smith | Commit `8c00cb244761aa23659421a8cbbbf7a3b27b7d59`, designated TEI: 6,153 entries | Public-domain designation applies to the TEI; do not substitute its separately restricted source PDF. Namespaced parser; entries may lack a G-number. LXX-only coverage is not promised |
| Direct Perseus LSJ | Commit `56061ca127f4a2844980baffc5f2b6d1332897b3`; 27 XML files | Legacy TEI P4 and Beta Code require a separate adapter. Preserve entry IDs/keys, block network/entity resolution, apply the source-specific attribution requirements |
| TVTMS | STEP commit above, current `Versification/TVTMS ...txt`: 29,897 lines | Parse documented sections/conditions and baseline explicitly. Generic Greek tradition is not an edition-specific Swete map |
| Copenhagen map | Commit `519af776ab65d89a51e37f750779250f940459ef`, `versification-mappings/standard-mappings/lxx.json` | Many-to-many/title overlaps and `PSA 151` to `PS2` aliases must survive. Use as a cross-check, not an automatic override |

The source lock must contain exact filenames, byte sizes, hashes, parser versions, source
license text hashes and approved uses. Proposed package versions are immutable: a changed
upstream byte requires a new lock and a new review. Pin known inputs rather than fetching
`master` or `main` during tests or builds.

For current sibling Swete exports, the inspected hashes are:

```text
text   9fc94c39ef80b37297885b5bff01344040a666a990c99aa9eb96fb4197c57017
words  7d31d58ba9843e67e179616e216824c2aceed4b82558e98bcd485fd0b20d5524
spans  b911120521882618311ca91627ddf0db92dead767aa2117bba22c1db5e9d2d51
```

These identify inspected artifacts, not a release approval. Existing fragment locations
are leaf/page/line/strip, with no claim of individual word bounding boxes. FR-O.1's
bounding-box requirement needs a separate source-package decision or completion before
claiming that transcription requirement is satisfied.

### External source references

- [Pinned TBESG](https://github.com/STEPBible/STEPBible-Data/blob/94802ced31e63882ab42a86d79eb0017df4545e3/Lexicons/TBESG%20-%20Translators%20Brief%20lexicon%20of%20Extended%20Strongs%20for%20Greek%20-%20STEPBible.org%20CC%20BY.txt)
- [STEP source documentation](https://github.com/STEPBible/STEPBible-Data/tree/94802ced31e63882ab42a86d79eb0017df4545e3)
- [TFLSJ extra](https://github.com/STEPBible/STEPBible-Data/blob/94802ced31e63882ab42a86d79eb0017df4545e3/Lexicons/TFLSJ%20extra%20-%20Translators%20Formatted%20full%20LSJ%20Bible%20lexicon%20-%20STEPBible.org%20CC%20BY.txt)
- [QuantForge Psalter](https://github.com/QuantForgeSoftware/lxx/blob/46258f8bde173998ef0633d79eff3067b9041575/data/morph-morpheus/024-Ps.txt) and [analysis code](https://github.com/QuantForgeSoftware/lxx/blob/46258f8bde173998ef0633d79eff3067b9041575/code/python/analyze_lxx.py)
- [Abbott-Smith snapshot](https://github.com/translatable-exegetical-tools/Abbott-Smith/tree/8c00cb244761aa23659421a8cbbbf7a3b27b7d59)
- [LSJ license notice](https://github.com/PerseusDL/lexica/blob/56061ca127f4a2844980baffc5f2b6d1332897b3/CTS_XML_TEI/perseus/pdllex/grc/lsj/README.md)
- [Copenhagen map](https://github.com/nida-institute/versification/blob/519af776ab65d89a51e37f750779250f940459ef/versification-mappings/standard-mappings/lxx.json)
- [Unresolved MACULA provenance question](https://github.com/Clear-Bible/macula-hebrew/issues/145)

## 5 Identity and canonical data contracts

### Source identity and retained revisions

Use an immutable source identity such as:

```text
edition_id       swete1896
text_revision_id r0001                    # manifest also records content SHA-256
unit_id          lxx.swete1896.r0001.ps022.v001.a
token_id         lxx.swete1896.r0001.ps022.v001.t001
rendering_id     rnd.lxx.swete1896.r0001.ps022.v001.a.literal.alt.0001
```

Edition IDs use a documented conservative slug grammar. A text revision binds source
bytes, corrections, segmentation and tokenizer version; its label cannot be reused with
different hashes. Any text/tokenization change publishes a new revision. Reuse unchanged
source locations as evidence, but do not silently reuse a token identity for a new word.

Retain old revisions while any rendering, annotation, cross-link, review, cursor or export
references them. Retargeting is an explicit operation with a split/merge/insertion/deletion
map and fresh review for affected evidence. Lexical annotation corrections have their own
revision and do not pretend that source text changed.

Existing MT IDs and paths remain unchanged. Previously admitted `lxx.ps...` IDs are logical
legacy locators, not sufficient source anchors: require an explicit edition/revision to
resolve them; do not accept ambiguous or unversioned Greek writes. Inventory any persisted
legacy Greek IDs before removing or redirecting a route. Use a structured identity helper
instead of dotted-string offsets throughout registry, rendering, comparison, Codex and UI.

### Proposed storage

```text
content/lxx/editions/<edition>/<text_revision>/package.json
content/lxx/editions/<edition>/<text_revision>/psalms/psNNN/<unit_id>.json
content/lxx/editions/<edition>/<text_revision>/annotations/<analysis_set>.jsonl
content/lexicons/grc/<source>/<package_revision>/entries.jsonl
content/lexemes/grc/lexemes.jsonl
content/versification/lxx/<edition>/<text_revision>/map.json
content/cross_alignments/mt_lxx/<edition>/<text_revision>/<set_id>.json
content/source_registry.json
content/audit/packages/<package_id>.jsonl
```

These are normalized canonical packages and authored annotations, not mutable raw inputs.
Derive indexes and backlink lists from them; avoid copying cross-alignment IDs into every
MT unit merely to support navigation. Each package has a deterministic manifest and schema
version. Imports are staged and validated before a registry descriptor makes them active.

Add strict Greek unit/token, dictionary-entry, lexical-crosswalk, annotation-set,
versification and cross-alignment schemas. Share mandatory rendering/alignment/audit
structures where appropriate. Keep the existing Hebrew contracts valid; do not satisfy a
Hebrew `stem`, OSHB or MACULA requirement with fabricated Greek values.

### Greek words and lexical identifiers

Each Greek token stores its source surface, original source locator/fragments, text span,
position and canonical NFC form. Search normalization is a separate derived field: case
folding, sigma handling, optional mark-insensitive keys and explicit elision handling.
Keep diplomatic spelling, marks and iota distinctions in source text. Confusable Latin or
Cyrillic characters produce findings; automatic replacement is not a source correction.

Keep the following separately:

- A local `lexeme_id`, with language, dictionary headword and reviewed distinctions.
- A source-specific `entry_id` and source locator, scoped to its immutable package revision.
- External identifier assignments `{scheme, value, relation, source_entry_id, status}`.
- Token analyses with lemma candidates, raw tag/scheme, parsed features, provenance,
  confidence, status and an optional reviewed selected analysis.

An external ID remains a string. Accept documented extended ranges without a hard maximum,
retain suffixes such as `G2264G`, and preserve scheme identity. `G2264` can return multiple
entries rather than choosing a person implicitly. `G1508` combination relationships and
`G2504` crasis relationships are typed edges, not sets of equivalent aliases. Crosswalks
may point to Hebrew IDs without claiming Hebrew and Greek words are interchangeable.

Every word must have an annotation status; unresolved lemma/morphology/ID is represented
explicitly. “All fields populated” is not an accuracy requirement. Inflectional morphology
comes from occurrence analysis, not a dictionary POS field. A null external ID is allowed
with a recorded lexical gap; it must not hide the word from the concordance.

### Canonical audits and approvals

The current audit writer allocates IDs from an owning verse. Add an approved package audit
namespace/container for source registration, dictionary entries, maps, analysis sets and
cross-boundary links; never invent a verse to obtain an audit ID. Preserve every mandatory
AuditRecord field, before/after hashes, actor, rationale and signoff. Namespace examples and
strict patterns must be approved with the schema patch and tested against old records.

Review decisions bind target ID, payload hash, source revisions and reviewer identity.
Compute specialist eligibility from current decisions, without satisfying new requirements
through cached historic approval counts. Changes invalidate the affected decision's
applicability while retaining its history. Canonical English changes still require two
qualified approvals; no import or source switch supplies those approvals automatically.

## 6 Import and source policy

Build a dedicated source intake/registration service. A dry run reports added packages,
license decisions, source exceptions, token counts, annotation matches/gaps, prospective
content changes and affected references. It must not call `bootstrap_project` or the current
full importer. Preserve project settings and existing canonical content exactly.

Keep source capabilities in an effective registry that can override a legacy manifest
without rewriting `data/raw`. Track source components: MACULA Hebrew enrichment and its
unconfirmed Greek correspondences can have different permitted uses. Denied components
must be removed before constructing prompts, lookup results or exports, not merely labeled
afterward. Separate roles for Greek source text, dictionary glosses and English translation
witnesses; English witnesses remain excluded from generation.

Check the full dependency chain for display, generation and export. Include lexical entry
fragments, morphology, cross-links, generated reports and cached payloads. Unknown lineage
blocks the affected capability. Restricted local witnesses stay outside committed content
and public indexes; their text cannot leak through counts, snippets, prompt logs or nested
audit/export payloads. Ordinary open Greek study does not depend on installing them.

Imports read immutable packages, normalize into staging, create required audits, validate
all schemas/references and activate one manifest only after every file is complete. A retry
of the same package is a no-op. A different checksum under the same revision fails. Preserve
previous active manifests for rollback; rollback changes selection, not historical evidence.

Morphology transfer first uses edition-qualified verse mapping and normalized source spans.
QuantForge/Swete token-count differences prohibit ordinal joins. Candidate matching must
support split/joined forms and multiple analyses; unmatched tokens remain unresolved.
Record matching evidence and evaluate independently before any selection becomes reviewed.

The Swete map needs edition exceptions: do not fabricate 135:23, which is absent in this
edition, merely because a generic LXX map includes it. Preserve titles, subverse spans,
cross-psalm Hallelujah shifts and explicit Greek-only/MT-only/edition-absent cases. Swete's
Vaticanus lacuna and Sinaiticus substitution need span-level attribution: B through 105:26,
S from 105:27 through the first clause of 137:6, and B again at the printed within-verse
boundary. Apparatus silence leaves an unresolved check, not a proven transcription error.

## 7 Search indexes and bounded queries

Separate rebuildable search catalogs from operational state before replacing the current
destructive rebuild. Keep generation jobs and UI state in the operational database.
Build immutable catalog files containing MT and approved Greek indexes, then atomically
publish a small active-catalog descriptor. Update all lexical/search readers and summary
cache builders to use catalog connections; jobs and UI state retain operational connections.

Build and publish protocol:

1. Bind a validated canonical manifest and all source/annotation revisions.
2. Build a new database under a staging name; create indexes and run SQLite integrity,
   foreign-key, uniqueness, row-count and representative query checks.
3. Close writers and seal the catalog. Publish its descriptor with an atomic file replace;
   readers retain the catalog revision they opened for the duration of a request.
4. Tag caches and cursors with that revision. Retain the last catalog and every catalog with
   active readers; remove retired files only after handles are closed, including on Windows.
5. On failed build or publish, keep serving the previous descriptor; on startup validate the
   active descriptor and fall back to the recorded last-good catalog if necessary.

Proposed indexes: Greek units/tokens, analysis candidates/selections, lexemes, dictionary
entries, typed external-ID assignments, verse-map spans and cross-alignment membership.
Use composite scope keys containing edition/text revision and annotation/index revisions.
Persist canonical entry text in source packages; SQL is a rebuildable query mirror.

Concordance defaults to exact lemma/identifier match. Surface prefix/substring modes are
explicit and accent-insensitive when selected. Unknown field names return a validation
error. Return token count, distinct verse count, page items and next cursor; never use the
old capped reference arrays as totals. Default page size 50, maximum 200. Order by structured
reference, position and token ID, with the immutable catalog/query fingerprint in the cursor.
An unavailable old catalog yields a typed stale-cursor response and a restart action.

## 8 Services and user interface

### Service contracts and operational interfaces

Implement Greek corpus, lexical, versification, annotation and cross-alignment services.
Routes and CLI/MCP call those services; no client performs direct content writes.

| Interface | Required behavior |
|---|---|
| `GET /lxx/editions` | Approved editions/revisions, availability, provenance and capabilities |
| `GET /lxx/psalms` and `/lxx/units/{id}` | Structured edition references and actual Greek tokens; no joined-hint fallback |
| `GET /greek/tokens/{id}/card` | Source identity, analyses, IDs, dictionary summaries, exact counts, provenance and review state |
| `GET /greek/lexicon/entries/{entry_id}` | Attributed sanitized entry and typed internal/external references |
| `GET /greek/lexicon/identifiers` | Exact scheme/value lookup; zero/one/multiple results are explicit |
| `GET /greek/concordance` | Bounded results with total tokens/verses, revision and cursor |
| `GET /versification/map` and `/units/{mt_id}/parallel` | Many-to-many, title, absent and Greek-only results with labeled references |
| Cross-alignment read/review routes | Explicit active set, status filtering, endpoint validation and atomic replacement |

Every new route gets an MCP tool or a reasoned `EXCLUDED` entry, checked by the existing
coverage test. Add CLI intake dry-run/apply, validate Greek packages, build/check catalog,
inspect gaps, seed cross-alignments and export a study bundle. Mutations stamp their actual
actor and write audits. Read-only tools must not imply acceptance or canonical promotion.

### Mounted study flow

Extend `ComparisonPage`, `AppContext` and the active comparison table with MT/LXX/Parallel
selection and edition/revision selection. Group navigation can select multiple MT/LXX
members; preserve existing translations rather than moving or merging them. Psalm 151 is
reachable directly despite having no MT partner. Show corpus names with references.

Add `GreekSourcePane`, a native Greek token button, `GreekWordCard` and `useGreekStudy`.
Use `lang="grc"` and LTR for Greek, with separate Hebrew RTL spans. Distinguish surface,
dictionary lemma, lexical IDs and occurrence parsing. Expose candidate/unresolved status and
the source of each analysis. A missing entry or unaligned token is a visible state, not an
empty card or an inferred “no Hebrew counterpart.”

Load brief lexical data first, long entries on demand, and occurrences in bounded pages.
Treat dictionary markup as untrusted. Convert HTML/TEI/custom references to a constrained
presentation tree, escape text, disable XML external/network entities and reject script,
event-handler and `javascript:` links. Unsupported markup becomes safe text plus a parser
finding. Do not use raw `dangerouslySetInnerHTML` for upstream dictionary content.

Cache keys include edition, text/analysis/catalog revisions, token or query, and translation
context when English is included. Switching project/edition cannot retain another project's
English snippet. Reject stale asynchronous responses after selection changes.

Greek words work by keyboard and touch, not hover alone. Enter/Space opens the persistent
card; Escape closes overlays and returns focus. Definitions, references, filters and
occurrence navigation are keyboard reachable. Announce loading/errors, preserve controls
at 200% zoom and 430px width, and show attribution on the card and exported entry.

### Reviewed Hebrew bridge

A cross-alignment set references immutable MT and Greek snapshots. Rows support many-to-many
groups, explicit Greek plus/Hebrew minus, transposition and uncertainty. Reject both-empty
rows, nonexistent tokens, wrong revisions and overlapping active accepted ownership.
Exactly-one coverage applies within a declared accepted set when it is marked aligned;
proposed alternative analyses do not violate accepted-set uniqueness.

Seeds enter proposed. Counts and distributions default to accepted evidence, with separate
proposed/unresolved totals. A Greek-plus claim requires an explicit reviewed observation;
absence of a link means unresolved. A new accepted set atomically supersedes the old one;
old approvals and exports remain attributable to the set they used. Store hypotheses about
a Hebrew Vorlage separately from observed links. Do not reuse English-span coverage code.

## 9 Work packages and dependency order

Each row is a reviewable change set; split schema/parser/service work further if a diff
cannot be assessed independently. Source-data review runs alongside software work.

| Package | Owner role and files | Depends on | Exit condition |
|---|---|---|---|
| W0 decisions and source lock | Owner, schema owners, Greek reviewer; requirements, data-source policy, lock/evidence | — | Section 3 choices resolved for the next slice; source permissions and intake procedure are explicit |
| W1 capability and audit foundation | Backend; registry, license rules, audit service, manifest/audit schemas, input consumers | W0 | Effective component permissions enforced; global package mutations auditable; no raw writes/config resets |
| W2 identity and Greek contracts | Backend/schema owners; IDs, config, registry, schemas, validator, remaining positional parsers | W0 | MT round trips unchanged; simultaneous edition/revision IDs route and validate; Greek units require Greek fields |
| W3 immutable Greek import and maps | Data/backend; new intake/import/versification services, scripts/CLI | W1 W2 and approved source package | All 151 psalms accounted for, titles/135:23/151 handled, idempotent activation and rollback proven |
| W4 catalog lifecycle | Backend; DB connection separation, concordance rebuild, lexical/search readers, summary caches | W2 | Failure injection preserves live queries, jobs and UI state; MT and Greek counts agree with canonical packages |
| W5 dictionary adapters | Data/backend; TBESG, both TFLSJ, Abbott-Smith, optional direct LSJ, crosswalk schemas | W1 W2; approved per-source permissions | Every input row accounted for; typed relationships, attribution and safe rendering fixtures pass |
| W6 morphology and lexeme analysis | Greek/data reviewers; QuantForge adapter, normalizer, analysis-set schema/review service | W2 W3 W5 | Every token has status; ambiguity/gaps retained; stratified accuracy review published with seed errors exposed |
| W7 lexical APIs and concordance | Backend; lexical services, catalog queries, routes, MCP/CLI contracts | W3 W4 W5 W6 | Exact ID lookup and complete bounded occurrence traversal pass; no seed status hidden |
| W8 mounted Greek word study | UI/backend; active page/context/table/card/hooks/styles, service DTOs | W7; basic source reader can start after W3 | End-to-end word journey passes keyboard, offline, project-switch and source-attribution checks |
| W9 accepted Hebrew Greek bridge | Greek/alignment reviewers, backend/UI; cross contract/service/review/view | W1 W2 W3 W6 W8 | Gold set reviewed; atomic accepted coverage and distinct specialist roles enforced; proposed counts remain separate |
| W10 release export and rollout | Backend/release reviewer; export/report/notice generation, feature availability | W8; W9 for reviewed bridge release | Exact dependency/attribution manifest, reconstruction and failure rollback tests pass; owner/source signoffs complete |
| W11 later Greek generation | Backend/model-pipeline owners; prompts, source resolver, generation/composer/Codex/briefing/rebuild | W9 W10 and separate generation capability approval | Actual revision/token/span anchors checked on every path; no English-witness inputs; specialist rendering approvals enforced |

Critical path for the first useful release is W0 → W1/W2 → W3/W4/W5 → W6/W7 → W8/W10.
Dictionary adapters and safe catalog work can proceed independently after their foundations.
The approved source package and Greek review capacity are real dependencies; do not hide
them behind a coding completion estimate.

Release A is the approved Greek reader/card/dictionaries/concordance, with unresolved
analyses and links labeled and Greek generation disabled. Release B adds the reviewed bridge
and distributions. Neither claims to translate the whole LXX or satisfy every expert-analysis
requirement. Keep MT as the default until the new route is enabled by an explicit feature
availability record tied to an approved source/catalog.

## 10 Validation and acceptance matrix

The checks below are **future implementation acceptance tests**. Local probes in section 2
and the source inspections in section 4 have already run; benchmark targets and future test
results have not. Build offline fixtures from permitted minimal examples and authored cases.

| Test family | Required adversarial cases and assertions |
|---|---|
| Identity/storage | MT and two Greek editions with identical verse labels never collide; two text revisions preserve old anchors; every new ID loads/lists/saves/validates/exports with its intended corpus; reject unknown/ambiguous locators |
| Greek schemas | Greek data cannot satisfy Hebrew-only fields accidentally; unexpected fields and malformed IDs fail; analysis gap and ambiguity are valid explicit states; old MT fixtures remain valid |
| Source policy | Disabled/unconfirmed Greek component absent from generation/composer/Codex single/passage/rebuild/briefing inputs; blocked display/export returns no text/snippets/count leakage; English translation witnesses excluded while permitted lexical glosses remain allowed |
| Intake/migration | Dry run has zero writes; apply audits every canonical mutation; second apply is a no-op; checksum reuse fails; malformed package, disk-full and interrupted activation preserve prior content/config; snapshot all raw files before/after and require byte identity |
| Source text/map | LXX 1, merged 9, joined 113, split 114–115, 147 split, 151, titles and cross-psalm Hallelujah; Swete 135:23 absent; 137:6 has two witness spans; overlapping generic title mappings do not lose links |
| Unicode/lexical IDs | NFC/NFD idempotence, sigma variants, breathings/accents, elision, iota handling, preserved diplomatic spelling; Latin/Cyrillic findings; G3107/bare 3107 source normalization, G6908, G2264G/H/I, G21502, Hebrew cross-reference, multi-ID expression, absent and malformed IDs |
| Dictionary parsers | BOM/preamble, repeated eStrong, both TFLSJ files, combination vs equivalence, custom references, malformed rows, TEI namespaces/P4 entities and Beta Code; XXE/network attempts, scripts, events and unsafe URL schemes never execute |
| Morphology | QuantForge MorphGNT-to-feature conversion preserves raw tags and unknowns; ὁδῷ is not accepted as masculine by default; synthetic proper-noun fallbacks remain proposed/unresolved; token-count mismatch cannot be handled by ordinal zip |
| Concordance | Fixture with 1,003 matching tokens, repeated hits in one verse/current psalm, distinct verse total; traverse 50-item pages with no omissions/duplicates; exact G1 never returns G10; separate suffixes and editions; invalid filters rejected; stale cursors explicit |
| Index failure safety | Existing jobs and selected-card state survive rebuild; bad Greek/duplicate ID/fault during build or pointer publish leaves previous queries working; old reader completes on its catalog while a new reader opens the new one; Windows handles do not block recovery |
| Review/bridge | Distinct specialist roles and content hashes required; no cached historical count bypass; both-empty/wrong-revision/foreign-token links rejected; plus/minus/many-to-many/cross-psalm work; proposals excluded from accepted totals; edits and retargeting require new applicable approval |
| API/MCP/CLI | Identical service outcomes for all interfaces; actors stamped; coverage test for every route; Greek import/index/diagnostics reproduce offline without authentication or model calls |
| Mounted UI | Source/edition switch, Greek word, safe long definition, all occurrences, navigate a hit, Hebrew counterpart, reverse navigation, Ps151; project switching/out-of-order requests cannot show wrong English; keyboard/touch/zoom/loading/error states covered |
| Export/rollback | Validate full provenance closure including entries/annotations/maps/audits; block restricted content at all nested locations; preserve old published revisions; disabling Greek availability restores MT navigation without deleting either corpus |

Targeted code locations include `tests/support.py`, new Greek contract/normalization/parser/
concordance/import/review tests, `tests/integration/test_mcp_server.py`, active comparison API
tests and current-route Playwright scenarios. The root `npm test` currently runs Python and
goldens; it is not evidence of a configured React unit runner. Add an explicit UI unit setup
only where it adds value; use current-route browser tests with mocked local data regardless.
Remove the full raw-tree-copy dependency from lean Greek fixtures before making them a
routine fast check; use unique temporary roots for concurrent test processes.

Quality gates distinguish parsing, coverage and accuracy. Require 100% input-row accounting,
zero broken references and zero unexplained dropped source words. For a proposed first
annotation release, review at least 600 stratified token occurrences across Psalter books,
parts of speech, names, elision, low-frequency forms and known seed errors. Proposed targets
are ≥99% lemma accuracy and ≥97% parsed-feature accuracy on expert-unambiguous reviewed
cases, with unresolved coverage reported separately. Publish exact numerators/denominators,
sampling design, ambiguous cases and interval method; these targets are not measured results
or a guarantee about all Greek tokens. Revise them explicitly after the pilot rather than
forcing a wrong analysis to meet a completeness percentage.

Proposed performance targets on a documented full-Psalter fixture: warm local API p95
≤200 ms for a brief card and ≤300 ms for a concordance page; brief card ≤100 KB excluding
requested long entries. Record hardware, dataset/catalog hash, sample count and cold/warm
conditions; inspect query plans and prohibit corpus-file reads per returned hit. If the
pilot misses a target, profile the failing stage rather than asserting performance from
the tiny fixture. Accessibility and correctness gates apply regardless of timing.

## 11 Migration and release procedure

1. Inventory and hash current content, source metadata and operational state. Treat the
   dirty working tree as real work to preserve, not as disposable generated content.
2. Resolve the intake/identity/source-rights decisions, then land schema/parser/policy
   foundations with MT regression tests. Prepare source packages outside raw.
3. Import a small Greek gold fixture and approved dictionary extracts into staging. Prove
   activation failure safety, exact identity and entry rendering before full-Psalter work.
4. Import approved full packages, build the catalog, and evaluate annotation/versification
   gaps. Do not copy seed text or substitute another edition to close a missing field.
5. Publish a read-only preview on the mounted route, finish expert sample review, then
   enable Release A. Keep existing MT projects and English renderings unchanged.
6. Review the cross-alignment gold set and enable Release B only after accepted-set policy,
   coverage and provenance pass. Report outstanding proposed/unresolved links.
7. Tag software and data packages, generate study exports and dependency notices, and retain
   active/previous descriptors and source snapshots. Rehearse rollback and independent
   offline reconstruction before release reviewer sign-off.

The earlier recovery audit lists 297 proposed renderings with no cached anchor evidence.
Carry that inventory forward; the Greek feature must not assign them a new source edition
or invent anchors. Do not change existing canonical text, approvals, IDs or alignment meaning
through a background importer. Any later canonical repair follows the review service.

## 12 Plan review and readiness

The associated [adversarial review](GREEK_LEXICAL_ADVERSARIAL_REVIEW.md) will record the
reviewed candidate hash, reviewer findings, dispositions and residual implementation gates.
Resolve critical design contradictions before calling the plan ready for implementation.
Open owner/source/Greek-expert gates remain explicit dependencies; a sound plan does not
pretend those approvals or future acceptance tests have already happened.
