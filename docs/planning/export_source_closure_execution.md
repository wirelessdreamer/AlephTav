# Export source closure hardening

Date: 2026-10-17. Scope: existing legacy book/release exports and the unexposed
Greek `prepare_bundle` helper. No production source or content was changed.

## Legacy exports

`export_service` now treats current effective source/component export capabilities as
authoritative. A project manifest's historical `allowed_for_export` flag cannot restore
revoked LXX permissions. The Hebrew export requires its existing UXLC source permission;
permitted Hebrew/English output remains available when unrelated Greek sources are blocked.

Nested source claims are checked before including renderings or witnesses. The legacy
format cannot establish Greek snapshot or source-package closure, so Greek-derived
renderings, unversioned Greek anchors and unscoped nested package inputs are excluded.
Allowed rendering output is a bounded projection; arbitrary cached inputs, notes and
extra nested provenance fields are omitted. Audit/review free text lacks export provenance
and remains local, with an explicit export-state message rather than a fabricated full
audit trail.

Project-wide reports may contain excluded source text, snapshots or free-form quotes.
The release path still invokes existing release validation, but publishes new report,
notice and inventory projections based on the permitted export payload instead of copying
those local reports. The exported report explicitly states that local audit/concern detail
was omitted and does not claim complete audit reconstruction. Existing destination
directories containing unscoped extra files are rejected; repeated bundle manifests do
not hash their previous copy.

Both public legacy export functions hold the same OS-backed `study-publication.lock`
used by source-policy publication throughout policy capture, filtering, report preparation
and final file serialization. Final policy fingerprints are checked under that lock.
The concurrent test proves policy publication waits while export serialization runs.
This does not claim retroactive erasure of bytes already exported before a later revocation.

## Greek bundle

Root-owned availability logic binds the exact `audit_files` references into the existing
release approval payload. `prepare_bundle` additionally requires:

- Policy capture before opening the active snapshot or release evidence, with checks after
  opening and before any possible return.
- Source and package-hash export permission, normalized package roots, exact manifest/file
  hashes and sizes, actual license bytes and exact dependency-hash closure.
- Audit references shaped exactly as `{path, sha256, package_id}`, limited to
  `content/audit/packages/*.json`. Strict AuditRecord validation, package entity identity,
  matching manifest `after_hash`, audit namespace/filename and complete package coverage
  are mandatory. Raw, arbitrary workspace and unrelated audit files cannot be included.
- Nested canonical source/catalog validation through `load_view`, unchanged complete
  availability-record hash, current policy and applicable release evidence at the end.

The helper then fails closed with an explicit independent-reconstruction gate. It returns
no bundle bytes, remains unexposed, and accepts no invented reconstruction pass report.
Implementing and independently verifying reconstruction remains required future work.

## Validation and handoff

```text
.venv/Scripts/python.exe -m pytest tests/unit/test_export_source_closure.py tests/unit/test_greek_bundle_closure.py tests/unit/test_greek_study_export.py -q
21 passed; 4 existing jsonschema RefResolver deprecation warnings

python -m ruff check app/services/export_service.py app/services/greek_study_export_service.py tests/unit/test_export_source_closure.py tests/unit/test_greek_bundle_closure.py
All checks passed

.venv/Scripts/python.exe -m mypy app/services/export_service.py app/services/greek_study_export_service.py --follow-imports=silent
Success: no issues found in 2 source files
```

An initial existing release integration run had two failures before export serialization.
Investigation established a coordinated fixture regression: bootstrap no longer rewrites
raw manifests, while copied fixture manifests retained vendored hashes and project metadata
still used fixture hashes. Root corrected the isolated test fixture reset without changing
production raw or release gates and reported a fresh `test_review_and_export.py` run with
**7/7 passing**. The shared fixture fix belongs to root's workstream.

Changed in this slice:

- `app/services/export_service.py`
- `app/services/greek_study_export_service.py` (`prepare_bundle` only; root owns availability)
- `tests/unit/test_export_source_closure.py`
- `tests/unit/test_greek_bundle_closure.py`
- `docs/planning/export_source_closure_execution.md`

Fixtures are authored and temporary. No new export route was exposed, no approval or
source availability was created, no raw/canonical production content was changed, and
no commit or push was performed.

## Follow-up project-license error regression

The full-suite recheck found that changing a project source's export flag no longer
changed its raw manifest, so the raw-only license audit missed that forbidden request
and later reported a generic manifest mismatch. `_ensure_exportable` now evaluates
both current project manifests and the immutable raw-license audit with the existing
`evaluate_manifest` policy. A forbidden project request gets the precise license-policy
error before release validation. Effective capabilities remain the final permission
authority; the project flag grants no permission and no raw file is changed.

A lean regression and the affected API test were run with related export checks:

```text
.venv/Scripts/python.exe -m pytest tests/integration/test_api_mutations.py::test_release_export_endpoint_blocks_forbidden_source_licenses tests/integration/test_review_and_export.py tests/unit/test_export_source_closure.py tests/unit/test_greek_bundle_closure.py tests/unit/test_greek_study_export.py -q
30 passed; 4 existing jsonschema RefResolver deprecation warnings

python -m ruff check app/services/export_service.py tests/unit/test_export_source_closure.py
All checks passed

.venv/Scripts/python.exe -m mypy app/services/export_service.py --follow-imports=silent
Success: no issues found in 1 source file
```
