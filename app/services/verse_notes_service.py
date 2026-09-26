"""A reviewer's notes on a verse, and the rebuilds made with them.

Notes are instructions to the translator ("make it clear the teaching is
Yahweh's") or comments. A rebuild retranslates the verse with its open
instructions; its renderings are saved as ``proposed`` but held back as a
*pending* rebuild, so the table keeps showing the current text until the
reviewer accepts or discards it. The blind audit of the rebuilt text is held on
the rebuild record too, and only becomes the verse's assessment on accept.

Every change here writes an AuditRecord on the unit.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.core.errors import NotFoundError, ValidationError
from app.services import audit_service, registry_service
from app.services import psalm_translations_service as translations

APPLIES_TO = ("literal", "english", "both")
KINDS = ("instruction", "comment")
NOTE_OPEN = "open"
NOTE_ADDRESSED = "addressed"

REBUILD_PENDING = "pending"
REBUILD_ACCEPTED = "accepted"
REBUILD_DISCARDED = "discarded"

#: Statuses a proposed rendering outranks when the table picks what to show.
REPLACEABLE = ("proposed", "draft")


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _next_id(prefix: str, unit_id: str, existing: list[str]) -> str:
    return f"{prefix}.{unit_id}.{len(existing) + 1:04d}"


def _mutate(
    unit_id: str,
    mutator: Any,
    summary: str,
    rationale: str,
    created_by: str,
    entity_type: str,
    entity_id: str | None = None,
) -> Any:
    """Apply ``mutator`` to the unit and audit the change. Returns the mutator's result."""
    unit = registry_service.load_unit(unit_id)
    before_hash = registry_service.file_hash(unit)
    result = mutator(unit)
    audit_service.create_audit_record(
        unit,
        before_hash=before_hash,
        after_hash=registry_service.file_hash(unit),
        summary=summary,
        rationale=rationale,
        created_by=created_by,
        entity_type=entity_type,
        entity_id=entity_id or (result or {}).get("note_id") or (result or {}).get("rebuild_id"),
    )
    registry_service.save_unit(unit)
    return result


# -- Notes -----------------------------------------------------------------


def _find_note(unit: dict[str, Any], note_id: str) -> dict[str, Any]:
    for note in unit.get("verse_notes", []):
        if note["note_id"] == note_id:
            return note
    raise NotFoundError(f"Verse note not found: {note_id}")


def _check_fields(applies_to: str | None, kind: str | None) -> None:
    if applies_to is not None and applies_to not in APPLIES_TO:
        raise ValidationError(f"applies_to must be one of {', '.join(APPLIES_TO)}")
    if kind is not None and kind not in KINDS:
        raise ValidationError(f"kind must be one of {', '.join(KINDS)}")


def add_note(
    unit_id: str,
    text: str,
    applies_to: str = "english",
    kind: str = "instruction",
    quote: str | None = None,
    token_ids: list[str] | None = None,
    created_by: str = "reviewer",
    translation_id: str | None = None,
) -> dict[str, Any]:
    cleaned = text.strip()
    if not cleaned:
        raise ValidationError("A note needs some text")
    _check_fields(applies_to, kind)
    translations.require(unit_id.split(".")[0], translation_id)

    def add(unit: dict[str, Any]) -> dict[str, Any]:
        notes = unit.setdefault("verse_notes", [])
        note: dict[str, Any] = {
            "note_id": _next_id("vn", unit_id, [n["note_id"] for n in notes]),
            "text": cleaned,
            "applies_to": applies_to,
            "kind": kind,
            "status": NOTE_OPEN,
            "created_at": _now(),
            "created_by": created_by,
        }
        if quote and quote.strip():
            note["quote"] = quote.strip()
        if token_ids:
            known = {token["token_id"] for token in unit.get("tokens", [])}
            unknown = [t for t in token_ids if t not in known]
            if unknown:
                raise ValidationError(f"Tokens not in {unit_id}: {unknown}")
            note["token_ids"] = list(token_ids)
        translations.tag(note, translation_id)
        notes.append(note)
        return note

    return _mutate(unit_id, add, "Add verse note", cleaned, created_by, "verse_note")


def update_note(
    unit_id: str,
    note_id: str,
    created_by: str = "reviewer",
    text: str | None = None,
    applies_to: str | None = None,
    kind: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    _check_fields(applies_to, kind)
    if status is not None and status not in (NOTE_OPEN, NOTE_ADDRESSED):
        raise ValidationError(f"status must be {NOTE_OPEN} or {NOTE_ADDRESSED}")
    if text is not None and not text.strip():
        raise ValidationError("A note needs some text")

    def update(unit: dict[str, Any]) -> dict[str, Any]:
        note = _find_note(unit, note_id)
        for key, value in (
            ("text", text.strip() if text is not None else None),
            ("applies_to", applies_to),
            ("kind", kind),
            ("status", status),
        ):
            if value is not None:
                note[key] = value
        note["updated_at"] = _now()
        return note

    return _mutate(
        unit_id, update, "Update verse note", f"edited {note_id}", created_by, "verse_note", note_id
    )


def remove_note(unit_id: str, note_id: str, created_by: str = "reviewer") -> dict[str, Any]:
    def remove(unit: dict[str, Any]) -> dict[str, Any]:
        note = _find_note(unit, note_id)
        unit["verse_notes"] = [n for n in unit["verse_notes"] if n["note_id"] != note_id]
        return note

    return _mutate(unit_id, remove, "Remove verse note", note_id, created_by, "verse_note", note_id)


def open_instructions(
    unit: dict[str, Any], layer_key: str, translation_id: str | None = None
) -> list[dict[str, Any]]:
    """The translation's open instruction notes for ``layer_key`` ("literal" or "english")."""
    return [
        note
        for note in unit.get("verse_notes", [])
        if note["kind"] == "instruction"
        and note["status"] == NOTE_OPEN
        and note["applies_to"] in (layer_key, "both")
        and translations.in_translation(note, translation_id)
    ]


# -- Rebuilds ----------------------------------------------------------------


def pending_rebuild(
    unit: dict[str, Any], translation_id: str | None = None
) -> dict[str, Any] | None:
    """The translation's rebuild of this verse awaiting a decision; one at a time."""
    for rebuild in unit.get("rebuilds", []):
        if rebuild["status"] == REBUILD_PENDING and translations.in_translation(
            rebuild, translation_id
        ):
            return rebuild
    return None


def rebuild_view(unit: dict[str, Any], rebuild: dict[str, Any] | None) -> dict[str, Any] | None:
    """A rebuild with the before and after text of each layer it touched."""
    if rebuild is None:
        return None
    by_id = {r["rendering_id"]: r for r in unit.get("renderings", [])}
    texts = {}
    for layer, rendering_id in rebuild["rendering_ids"].items():
        previous_id = rebuild["previous_rendering_ids"].get(layer)
        previous = by_id.get(previous_id or "")
        texts[layer] = {
            "previous": previous["text"] if previous else None,
            "rebuilt": by_id[rendering_id]["text"] if rendering_id in by_id else None,
            # A proposed rebuild only replaces text that is itself unreviewed; a
            # canonical or accepted rendering stays until review promotes the new one.
            "replaces_current": previous is None or previous["status"] in REPLACEABLE,
        }
    return {**rebuild, "texts": texts}


def verse_history(unit_id: str) -> dict[str, Any]:
    """Everything that happened to a verse, newest first, plus each rebuild's diff."""
    unit = registry_service.load_unit(unit_id)
    events = [
        {
            key: record.get(key)
            for key in (
                "audit_id",
                "created_at",
                "created_by",
                "summary",
                "rationale",
                "entity_type",
                "entity_id",
            )
        }
        for record in unit.get("audit_records", [])
    ]
    events.sort(key=lambda event: event["created_at"] or "", reverse=True)
    return {
        "unit_id": unit_id,
        "events": events,
        "rebuilds": [rebuild_view(unit, r) for r in reversed(unit.get("rebuilds", []))],
        "notes": unit.get("verse_notes", []),
    }


def pending_rendering_ids(unit: dict[str, Any]) -> set[str]:
    """Renderings a pending rebuild holds back from the table and the auditor.

    Every translation's pending rebuilds count: a held literal is shared by them all.
    """
    return {
        rendering_id
        for rebuild in unit.get("rebuilds", [])
        if rebuild["status"] == REBUILD_PENDING
        for rendering_id in rebuild["rendering_ids"].values()
    }


def record_rebuild(
    unit_id: str,
    english_layer: str,
    note_ids: list[str],
    rendering_ids: dict[str, str],
    previous_rendering_ids: dict[str, str | None],
    note_responses: list[dict[str, str]],
    run_ids: list[str],
    created_by: str,
    translation_id: str | None = None,
) -> dict[str, Any]:
    def add(unit: dict[str, Any]) -> dict[str, Any]:
        if pending_rebuild(unit, translation_id) is not None:
            raise ValidationError("This verse already has a rebuild waiting for a decision")
        rebuilds = unit.setdefault("rebuilds", [])
        rebuild = {
            "rebuild_id": _next_id("rb", unit_id, [r["rebuild_id"] for r in rebuilds]),
            "status": REBUILD_PENDING,
            "english_layer": english_layer,
            "note_ids": note_ids,
            "rendering_ids": rendering_ids,
            "previous_rendering_ids": previous_rendering_ids,
            "note_responses": note_responses,
            "run_ids": run_ids,
            "analysis": None,
            "created_at": _now(),
            "created_by": created_by,
        }
        translations.tag(rebuild, translation_id)
        rebuilds.append(rebuild)
        return rebuild

    return _mutate(
        unit_id,
        add,
        "Rebuild verse with notes",
        f"rebuilt {', '.join(rendering_ids)} with {len(note_ids)} note(s)",
        created_by,
        "rebuild",
    )


def store_rebuild_analysis(
    unit_id: str, rebuild_id: str, analysis: dict[str, Any], created_by: str
) -> dict[str, Any]:
    def store(unit: dict[str, Any]) -> dict[str, Any]:
        rebuild = _find_rebuild(unit, rebuild_id)
        if rebuild["status"] != REBUILD_PENDING:
            raise ValidationError(f"Rebuild {rebuild_id} is already {rebuild['status']}")
        rebuild["analysis"] = analysis
        return rebuild

    return _mutate(
        unit_id,
        store,
        "Analyse rebuilt verse",
        "blind audit of the rebuilt text, held until the rebuild is decided",
        created_by,
        "rebuild",
        rebuild_id,
    )


def _find_rebuild(unit: dict[str, Any], rebuild_id: str) -> dict[str, Any]:
    for rebuild in unit.get("rebuilds", []):
        if rebuild["rebuild_id"] == rebuild_id:
            return rebuild
    raise NotFoundError(f"Rebuild not found: {rebuild_id}")


def accept_rebuild(
    unit_id: str,
    rebuild_id: str,
    addressed_note_ids: list[str] | None = None,
    created_by: str = "reviewer",
) -> dict[str, Any]:
    """Show the rebuilt text, adopt its analysis, and close the notes it addressed."""
    from app.services import codex_analysis_service

    unit = registry_service.load_unit(unit_id)
    rebuild = _find_rebuild(unit, rebuild_id)
    if rebuild["status"] != REBUILD_PENDING:
        raise ValidationError(f"Rebuild {rebuild_id} is already {rebuild['status']}")
    addressed = set(addressed_note_ids or [])
    unknown = addressed - set(rebuild["note_ids"])
    if unknown:
        raise ValidationError(f"Notes not part of this rebuild: {sorted(unknown)}")

    def accept(unit: dict[str, Any]) -> dict[str, Any]:
        rebuild = _find_rebuild(unit, rebuild_id)
        rebuild["status"] = REBUILD_ACCEPTED
        rebuild["decided_at"] = _now()
        rebuild["decided_by"] = created_by
        for note in unit.get("verse_notes", []):
            if note["note_id"] in addressed:
                note["status"] = NOTE_ADDRESSED
                note["addressed_in"] = rebuild_id
                note["updated_at"] = rebuild["decided_at"]
        return rebuild

    accepted = _mutate(
        unit_id,
        accept,
        "Accept rebuilt verse",
        f"{len(addressed)} of {len(rebuild['note_ids'])} note(s) marked addressed",
        created_by,
        "rebuild",
        rebuild_id,
    )
    if accepted.get("analysis"):
        # The held audit was of exactly the text now shown, so it becomes the verdict.
        codex_analysis_service.adopt_rebuild_analysis(unit_id, accepted)
    return accepted


def discard_rebuild(unit_id: str, rebuild_id: str, created_by: str = "reviewer") -> dict[str, Any]:
    """Keep the current text; the rebuilt renderings are rejected, the notes stay open."""
    from app.services import rendering_service

    unit = registry_service.load_unit(unit_id)
    rebuild = _find_rebuild(unit, rebuild_id)
    if rebuild["status"] != REBUILD_PENDING:
        raise ValidationError(f"Rebuild {rebuild_id} is already {rebuild['status']}")

    def discard(unit: dict[str, Any]) -> dict[str, Any]:
        rebuild = _find_rebuild(unit, rebuild_id)
        rebuild["status"] = REBUILD_DISCARDED
        rebuild["decided_at"] = _now()
        rebuild["decided_by"] = created_by
        return rebuild

    discarded = _mutate(
        unit_id,
        discard,
        "Discard rebuilt verse",
        "current text kept",
        created_by,
        "rebuild",
        rebuild_id,
    )
    for rendering_id in discarded["rendering_ids"].values():
        rendering_service.update_rendering(
            rendering_id,
            {"status": "rejected", "rationale": f"discarded with {rebuild_id}"},
            created_by=created_by,
        )
    return discarded
