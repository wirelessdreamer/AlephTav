# Intentional translation choices

A translator can deliberately choose wording while supporting context remains
unestablished. Record the choice and the uncertainty together. A statement of
intent belongs in the translation's durable audit history, independently of
accuracy assessments, source declarations and review approvals.

## Recording a choice

Open **History** for a verse, or **Liberties** for an arrangement. Expand
**Intentional translation choices**, then:

1. Select the exact rendering or arrangement lines. Select several lines when
   the choice depends on their relationship.
2. Describe the intentional choice and its reason. If the original reason is
   unknown, say **Original reason was not recorded**.
3. Choose **Supporting context not established** or **Context supplied by
   translator**, and write a context note. Name what remains unknown rather than
   supplying an inferred explanation. Supplied context is recorded as the
   translator's statement, without a claim of source verification.
4. Enter who is recording the statement and save it.

The server records the current date, an audit ID, the selected wording, declared
source anchors and an authored-target revision. For arrangements it also captures
the complete written/performed context, including neighboring lines, section
order, repeats, declared liberties and omissions. That context preserves why a
choice concerns the beginning or ending of a song.

The recording date describes when the explanation was saved. It does not recover
the original decision date or establish who originally authored the choice.
Recorder names follow the existing local attribution model; MCP actors are
stamped `mcp:<name>`. This operation does not authenticate a human reviewer.

## Footnotes on the lyric sheet

The arrangement's **Text** view links intentional alternatives to numbered context
footnotes. For Psalm 88, these clarify the original Hebrew and the recorded,
proposed/unreviewed literal comparison, and state that the alternative wording is
intentional. A choice covering several lines shares one footnote; sung repetitions
reuse its number. **Copy text with footnotes** includes the same explanations.

Only current entries that have not been superseded are attached to the live lyric
sheet. Applicability is checked again after arrangement edits; copying waits until
the notes have been checked. Historical annotations retain their own footnotes
beside their archived wording in the choice history.

## History and corrections

Entries are append-only through the supported workflow. **Append a correction**
creates a new entry linked to the earlier audit ID; both remain visible. A
correction must concern the same target identities in the same translation.

Each read compares the stored target revision with the current authored content.
History identifies current, changed or missing targets. A stale submission is
refused before an entry is appended. Selections retain their exact revision across
background refreshes. Refresh the targets, compare the wording and explicitly use
the current wording or reselect the target before submitting again. Changing an
approval, status, cached assessment, metric
or generation telemetry does not change this authored-target fingerprint.

The revision is SHA-256 over compact, key-sorted UTF-8 JSON, prefixed by
`alephtav:intentional-choice:authored-target:v1` followed by a NUL byte. The
allowlisted projection is implemented in
[`translation_choices_service.py`](../app/services/translation_choices_service.py).
It binds exact text, membership and declared semantic context, with a separate
version from the R3 review-evidence digest. Recording intent works even when
source context is unavailable or an R3 review digest cannot be calculated.

Choices are version-1 structured snapshots in the existing
`translation_context` audit carrier, with `kind: intentional_choice`. Every entry
uses the mandatory `AuditRecord` contract; no audit, alignment or unit schema is
changed. Audit-only saves read the persisted anchor unit to preserve content that
normal readers may enrich in memory. Existing audit records remain an unchanged
prefix, and translation text, approvals, assessments and flags remain intact.

Recording intent contributes no approval count, source permission, concern
resolution or publication eligibility. The service returns
`counts_for_publication: false`. These records do not become generation guidance
or briefing answers. They survive deletion of derived caches and remain local
under the existing export policy for unscoped audit history.

The existing trusted-local write/concurrency model still applies. This feature
does not claim cross-process transactional serialization with other content
writers; the shared mutation work in R6 remains separate.

## Bone and Ash, Psalm 88

The inspected stored translation is `tr.ps088.0001`, arrangement
`arr.ps088.0001`, titled **God of my salvation**. Likely targets for the example
discussed are:

| Place | Arrangement line | Stored wording |
| --- | --- | --- |
| Opening | `ln.0002` | that’s what I’ve called you |
| Closing | `ln.0049` | darkness… |
| Closing | `ln.0050` | my closest friend. |

The opening addition occurs in the arrangement, so a verse-rendering-only entry
would miss it. The closing choice can bind both lines together. The source uses
MT numbering: stored `ps088.v002.a` and `ps088.v019.a` correspond to displayed
English Psalm 88:1 and 88:18; the MT heading occupies verse 1.

Existing import/analysis explanations identify departures, but do not establish
the translators' original reasoning. At the user's direction, two entries now
record the stated reason **“creative liberties intentionally taken”**:

- `aud.ps088.v001.a.0004`: the opening addition, `ln.0002`.
- `aud.ps088.v001.a.0005`: the closing pair, `ln.0049` and `ln.0050`.

Both declare `context_status: not_established`. The recorder is
`codex:user-reported-intent`; the timestamps record the current logging operation.
No historical author/date or additional literary, linguistic or theological reason
was inferred. These records append to the existing first-unit audit carrier,
leaving wording and approvals intact.

Follow-up annotations `aud.ps088.v001.a.0006` and `aud.ps088.v001.a.0007` link to
those earlier entries. They preserve the original Hebrew and the locally stored
literal backbone, explicitly labeled proposed/unreviewed comparison context,
alongside the intentional alternative wording. Supporting historical or
interpretive context for the creative liberty remains unestablished. The original
entries remain inspectable.

## CLI and API

With the project virtual environment active, inspect the arrangement's targets,
revision values and existing history:

```powershell
python -m app.cli list-translation-choices ps088 --translation-id tr.ps088.0001 --arrangement-id arr.ps088.0001
```

`record-translation-choice` accepts the psalm ID and required options
`--target-kind`, `--target-id`, `--expected-revision`, `--decision`, `--rationale`,
`--context-note` and `--created-by`. For an arrangement line also supply
`--arrangement-id`. Repeat `--target-id` and `--expected-revision` in corresponding
order to group lines. Optional `--supersedes-audit-id` appends a correction;
`--context-status` defaults to `not_established`. CLI JSON output is ASCII-safe
for Windows redirection while retaining exact text when parsed.

HTTP clients use `GET` and `POST`
`/psalms/{psalm_id}/translation-choices`. Reads accept optional `translation_id`,
`unit_id` and `arrangement_id` filters. Writes require between 1 and 20 target
references, each with `kind`, `id`, `expected_revision`, and `arrangement_id` for
arrangement lines. The service supplies snapshots and audit metadata. Unknown
write fields, forged snapshots/authority, stale revisions and foreign targets
are refused. MCP exposes `list_translation_choices` and
`record_translation_choice` through the same shared service.
