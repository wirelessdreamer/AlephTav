# R3 review-evidence implementation

Date: 2026-11-05. Scope: the requested versioned rendering-review contract,
conservative migration preview, and regression coverage. This records engineering
work, not translation-quality results or editorial/release approvals. R4/R5
authentication and authoritative eligibility remain separate work.

The normative contract, migration rules and command are in
[Review evidence contract](../REVIEW_EVIDENCE_CONTRACT.md).

## Implemented behavior

- Extracted the original seven-field review contract into a frozen legacy schema
  and added disjoint strict v2/composite schemas. The unit schema references the
  composite. V2 requires bounded principal/channel claims, calendar-valid zoned
  time, a versioned SHA-256 payload digest, and a separate policy fingerprint.
  The mandatory audit and alignment contracts remain unchanged.
- Added pure payload and policy projection functions. Tests cover target text,
  spans, owned alignments, source tokens/edition/map/snapshot, real Greek
  attribution, persisted producer hints, applicable style and canonical upstream
  dependencies. Review/audit/cache/runtime changes do not create circular hashes.
  Malformed policy, ambiguous ownership and unsupported nesting are refused.
- Added non-authoritative evidence classification. Every classification has
  `counts_for_publication: false`. No historical timestamp, identity or digest is
  synthesized, and no historical approval is upgraded in place.
- Held targets with any version-bearing decision pending activation. Mixed or
  future-version history cannot borrow cached or legacy authority, use legacy
  review submission to downgrade, promote, appear in release-approved readers,
  or publish through canonical/accepted-alternate export paths. Existing wholly
  legacy behavior remains intact. Refused exports preserve prior artifacts.
- Added `preview-review-migration --root PATH`: deterministic JSON on stdout,
  explicit completeness/diagnostics and observed file hashes, without apply mode,
  bootstrapping, hydration, cache generation or workspace creation. It diagnoses
  malformed/duplicate/orphan/future evidence and unavailable bindings without
  copying private review/source text into the report. Arrangement approval counts
  are informational and remain outside this rendering migration.
- Extended ID-schema regression coverage to both referenced review contracts.
- Made the composer golden fixture request its raw-source fixture explicitly so
  the documented standalone golden command works without earlier seeded tests.

## Production verification

Commands used the project virtual environment and `-B`; output was captured only
under the ignored `.run/r3-01a1ae05` directory.

```powershell
python -B -m app.cli preview-review-migration --root D:\Code\AlephTav
python -B scripts/validate_content.py
```

The preview exited 0 with `scan_complete: true` and no diagnostics. It observed:

| Stored data | Count |
| --- | ---: |
| Psalm units | 2,527 |
| Psalm metadata files | 150 |
| Renderings / cached summaries | 426 / 426 |
| Review decisions / cached authority claims | 0 / 0 |
| Arrangements | 19 |
| Arrangement line / omission approvals | 0 / 0 |

These are inventory counts, not quality measurements. No approvals were created.
Content validation exited 0: **2,694 files, zero errors**.

The production verification compared the exact file keyset and SHA-256 of all
**2,860 content/raw files**, both mandatory schemas, and 30 existing report files;
all were unchanged. This includes the pre-existing dirty raw manifests. The
preview, validator and tests never perform a production migration. A final
post-test content/raw/schema preservation check is recorded with the test results.

## Regression and static checks

Coverage includes strict v2/frozen v1 validation, actual calendar/offset checks,
private-error redaction, digest sensitivity and exclusions, explicit fresh fixture
evidence, stale policy/payload refusal, mixed-version downgrade containment,
readers/exports, and byte-preserving failures. Preview tests exercise empty/missing
workspaces in fresh subprocesses, determinism, duplicate JSON keys/identities,
orphan/cross-unit targets, missing authority context, nesting failures and Windows
reparse guards. Actual symlink creation is unavailable on this host; synthetic
reparse cases run successfully.

Focused checks passed: 181 ID/contract/payload/boundary tests, 17 boundary/content
validation tests, 73 contract/public-export tests, and 16 preview tests with one
host-dependent skip. These runs overlap; their counts must not be added.

New R3 Python modules/tests pass Ruff lint/format checks. Touched existing files
introduce no new Ruff findings. Repository-wide checks still report inherited
debt: `ruff check .` has 378 findings and `ruff format --check .` identifies 32
files, including existing report-building scripts. `mypy app` reports 70 errors in
21 files, identical to the pre-R3 shadow baseline; scoped checks of the three new
services and CLI pass. No existing check was suppressed to obtain these results.

Final independent runs used the project virtual environment:

```powershell
python -m pytest tests/unit -m "not corpus_audit" -q
python -m pytest tests/integration -m "not corpus_audit" -q
python -m pytest tests/golden -m "not corpus_audit" -q
```

| Suite | Result |
| --- | --- |
| Unit | 822 passed |
| Integration | 149 passed, 1 host-dependent symlink skip |
| Golden | 4 passed, 1 corpus-audit test deselected |
| Total | **975 passed, 1 skipped, 1 deselected** |

The final post-test preservation helper exited 0: all **2,860 content/raw files**
and both mandatory schemas still match the original exact keyset and hashes.
Canonical content and historical approval records were not rewritten. The earlier
production verification separately confirmed the 30 existing reports were unchanged.
Final test logs, preview, validator output and preservation JSON are retained under
the ignored `.run/r3-01a1ae05` directory. `git diff --check` passes.
