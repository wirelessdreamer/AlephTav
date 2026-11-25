# Intentional translation-choice audit implementation

Date: 2026-11-05. The requested audit workflow records deliberate creative choices
and explicitly unestablished context while preserving translation text and review
requirements. [Translation choices](../TRANSLATION_CHOICES.md) describes the
workflow and storage contract.

## Recorded Psalm 88 choices

At the user's direction, two records were appended for **Bone and Ash**,
translation `tr.ps088.0001`, arrangement `arr.ps088.0001`:

| Record | Targets | Choice |
| --- | --- | --- |
| `aud.ps088.v001.a.0004` | `ln.0002` | Opening addition “that’s what I’ve called you” |
| `aud.ps088.v001.a.0005` | `ln.0049`, `ln.0050` | Closing pair “darkness…” / “my closest friend.” |

Both preserve the user's exact stated reason, **“creative liberties intentionally
taken”**, and declare `context_status: not_established`. The context note records
that supporting context has not been established, as stated by the user. The
recorder is `codex:user-reported-intent`; server timestamps describe this logging
operation. No original author/date, specific literary allusion, source support or
additional rationale was inferred from the earlier import analysis.

The opening addition belongs to the arrangement rather than the verse rendering.
The closing pair is recorded together, with the complete performed context and
declared anchors retained in the immutable snapshots.

## Implemented workflow

- New shared service resolves exact targets and captures versioned authored
  snapshots independently of the R3 review digest or source-context availability.
- Verse **History** and arrangement **Liberties** expose recording and history.
  Required choice, rationale, context limitation and recorder fields permit an
  honest statement that an original reason was not recorded.
- Target revisions remain frozen at selection. A background refresh cannot bind
  an explanation to changed wording. Explicit comparison/acceptance or reselection
  is required to adopt current wording; failed saves retain drafts.
- Corrections append linked records for the same target identities and scope.
  Existing entries survive, including when their targets change or disappear.
- CLI, HTTP and MCP use the same service. MCP attribution is agent-stamped;
  snapshots, audit IDs and recording timestamps are server-owned.
- Existing `translation_context` audit storage carries structured
  `intentional_choice` events. Audit-only writes read the persisted anchor unit,
  avoiding unrelated witness enrichment from ordinary unit readers.
- No content/audit/alignment schema is changed. Entries contribute no review,
  publication or source authority and do not become generation instructions,
  assessment edits or concern resolutions. Existing export policy retains this
  unscoped audit history locally.

## Verification

| Check | Result |
| --- | --- |
| Unit suite | 875 passed |
| Integration suite | 187 passed, 1 host-dependent symlink skip |
| Golden suite | 4 passed, 1 corpus-audit test deselected |
| Python total | **1,066 passed, 1 skipped, 1 deselected** |
| Focused browser regressions | **5 passed** with mocked HTTP and no production API writes |
| UI TypeScript/Vite build | Passed |
| Production content validation after recording | **2,694 files, zero errors** |
| Scoped Ruff lint/format and new-service/adapter type checks | Passed |

Browser coverage includes grouped lines, append-only correction/history,
translation-scope reset, verse-history mounting, failed-save retention, and both
manual and background revision changes. Desktop and phone screenshots were
visually checked, including a phone-width overflow assertion. The browser checks
used a Vite-only server with mocked requests, avoiding the default API bootstrap.

The standard `mypy app` check reports the same **70 errors in 21 files** as the
pre-change baseline; normalized error identities have no additions or removals.
There are no new type errors in the new service, API or CLI/MCP adapters. Existing
repository-wide lint/format debt remains outside this change.

Preservation compares the original exact keyset and SHA-256 values of **2,916
content/raw/schema/report files**. **2,915 files remain byte-identical.** The sole
changed file is `content/psalms/ps088/ps088.v001.a.json`: exactly two valid audit
records and matching IDs were appended. All prior audit records remain identical,
and every non-audit field is unchanged. Translation text, assessments, approvals,
raw sources, all schemas and reports are preserved.

Detailed outputs and the repeatable preservation helper are retained under the
ignored `.run/choices-01a1ae05` directory. The complete integration log is also in
`.run/r3-01a1ae05/translation_choices_integration.log`. `git diff --check` passes.
