# Rendering review evidence, version 2

R3 defines stored evidence and a conservative, read-only migration inventory. It
does not authenticate a reviewer or activate the new publication gate. The schema
is a data contract; `principal.kind: "human"` is a claim until the protected review
channel in R4 verifies it. R5 will evaluate current, independent, qualified human
decisions. No R3 classification counts as publication authorization.

## Stored records and compatibility

`unit.review_decisions` accepts exactly one of two disjoint contracts:

- [`review_decision_v1.schema.json`](../schemas/review_decision_v1.schema.json)
  freezes the existing seven-field contract: `decision_id`, `target_id`,
  `reviewer_role`, `reviewer`, `decision`, `notes`, and `timestamp`. Its original
  validation remains unchanged, including historical timestamp strings.
- [`review_decision_v2.schema.json`](../schemas/review_decision_v2.schema.json)
  retains those fields and requires the fields below. Unknown properties are
  rejected, including in the principal and digest objects.

| Field | Contract |
| --- | --- |
| `contract_version` | Integer `2` |
| `principal` | Stable `principal_id` and `kind`, either `human` or `agent` |
| `channel` | `ui`, `api`, `cli`, `mcp`, or `import`; MCP requires agent kind |
| `payload_digest` | Object with `version: 2`, `algorithm: "sha256"`, and lowercase 64-hex `value` |
| `policy_revision` | Lowercase 64-hex fingerprint of applicable policy and source authority |

The decision enum remains `approve`, `accept-alternate`, `reject`,
`request_changes`, or `withdraw`. V2 IDs retain the existing rendering/review ID
patterns and are bounded to 200 characters. Principal IDs contain ASCII letters,
digits, dots, underscores, colons, or hyphens, beginning with a letter or digit,
and are bounded to 200 characters. Reviewer role and display name are nonblank,
bounded to 100 and 200 characters respectively; notes are bounded to 10,000.

V2 timestamps use a calendar-valid RFC 3339 profile: uppercase `T`, seconds,
optional one to nine fractional digits, and `Z` or an explicit numeric offset.
Timezone-free values, impossible dates, leap seconds, whitespace, and invalid
offsets are refused. The dedicated validator uses the standard library for
calendar validation without optional format-checking dependencies. It does not
reinterpret legacy timestamps. Validation errors identify fields and rules and
do not echo review notes or other record values.

These checks cannot establish enrollment, qualifications, independence, authorship,
or the provenance of a timestamp. The authenticated writer must derive identity,
role and channel, assign fresh immutable decision IDs/times, and enforce append-only
history in R4/R5. R3 supplies no v2 decision-write endpoint or migration apply mode.

## Deterministic bindings

[`review_payload_service.py`](../app/services/review_payload_service.py) is the
normative projection implementation. Its named field constants explicitly define
what is bound. Both functions are pure: inputs are dictionaries, no filesystem or
registry reads occur, and inputs are not mutated.

Projection objects are serialized as UTF-8 JSON with sorted object keys, compact
separators, exact Unicode/text values, and non-finite numbers refused. Missing and
present-empty values remain distinct. Semantic array order is preserved; selected
alignments and style profiles are sorted by stable identity. Reviewer role order
is normalized as a set after validating nonempty, unique roles. Missing optional
context is represented explicitly; a fingerprint never certifies that context is
sufficient for publication.

`review_payload_digest(unit, target_id, project)` uses the domain
`alephtav.rendering-review-payload.v2` and binds:

- The exact target text, identity, layer, translation identity, target spans,
  rationale, style references, delivery/metric constraints, variation basis,
  preserved source images, and substantive differentiator.
- Unit source text, source token order and semantic token fields, including
  morphological, lexical, compiler, and enrichment data.
- Translation basis, source anchor, persisted alignment hints, source IDs, and
  selected Greek edition/package/manifest/map/snapshot provenance. Greek source
  attribution is an ordered list of attribution/license pairs.
- Formal alignments attached to the selected rendering's owned spans, including
  source/target endpoints, type, confidence and notes. Duplicate identities,
  ambiguous span ownership and invalid selected endpoints are refused.
- Canonical upstream renderings used by the generation dependency graph, with
  missing dependencies explicit. Lyric layers also bind the literal grounding.
  Ambiguous canonical dependencies are refused.
- Applicable referenced style profiles and the divine-name policy.

`review_policy_revision(unit, target_id, project, source_registry)` uses the
separate domain `alephtav.rendering-review-policy.v2`. It binds the configured
rendering-review thresholds, allowed role set and release role; referenced source
manifest identities, revisions and permissions; and the relevant source-registry
components, capability/status/package information and ordered authority decisions.
It excludes unrelated sources and unrelated registry labels. Malformed configured
policy is refused rather than replaced by permissive defaults. The helper can
represent absent authority context; the migration preview requires the registry
file to assess binding readiness. A matching source-policy fingerprint neither
grants a license nor bypasses current source-permission checks.

Audit events, review decisions, cached signoffs/counts, rendering publication
status, runtime/generation telemetry and unrelated renderings/profiles are excluded.
Changing only those excluded fields does not change the payload digest. Selecting
a different canonical upstream dependency can change it even though a target's own
status is excluded. Source-policy changes affect the policy fingerprint separately.
These hashes do not replace file-integrity or audit hashes, and the mandatory
audit/alignment schemas remain intact. Expanding the semantic projection requires
an explicit contract-version decision and regression coverage.

## Historical evidence and explicit reattestation

Retain every historical record exactly as stored. Never fill in a missing principal,
channel, historical digest or timestamp from today's content or a display name.
An existing cached `review_signoff` is a derived summary, not a review decision.

The pure classifier returns one of:

| Status | Meaning |
| --- | --- |
| `legacy_requires_reattestation` | Valid historical contract; no v2 authority inferred |
| `invalid` | Invalid or unsupported contract |
| `binding_unavailable` | Current digest/policy cannot be supplied and validated |
| `payload_mismatch` | Review payload differs from the supplied current payload |
| `policy_mismatch` | Payload matches but applicable policy differs |
| `binding_current_unverified` | Both bindings match; authenticated human review is unverified |

Every result has `counts_for_publication: false`. Fresh reattestation means a
reviewer actually inspects a frozen candidate and submits a new authenticated
decision with a new ID/time and its current bindings. It never means upgrading
the old record in place. Fixture examples in
[`test_review_evidence_contract.py`](../tests/unit/test_review_evidence_contract.py)
and [`test_review_payload_digest.py`](../tests/unit/test_review_payload_digest.py)
exercise fresh evidence, stale payloads/policies, and changes to text, spans,
alignments, sources and style. Their invented identities are test data only.

During R3, wholly legacy targets retain the existing runtime behavior. Once a
target has any decision with a `contract_version` key, including an unsupported
version, it is held pending activation: legacy decisions and cached counts cannot
contribute authority, legacy review submission cannot downgrade it, and promotion,
release-approved readers, and exports refuse to treat it as approved. This includes
mixed legacy/v2 histories and accepted alternates. History and stored canonical
text/status are preserved. This containment is deliberately separate from the
future global R5 gate; R3 does not claim to secure the remaining legacy human
identity model.

## Read-only migration preview

Run from the source checkout with the project virtual environment active:

```powershell
python -B -m app.cli preview-review-migration --root D:\Code\AlephTav
```

The command emits deterministic JSON to stdout. `--root` overrides
`ALEPHTAV_ROOT_DIR`; absent both, it uses the checkout root. Exit code 0 means the
inventory scan completed, not that records are approved. Exit code 1 accompanies
an incomplete scan with structured diagnostics. There is no `--apply` option.
Shell redirection can save the report when desired; the command creates no report,
cache, content, audit or missing-workspace directories itself.

The version-1 preview envelope includes `target_contract_version: 2`,
`scan_complete`, `summary`, `files`, `records`, and `diagnostics`. Each read file has
its observed SHA-256; records have stable file paths/JSON pointers and safe IDs.
Diagnostics contain stable codes, not record text. Review notes, reviewer display
names, source text and candidate text are not copied into the report. Files are
limited to 16 MiB, duplicate JSON keys and malformed data are diagnosed, and
symlinks/reparse points below the selected workspace are refused.

The scanner reads stored project, source registry, Psalm unit and meta JSON
directly. It does not call bootstrapping or hydrating registry readers. It detects
duplicate decision/target/unit IDs, orphaned and cross-unit targets, invalid or
future contracts, missing binding context, and cached authority claims. Missing
project or source registry files make the scan incomplete; they are never created
or silently substituted. Legacy reattestation requirements alone do not make the
scan incomplete. Cached signoffs are inventoried separately and never synthesized
into decisions. Arrangement line/omission approval counts are informational under
`arrangement_scope`; this rendering contract does not migrate them.

`scan_complete` describes these checks over the observed files. The preview is not
a transactional filesystem snapshot, a complete corpus/schema audit, or a
translation-quality assessment. Run the content validator separately and preserve
the output and underlying candidate/source snapshots before a future human review.
