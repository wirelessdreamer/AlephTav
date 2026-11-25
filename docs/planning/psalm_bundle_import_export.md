# Single-psalm export and import (design)

Date: 2026-11-21. Status: design, not implemented.

## Problem

A translation of one psalm (for example "Bone and Ash", Psalm 23, in project
`col.0001`) can only leave a workbench today through git, by copying the
whole `content/` tree. A workbench that is not shared through git (another
machine, a collaborator's local install, a scratch workspace) has no clean
way to send or receive one psalm's translation.

`export_book(psalm_id)` already exists, but it publishes release text. It
cannot be imported back and it drops everything that is not publishable.

## What moves

The unit of export is **one translation of one psalm**: what
`psalm_translations_service` says a translation owns. The Hebrew, gloss and
literal are shared by every translation and already exist in the receiving
workbench, so they are not copied. A fingerprint of them is carried instead.

| Record | Lives in | Selected by |
|---|---|---|
| Translation (title, guidance, `created_via`) | `psNNN.meta.json` → `translations[]` (main: meta root) | `translation_id` |
| Project title and text license | `content/collections.json` | translation's `collection_id` |
| English renderings (above `literal`) | unit → `renderings[]` | `in_translation` |
| Alignments owned by those renderings | unit → `alignments[]` | the rendering's `alignment_ids` |
| Verse assessments | unit → `comparison_assessments[]` | `in_translation` |
| Verse notes and rebuilds | unit → `verse_notes[]`, `rebuilds[]` | `in_translation` |
| Psalm analyses | meta → `analyses[]` | `in_translation` |
| Song settings | meta → `arrangements[]` | `in_translation` |
| Guidance and briefing history, translation choices | unit audit records, `entity_type: translation_context` | `translation_id` in the snapshot |
| Audit history of all of the above | unit → `audit_records[]` | `entity_id` in the exported set |

Not exported: the Hebrew, tokens, witnesses, gloss and literal renderings,
other translations' records, derived caches, and Codex sessions.

## Bundle format

One JSON file, `ps023.bone-and-ash.psalm.json`, validated by a new
`schemas/psalm_bundle.schema.json`:

```json
{
  "format": "alephtav.psalm-translation",
  "format_version": 1,
  "exported_at": "…",
  "exported_by": "reviewer",
  "source": {
    "psalm_id": "ps023",
    "translation_id": "tr.ps023.0001",
    "project": { "title": "Bone and Ash", "output_text_license": "CC0 1.0" },
    "workbench_project_id": "proj.main"
  },
  "hebrew_fingerprint": {
    "ps023.v001.a": "<sha256 of source_hebrew + token ids/surfaces>",
    "…": "…"
  },
  "translation": { "title": "…", "guidance": "…", "created_via": "human" },
  "units": {
    "ps023.v001.a": {
      "renderings": [], "alignments": [], "comparison_assessments": [],
      "verse_notes": [], "rebuilds": []
    }
  },
  "analyses": [],
  "arrangements": [],
  "context_history": [],
  "audit_history": [],
  "content_sha256": "<sha256 of everything above>"
}
```

Records are copied as stored, with their original ids. Import rewrites the
ids (below), so export stays a plain read.

## Import

`import_psalm_bundle(bundle, collection_id, title=None, created_by)`:

1. **Check.** The schema and `content_sha256` match. `format_version` is
   known. The psalm exists here. Every unit's Hebrew fingerprint matches the
   local unit. A mismatch refuses the import, naming the verses, because
   alignments point at token ids. The target project has no translation of
   the psalm yet (the existing one-per-project rule).
2. **Create the translation** with `psalm_translations_service.create_translation(...,
   created_via="import")`. The bundle's main translation also becomes an added
   translation here, because the receiving psalm already has its own main one.
3. **Reissue ids.** Every id is local and sequential (`tr.`, `rnd.`, `aln.`,
   `cmp.`, `anl.`, `arr.`, note and rebuild ids, `aud.`). Allocate fresh ids
   with the `app/core/ids.py` helpers and rewrite every reference through one
   old→new map: `alignment_ids`, `english_rendering_id`, `revision_of`,
   rebuild `rendering_ids` and `note_ids`, `addressed_in`, and `translation_id`
   on every record. Each record's `audit_ids` is replaced by the import audit
   from step 5. Arrangement lines anchor to token ids, which match once the
   Hebrew fingerprint does, so only the arrangement's own ids change. A reference to a shared record that is not in the bundle
   (`literal_rendering_id`) is re-pointed at the local canonical literal for
   that unit, or cleared with a note if there is none.
4. **Reset review state.** Approvals from another workbench were not logged by
   this one's review service, so they do not count here:
   - every imported rendering comes in as `proposed`, with a fresh
     `review_signoff`, and is never canonical;
   - the original status and approvers are kept read-only under
     `provenance.imported_from`.
   This follows the canonical rule in `docs/REVIEW_POLICY.md` and the reason
   `translation_transfer_service` refuses to move canonical renderings.
5. **Write audits.** Every touched unit gets one `AuditRecord`
   (`change_type: "import"`, rationale naming the bundle's `content_sha256`,
   source translation and export time). Guidance and briefing history are
   replayed through `translation_context_service.append`. The bundle's own
   audit history is not written into `audit_records` (its ids would collide
   and its hashes describe another file). It is kept whole, once, on the new
   translation as `imported_from.audit_history`.
6. **All or nothing.** Snapshot the meta and every unit file first, and
   restore them on any failure, as `move_translation_and_replace_bundle`
   does. Then run `validate_content.py` checks on the psalm.

`preview_psalm_bundle(bundle, collection_id)` runs steps 1 and 3 without
writing. It returns counts per record type, the verses with Hebrew
mismatches, the references it will re-point or clear, and whether the
project is free.

## Projects

The importer picks the destination project. The default is a project with
the bundle's project title: reused if it exists and has no translation of the
psalm, created otherwise. The bundle's text license is applied only when the
project is created, never to an existing project.

## Surfaces

| Surface | Export | Import |
|---|---|---|
| Service | `psalm_bundle_service.export_translation(psalm_id, translation_id)` | `preview_bundle`, `import_bundle` |
| CLI | `psalms-workbench export-psalm ps023 --translation tr.ps023.0001 -o file` | `import-psalm file [--project col.0003] [--dry-run]` |
| API | `GET /psalms/{psalm_id}/translations/{tid}/bundle` (download) | `POST /psalms/import-bundle/preview`, `POST /psalms/import-bundle` |
| MCP | `export_psalm_bundle` | `preview_psalm_bundle`, `import_psalm_bundle` (MCP test requires one per route) |
| UI | "Export psalm" in the project's psalm menu | "Import psalm…" in the project picker: file → preview → confirm |

## Out of scope for v1

- Updating an earlier import in place (re-import creates a second
  translation, so it needs a different project). The `content_sha256` on
  `imported_from` makes "already imported" detection possible later.
- Whole-project export (a list of bundles would do).
- Carrying shared literal or gloss edits.

## Tests

- Round trip: export from the fixture workspace, import into a second temp
  workspace, compare text and alignment spans, and check that ids were
  reissued and every reference resolves.
- Refusals: Hebrew mismatch, occupied project, tampered `content_sha256`,
  unknown `format_version`.
- Review reset: a canonical source rendering arrives as `proposed` and the
  local canonical set does not change.
- Audit: every touched unit gains an import audit record and
  `validate_content.py` passes.
- Rollback: a failure injected mid-import leaves every file byte-identical.
