# Greek lexical and reference integration implementation plan

Date: 2026-10-17. Status: adversarial review completed; implementation gates remain explicit. This is an implementation
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
in Greek should read “absent from the MT 150-psalm corpus”; broader textual history is
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
content/lexemes/grc/<lexeme_set_revision>/lexemes.jsonl
content/lexemes/grc/<lexeme_set_revision>/crosswalks.jsonl
content/mt/source_snapshots/<mt_snapshot_id>/source_tokens.jsonl
content/versification/lxx/<edition>/<text_revision>/map.json
content/cross_alignments/mt_lxx/<edition>/<text_revision>/<set_id>.json
content/source_registry.json
content/audit/packages/<package_id>.jsonl
```

These are normalized canonical packages and authored annotations, not mutable raw inputs.
Derive indexes and backlink lists from them; avoid copying cross-alignment IDs into every
MT unit merely to support navigation. Each package has a deterministic manifest and schema
version. Imports are staged and validated before a single study snapshot makes them active
together with a compatible catalog, lexical packages, annotations and maps. Package
installation alone does not activate a source revision for readers.

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

Lexeme and crosswalk packages are immutable revisioned dependencies of annotation sets.
A homograph split or merge creates replacement lexeme identities and an explicit mapping;
it never changes what a retained lexeme ID meant to an old analysis. New crosswalk meanings
receive a new set revision. Re-evaluate affected analyses and approvals before activating
the replacement set; retain the old graph for old cards, bridges and exports.

Represent lexical expressions separately from physical source tokens. An expression
occurrence references ordered token spans and may have component relationships. For example,
`εἰ μή` can match a G1508 expression over two tokens; `κἀγώ` can match one G2504 occurrence
with component links, without creating additional printed καί/ἐγώ tokens. The source word
count never changes because a lexical expression has multiple components. Do not expand
dictionary relationship edges into corpus occurrences without an explicit occurrence analysis.

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
Compute specialist eligibility from each stable reviewer's latest applicable decision,
without satisfying new requirements through cached historic approval counts. A withdrawal,
rejection or request for changes revokes that reviewer's earlier approval even when the
payload hash has not changed. Keep a target with unresolved requested changes ineligible;
require a later explicit approval of the applicable target to clear it. Changes invalidate
the affected decision's applicability while retaining its history. Canonical English changes still require two
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

Imports read immutable packages, normalize into staging, create required audits, and validate
all schemas/references. Stage both the canonical manifest and its compatible catalog before
publishing the study snapshot described below. A retry
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
destructive rebuild. Put generation jobs and UI state in an explicitly durable local database,
proposed as `data/local/workbench_state.sqlite3`, excluded from Git and from index cleanup.
Migrate the old mixed database under an exclusive workspace migration lock with API/job
writers quiesced: back it up, copy operational tables transactionally, verify rows and keys,
record an idempotent migration marker, switch connection routing, then resume writers.
An interrupted cutover resumes from its marker or restores the original routing; retain the
original database until verification succeeds. Concurrent job writes cannot race a table copy.

Build immutable catalog files containing MT and approved Greek indexes. Update all lexical/
search readers and summary-cache builders to use catalog connections; jobs and UI state use
operational connections. W2 defines the MT source-snapshot contract and W4 retains the
initial source-only snapshot; W9 consumes it without changing MT IDs. Publish one
**study snapshot descriptor** binding the canonical
source registry revision, MT source snapshot, Greek text revision, lexeme/crosswalk package
revisions, analysis/map/accepted-alignment sets and compatible catalog hash.

Build and publish protocol:

1. Bind a validated candidate canonical manifest and all dependency revisions, plus the
   expected current study-snapshot hash. Installed immutable files are not yet active.
2. Build a new database under a staging name; create indexes and run SQLite integrity,
   foreign-key, uniqueness, row-count and representative query checks.
3. Close writers and seal the catalog. Under a short publication lock, compare the expected
   predecessor hash and recheck current permissions. A stale builder must fail rather than
   overwrite a newer publication. Atomically replace the single study-snapshot descriptor;
   a reader resolves canonical data and catalog through the same descriptor.
4. Tag caches and cursors with that revision. Retain the last catalog and every catalog with
   active readers; remove retired files only after handles are closed, including on Windows.
5. On failed build or publish, keep serving the previous complete study snapshot; on startup
   validate the active descriptor and recover the recorded last-good snapshot if necessary.
   Never recover source permissions from an old descriptor.

Every read also checks the **current** capability policy, including reads of retained
snapshots. Include its revision in response/cache validity and invalidate cached views when
permissions change. A revoked source cannot reappear through an old cursor, cached card or
rollback; return a typed source-unavailable result. Source-policy changes have their own
serialized audited publication, and the study-snapshot selection never grants permission.
Do not claim that already downloaded bytes can be retroactively erased from a user's device.

Proposed indexes: Greek units/tokens, analysis candidates/selections, lexemes, dictionary
entries, typed external-ID assignments, verse-map spans and cross-alignment membership.
Use composite scope keys containing edition/text revision and annotation/index revisions.
Persist canonical entry text in source packages; SQL is a rebuildable query mirror.

Concordance has a typed request: `study_snapshot_id`, `query_kind` (`lexeme_id`, `lemma_text`,
`identifier`, `surface`), value, identifier scheme where relevant, `analysis_scope`
(`reviewed`, `proposed`, `all`), `analysis_selection` (`selected`, `possible`), `match_unit`
(`token`, `expression`) and explicit relationship expansion. Lemma text may match multiple
homographs; a local lexeme query must not merge them. Selected queries use applicable
reviewed selections; possible queries inspect candidates in the requested scope, deduplicating
the same token or expression across competing analyses. The card and every page/count use
the same query predicate and snapshot. Release A exposes possible matches as such, alongside
reviewed counts and unresolved coverage; it never labels a seed count reviewed.

Identifier matching is exact and scheme-specific. G1508 uses an expression query: the fixture
`εἰ μή` has one match, two member tokens and one verse. G2504 on `κἀγώ` has one match and one
member token. Searching for component G2532 does not include the crasis unless component
expansion is explicitly requested and labeled. Return `match_unit`, `total_matches`,
`total_tokens` (distinct physical members), `total_verses`, counts by analysis status and a
coverage statement. Unresolved analyses cannot be silently treated as proven nonmatches.

Surface prefix/substring modes are explicit and optionally mark-insensitive. Unknown fields
return a validation error. Default page size 50, maximum 200. Order token matches by
structured reference/position/token ID and expression matches by first member/occurrence ID.
The cursor binds the complete query predicate and study snapshot; an unavailable old snapshot
yields a typed stale response and restart action. Do not reuse capped reference arrays.

## 8 Services and user interface

### Service contracts and operational interfaces

Implement Greek corpus, lexical, versification, annotation and cross-alignment services.
Routes and CLI/MCP call those services; no client performs direct content writes.

| Interface | Required behavior |
|---|---|
| `GET /lxx/editions` | Approved editions/revisions, availability, provenance and capabilities |
| `GET /lxx/psalms` and `/lxx/units/{id}` | Structured edition references and actual Greek tokens; no joined-hint fallback |
| `GET /greek/tokens/{id}/card` | Source identity, analyses, IDs, dictionary summaries, scoped counts, provenance, review state and study snapshot |
| `GET /greek/lexicon/entries/{entry_id}` | Attributed sanitized entry and typed internal/external references |
| `GET /greek/lexicon/identifiers` | Exact scheme/value lookup; zero/one/multiple results are explicit |
| `GET /greek/concordance` | Typed match/analysis scope; bounded results with match/token/verse totals, study snapshot and cursor |
| `GET /versification/map` and `/units/{mt_id}/parallel` | Many-to-many, title, absent and Greek-only results with labeled references |
| Cross-alignment read/review routes | Explicit active set, status filtering, endpoint validation and atomic replacement |
| `GET /greek/correspondences/distribution` | Accepted-set correspondence-group distributions with declared counting unit and denominator |

Every new route gets an MCP tool or a reasoned `EXCLUDED` entry, checked by the existing
coverage test. Add CLI intake dry-run/apply, validate Greek packages, build/check catalog,
inspect gaps, seed cross-alignments and export a study bundle. Mutations stamp their actual
actor and write audits. Read-only tools must not imply acceptance or canonical promotion.

### Mounted study flow

Extend `ComparisonPage`, `AppContext` and the active comparison table with MT/LXX/Parallel
selection and edition/revision selection. Group navigation can select multiple MT/LXX
members; preserve existing translations rather than moving or merging them. Keep source
navigation (`edition/revision/psalm/unit`) independent of the selected project's translation
membership. A concordance hit outside that project, including an empty project, opens the
source reader with an explicit “no English translation in this project” state; it does not
create, move or select a different project's translation. Psalm 151 is
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

Dictionary citations retain their original label, machine reference, source entry and
declared numbering baseline, which may be English/KJV rather than MT or LXX. Resolve through
that baseline's edition-aware map, including title offsets; a `Psa` attribute is not enough
to choose a corpus. TBESG `Psa.45.15`/`Ps 44(45):15` and `Psa.51.6` are required fixtures
against Swete 44:16 and 50:8 respectively. If a citation's baseline or target is uncertain,
show it as unresolved/external rather than linking to a plausible but different verse.

Cache keys include the study snapshot, current policy revision, token/query and translation
context when English is included. A card returns its study snapshot and the client must pass
it on dependent dictionary, occurrence and bridge requests, including the first occurrence
page. Serve that snapshot or return stale/unavailable and restart the complete view; never
mix old-card counts with new pages. Switching project/edition cannot retain another project's
English snippet. Reject stale asynchronous responses after selection changes.

Greek words work by keyboard and touch, not hover alone. Enter/Space opens the persistent
card; Escape closes overlays and returns focus. Definitions, references, filters and
occurrence navigation are keyboard reachable. Announce loading/errors, preserve controls
at 200% zoom and 430px width, and show attribution on the card and exported entry.

### Reviewed Hebrew bridge

A cross-alignment set references immutable MT and Greek snapshots. Before W9, capture a
retained **MT source snapshot** keyed by a content hash of Hebrew unit/token IDs, source forms,
segmentation and source provenance. Keep its source tokens separate from mutable English,
notes and project metadata; MT IDs and live paths remain unchanged. Hebrew endpoints are
`(mt_snapshot_id, token_id)`. Any Hebrew source correction creates a new snapshot; keep old
bridge evidence on the old snapshot and require explicit mapping/review before activation
against the new one. Rows support many-to-many
groups, explicit Greek plus/Hebrew minus, transposition and uncertainty. Reject both-empty
rows, nonexistent tokens, wrong revisions and overlapping active accepted ownership.
Exactly-one coverage applies within a declared accepted set when it is marked aligned;
proposed alternative analyses do not violate accepted-set uniqueness.

Seeds enter proposed. Counts and distributions default to accepted evidence, with separate
proposed/unresolved totals. A Greek-plus claim requires an explicit reviewed observation;
absence of a link means unresolved. A new accepted set atomically supersedes the old one;
old approvals and exports remain attributable to the set they used. Store hypotheses about
a Hebrew Vorlage separately from observed links. Do not reuse English-span coverage code.

W9 also owns distributions. Count each accepted alignment group once for a requested
source lexeme, using its opposite-side lexeme **multiset/signature** as the outcome; do not
invent a Cartesian product of Hebrew and Greek token pairs. Report alignment-group count,
distinct token counts, the accepted-set coverage denominator and separate plus/minus and
unresolved totals. Repeated source lexemes within one group contribute one group observation
and their actual token count separately. A pairwise statistic is a different explicitly
named future query. Test known many-to-many groups and replacement sets with exact totals.

## 9 Work packages and dependency order

Each row is a reviewable change set; split schema/parser/service work further if a diff
cannot be assessed independently. Source-data review runs alongside software work.

| Package | Owner role and files | Depends on | Exit condition |
|---|---|---|---|
| W0 decisions and source lock | Owner, schema owners, Greek reviewer; requirements, data-source policy, lock/evidence | — | Section 3 choices resolved for the next slice; source permissions and intake procedure are explicit |
| W1 capability and audit foundation | Backend; registry, license rules, audit service, manifest/audit schemas, input consumers | W0 | Effective component permissions enforced; global package mutations auditable; no raw writes/config resets |
| W2 identity and Greek contracts | Backend/schema owners; IDs, config, registry, schemas, validator, remaining positional parsers | W0 | MT round trips unchanged; simultaneous edition/revision IDs route and validate; Greek units require Greek fields |
| W3 immutable Greek import and maps | Data/backend; new intake/import/versification services, scripts/CLI | W1 W2 and approved package; W4 for activation | All 151 psalms accounted for, titles/135:23/151 handled; staging is idempotent and joint activation/rollback passes with W4 |
| W4 catalog lifecycle | Backend; durable-state migration, DB connection separation, rebuild, readers, summary caches | W1 W2 | Quiesced migration and single-snapshot publication/CAS survive faults; MT/Greek counts, jobs and UI state remain correct |
| W5 dictionary adapters | Data/backend; TBESG, both TFLSJ, Abbott-Smith, optional direct LSJ, crosswalk schemas | W1 W2; approved per-source permissions | Every input row accounted for; typed relationships, attribution and safe rendering fixtures pass |
| W6 morphology and lexeme analysis | Greek/data reviewers; QuantForge adapter, normalizer, analysis-set schema/review service | W2 W3 W5 | Every token has status; ambiguity/gaps retained; stratified accuracy review published with seed errors exposed |
| W7 lexical APIs and concordance | Backend; lexical services, catalog queries, routes, MCP/CLI contracts | W3 W4 W5 W6 | Exact ID lookup and complete bounded occurrence traversal pass; no seed status hidden |
| W8 mounted Greek word study | UI/backend; active page/context/table/card/hooks/styles, service DTOs | W7; basic source reader can start after W3 | End-to-end word journey passes keyboard, offline, project-switch and source-attribution checks |
| W9 accepted Hebrew Greek bridge | Greek/alignment reviewers, backend/UI; MT source snapshots, cross contract/service/review/view/distributions | W1 W2 W3 W6 W8 | Gold set reviewed; snapshot-bound coverage, group-count distributions and specialist roles enforced; proposals separate |
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
| Identity/storage | MT and two Greek editions with identical verse labels never collide; source/lexeme/crosswalk revisions preserve old anchors and reviews; capture MT source snapshot and edit live Hebrew source without changing the old bridge; every new ID round-trips; reject ambiguous locators |
| Greek schemas | Greek data cannot satisfy Hebrew-only fields accidentally; unexpected fields and malformed IDs fail; analysis gap and ambiguity are valid explicit states; old MT fixtures remain valid |
| Source policy | Disabled/unconfirmed Greek component absent from all model inputs; revoke permission after a cached card/cursor, then attempt retained-catalog access and rollback without recovering permission; blocked display/export leaks no text/snippets/counts; permitted lexical glosses remain distinct from translation witnesses |
| Intake/migration | Dry run has zero writes; apply audits every canonical mutation; second apply is a no-op; checksum reuse fails; malformed package, disk-full and interrupted activation preserve prior content/config; snapshot all raw files before/after and require byte identity |
| Source text/map | LXX 1, merged 9, joined 113, split 114–115, 147 split, 151, titles and cross-psalm Hallelujah; Swete 135:23 absent; 137:6 has two witness spans; overlapping generic title mappings do not lose links |
| Unicode/lexical IDs | NFC/NFD idempotence, sigma variants, breathings/accents, elision, iota handling, preserved diplomatic spelling; Latin/Cyrillic findings; G3107/bare 3107 source normalization, G6908, G2264G/H/I, G21502, Hebrew cross-reference, multi-ID expression, absent and malformed IDs |
| Dictionary parsers | BOM/preamble, repeated eStrong, both TFLSJ files, typed relationships, references with declared numbering/title offsets (TBESG G0020/G0082), malformed rows, TEI namespaces/P4 entities and Beta Code; XXE, scripts, events and unsafe links never execute |
| Morphology | QuantForge MorphGNT-to-feature conversion preserves raw tags and unknowns; ὁδῷ is not accepted as masculine by default; synthetic proper-noun fallbacks remain proposed/unresolved; token-count mismatch cannot be handled by ordinal zip |
| Concordance | 1,003 matching tokens paginate without omissions/duplicates; homographs and competing analyses share exactly the card's scope predicate; unresolved coverage visible; G1 differs from G10; G1508 expression has 1 match/2 tokens, G2504 has 1/1, component expansion opt-in; stale first-page and cursor requests explicit |
| Index failure safety | Operational-state cutover quiesces writers and recovers interrupted migration; jobs/card state survive; a fault between canonical staging and study-snapshot publication leaves old queries coherent; competing builders cannot regress the active snapshot; live Windows readers complete safely |
| Review/bridge | Distinct specialists and hashes required; no historic-count bypass; approve then request_changes/withdraw on the same hash revokes eligibility; invalid endpoints rejected; accepted-set distributions have exact group/token denominators for many-to-many, repeats and plus/minus; replacement/edits require applicable approval |
| API/MCP/CLI | Identical service outcomes for all interfaces; actors stamped; coverage test for every route; Greek import/index/diagnostics reproduce offline without authentication or model calls |
| Mounted UI | Source switch/word/entry/occurrences/bridge/reverse navigation; empty and one-psalm projects open outside-project hits and Ps151 without creating translations; MT9+10 survive LXX9 navigation; publish a new snapshot between card and first page without mixed counts; async/accessibility/error states covered |
| Export/rollback | Validate full provenance closure including entries/annotations/maps/audits; block restricted content at all nested locations; preserve old published revisions; disabling Greek availability restores MT navigation without deleting either corpus |

Targeted code locations include `tests/support.py`, new Greek contract/normalization/parser/
concordance/import/review tests, `tests/integration/test_mcp_server.py`, active comparison API
tests and current-route Playwright scenarios. The root `npm test` currently runs Python and
goldens; it is not evidence of a configured React unit runner. Add an explicit UI unit setup
only where it adds value; use current-route browser tests with mocked local data regardless.
Remove the full raw-tree-copy dependency from lean Greek fixtures before making them a
routine fast check; use unique temporary roots for concurrent test processes.

Quality gates distinguish parsing, coverage and accuracy. Require 100% input-row accounting,
zero broken references and zero unexplained dropped source words. Before Release A, every
source word is clickable and indexed, and proposed pilot targets require plausible candidate
lemma/occurrence analyses for ≥95% of all physical tokens and at least one permitted entry
link for ≥95% of tokens and ≥90% of distinct resolved lexemes. Measure and publish the full
denominators, unresolved counts and proposed/reviewed fractions; unresolved tokens remain
in the surface concordance. A small accurate subset cannot satisfy these coverage gates.

Review at least 600 independently selected token occurrences, sampled proportionally across
Psalter books/parts of speech, plus a separately reported adversarial set of names, elision,
rare forms and known seed failures. Two qualified Greek readers establish reference labels
and retain ambiguity/adjudication outcomes. Proposed targets are ≥99% lemma accuracy and
≥97% parsed-feature accuracy on expert-unambiguous sampled cases, with abstentions and
unresolved sample coverage reported separately. If strata are oversampled, weight estimates
to the declared population; do not apply an unweighted pooled interval to that design.
Publish exact numerators/denominators, sampling design, ambiguity and interval method.
Targets are not measured results or a guarantee about every token. Revise them explicitly
after the pilot rather than forcing a wrong analysis to meet a completeness percentage.

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

The associated [adversarial review](GREEK_LEXICAL_ADVERSARIAL_REVIEW.md) records the
reviewed candidate hashes and all twelve findings, corrections and second-pass dispositions.
All three reviewers closed their findings at the design level; no remaining P1 contradiction
was reported within their scopes. Open owner/source/Greek-expert gates remain implementation
dependencies. The plan does not count those approvals or future acceptance tests as complete.
