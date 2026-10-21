# Greek data implementation execution record

Date: 2026-10-17. Work packages: W3, W5, W6. This records implemented offline
software slices and executed tests. It is not a source, license, owner, schema-owner,
Greek-specialist, or release approval. Nothing was imported into production or activated.

## Status

| Package | Implemented | Still required before its plan exit condition |
|---|---|---|
| W3 immutable Greek import/maps | Strict manifest/file/license closure inspection, zero-write dry run, normalized Greek unit/token/span validation, complete-Psalter psalm coverage check, atomic/idempotent candidate staging, source-gated audited inactive installation through foundation service, normalized map/witness-span validation | Approved immutable full Swete release; source-specific export-to-normalized adapter once that release format is fixed; actual all-word/verse/title accounting; documentary edition exception and witness-span map; TVTMS/Copenhagen candidate adapters and edition cross-check; schema-owner acceptance; activation/rollback through foundation snapshot publication |
| W5 dictionary adapters | TBESG and both TFLSJ eight-field adapters, BOM/preamble/row accounting, repeated eStrong records, separate e/d/uStrong identities and typed combination/crasis edges, namespaced Abbott-Smith TEI including entries without G-number, constrained safe presentation trees, baseline-bound citation resolution, deterministic normalized dictionary bytes and parser report, strict entry schema | Approved source-specific lineage/permissions and actual pinned artifact ingestion/count reconciliation; source-specific translation of bibliographic/custom references beyond the implemented STEP/TEI references; actual edition-aware citation map; optional direct LSJ P4/Beta Code adapter intentionally omitted |
| W6 morphology/lexemes | Separate source spelling/search normalization, foreign-script findings, nine-field QuantForge parser and raw MorphGNT features/unknowns, explicit verse/surface span matching including split/joined forms, multiple candidates and unresolved tokens, proposed-only output, immutable lexical graph references and explicit split/merge predecessors, physical expression counts with opt-in component expansion | Approved text/dictionary dependencies; measured full-corpus candidate/dictionary coverage; qualified independent Greek sample labels/adjudication and accuracy report; specialist selection/review workflow. No generated candidate is accepted automatically |

The full W3/W5/W6 plan exit conditions remain open. Tiny authored fixtures do not
establish full-Psalter coverage, transcription quality, dictionary coverage or expert accuracy.

## Interfaces

`app/services/greek_package_intake_service.py`:

- `inspect_package(package_root, require_full_psalter=True)` reads only and returns manifest,
  compatible canonical manifest hash, normalized units/maps/entries and a dry-run summary.
  Every physical file must be locked; a locked file must contain the declared license text.
- `stage_package(package_root, staging_root, require_full_psalter=True)` stages outside both
  repository/configured canonical content and raw roots. Reusing a revision with changed
  bytes fails; a retry with the same bytes is a no-op. Staging does not grant approvals.
- `install_staged_greek_package(staged_dir, created_by, rationale, ...)` requires package
  review status and current display permission, then uses foundation
  `package_install_service.install_staged_package` for auditing and inactive installation.
  Foundation's source package-hash allowlist and study publication remain the activation gate.
- `validate_greek_units` validates foundation IDs/contracts and exact Python-codepoint spans,
  requires all letters/marks/numbers to be token-accounted, preserves spelling/NFC, rejects
  fabricated Swete 135:23 and can require all 151 psalms explicitly.
- `validate_versification_map` retains explicit baseline/reference endpoints, many-to-many
  titles, Greek-only/MT-only/edition-absent rows, aliases, subverse and witness spans. It does
  not manufacture an edition map from a generic map or infer an absence from a missing link.

`app/services/greek_dictionary_service.py`:

- `parse_step_dictionary`, `parse_tflsj`, `parse_abbott_smith` return `AdapterResult` with
  entries, complete parser accounting, findings and version. `require_valid()` rejects any
  invalid row/entry; normalization cannot silently import the remaining valid subset.
- Entry IDs contain immutable package identity and source locator; external schemes/values
  remain separate from local lexeme IDs. Source labels and raw relationship expressions stay
  available as provenance. No dictionary relationship creates a corpus occurrence.
- `safe_presentation` returns a constrained tree, citations and findings. Unsupported markup
  is inert text; event attributes and unsafe links never become executable attributes/links.
  TEI DTD/entity declarations are refused before parsing; no network resolution is used.
- `resolve_citation` requires exact numbering baseline, machine reference, target edition and
  revision; uncertain or multiple mappings stay unresolved. Authored G0020/G0082 fixtures
  exercise English/KJV references against Swete 44:16 and 50:8 without assigning them by label.
- `normalized_dictionary_files` validates every entry and returns deterministic
  `entries.jsonl` and `adapter_report.json` bytes. Callers must lock these plus actual license
  bytes and dependency manifests before staging or audited installation.

`app/services/greek_analysis_service.py`:

- `normalize_greek` creates derived keys independently of immutable source forms. Optional
  mark/elision normalization is explicit; case folding retains iota distinctions.
- `parse_quantforge` retains all nine columns, raw tags, source rows, synthetic method and
  unknown features. It supplies no Strong identifiers and no reviewed selections.
- `propose_analyses` requires an explicit source-reference-to-versioned-unit map. It compares
  normalized contiguous source spans, supports split/join proposals, retains ambiguous repeat
  candidates and gives every token an annotation status. It never ordinal-zips corpora.
- `validate_lexical_graph` checks authored lexeme/source-entry crosswalk endpoints and retained
  replacement IDs while allowing repeated external IDs and homographs with distinct local IDs.
- `expression_matches` counts explicit physical members; G1508 is one match/two tokens and
  G2504 is one/one. Component expansion is off by default. The W7 API owns snapshot-bound
  query scope, pagination and current permission checks.

Foundation DTOs are used unchanged: edition/revision-qualified source unit IDs, 1-based token
positions, `surface`, NFC `normalized`, `text_span`, file/locator/fragments. Separate proposed
analysis sets include `analyses`, status and null `selected_analysis_id`. Dictionary entry
attribution carries source/revision/license/license-text hash/required attribution. The
application agent received these contracts; root owns CLI/API/MCP registration.

## Changed files

- `app/services/greek_package_intake_service.py`
- `app/services/greek_dictionary_service.py`
- `app/services/greek_analysis_service.py`
- `schemas/greek_dictionary_entry.schema.json`
- `schemas/greek_analysis_set.schema.json`
- `schemas/greek_versification_map.schema.json`
- `schemas/greek_lexeme_set.schema.json`
- `schemas/greek_crosswalk_set.schema.json`
- `tests/unit/test_greek_data_adapters.py`
- `docs/planning/greek_data_execution.md`

All are new files owned by this workstream. Existing dirty work was preserved. No raw,
canonical English, protected license/policy/CODEOWNERS, shared routing or production index
files were changed by this workstream. No commit or push was performed.

## Executed validation

Fixtures are authored inline format examples and definitions, not upstream extracts. Tests
are marked `no_seeded_repo`, run with unique temporary workspace roots and require no source
download, production import, model or authentication. Upstream documentary headers were
inspected in memory to verify STEP and Abbott-Smith column/attribute layouts; no source
package was downloaded to disk or installed.

Commands and results:

```text
.venv/Scripts/python.exe -m pytest tests/unit/test_greek_data_adapters.py -q
50 passed; 4 existing jsonschema RefResolver deprecation warnings

python -m ruff check app/services/greek_analysis_service.py app/services/greek_dictionary_service.py app/services/greek_package_intake_service.py tests/unit/test_greek_data_adapters.py
All checks passed

.venv/Scripts/python.exe -m mypy app/services/greek_analysis_service.py app/services/greek_dictionary_service.py app/services/greek_package_intake_service.py --follow-imports=silent
Success: no issues found in 3 source files
```

Coverage includes BOM/preamble/eight fields, malformed-row accounting, both TFLSJ files,
repeated eStrong/suffix/extended IDs, TEI namespaces and missing IDs, DTD/XXE rejection,
script/event/javascript inertness, citation baselines/title offsets, NFC/NFD/sigma/iota/elision
and foreign-script findings, synthetic and erroneous morphology staying proposed, mismatched
token ordering, split/join/repeat ambiguity, local homographs and predecessor references,
expression cardinality, strict schema rejection of invented selections, checksum revision
reuse and unaccounted-file rejection, zero-write dry run, raw/canonical staging rejection,
pending/self-declared approval denial, full license attribution closure, and disk-full
failure preservation of the prior candidate.

Primary format references:

- [STEP pinned source documentation](https://github.com/STEPBible/STEPBible-Data/tree/94802ced31e63882ab42a86d79eb0017df4545e3)
- [QuantForge pinned Psalter format](https://github.com/QuantForgeSoftware/lxx/blob/46258f8bde173998ef0633d79eff3067b9041575/data/morph-morpheus/024-Ps.txt)
- [Abbott-Smith pinned TEI](https://github.com/translatable-exegetical-tools/Abbott-Smith/blob/8c00cb244761aa23659421a8cbbbf7a3b27b7d59/abbott-smith.tei.xml)
- [MorphGNT feature documentation](https://github.com/morphgnt/sblgnt)
