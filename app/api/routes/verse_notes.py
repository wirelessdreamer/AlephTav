from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import raise_as_http
from app.services import codex_translation_service as translation
from app.services import verse_notes_service

router = APIRouter(tags=["verse-notes"])


@router.post("/units/{unit_id}/verse-notes")
def add_verse_note(unit_id: str, payload: dict) -> dict:
    try:
        return verse_notes_service.add_note(
            unit_id,
            text=str(payload.get("text", "")),
            applies_to=payload.get("applies_to", "english"),
            kind=payload.get("kind", "instruction"),
            quote=payload.get("quote"),
            token_ids=payload.get("token_ids"),
            created_by=payload.get("created_by", "reviewer"),
            translation_id=payload.get("translation_id") or None,
        )
    except Exception as error:
        raise_as_http(error)


@router.patch("/units/{unit_id}/verse-notes/{note_id}")
def update_verse_note(unit_id: str, note_id: str, payload: dict) -> dict:
    try:
        return verse_notes_service.update_note(
            unit_id,
            note_id,
            created_by=payload.get("created_by", "reviewer"),
            text=payload.get("text"),
            applies_to=payload.get("applies_to"),
            kind=payload.get("kind"),
            status=payload.get("status"),
        )
    except Exception as error:
        raise_as_http(error)


@router.delete("/units/{unit_id}/verse-notes/{note_id}")
def remove_verse_note(unit_id: str, note_id: str) -> dict:
    try:
        return verse_notes_service.remove_note(unit_id, note_id)
    except Exception as error:
        raise_as_http(error)


@router.post("/units/{unit_id}/rebuilds/{rebuild_id}/accept")
def accept_rebuild(unit_id: str, rebuild_id: str, payload: dict) -> dict:
    try:
        return verse_notes_service.accept_rebuild(
            unit_id,
            rebuild_id,
            addressed_note_ids=payload.get("addressed_note_ids"),
            created_by=payload.get("created_by", "reviewer"),
        )
    except Exception as error:
        raise_as_http(error)


@router.post("/units/{unit_id}/rebuilds/{rebuild_id}/discard")
def discard_rebuild(unit_id: str, rebuild_id: str, payload: dict | None = None) -> dict:
    try:
        return verse_notes_service.discard_rebuild(
            unit_id, rebuild_id, created_by=(payload or {}).get("created_by", "reviewer")
        )
    except Exception as error:
        raise_as_http(error)


@router.get("/units/{unit_id}/verse-history")
def get_verse_history(unit_id: str) -> dict:
    try:
        return verse_notes_service.verse_history(unit_id)
    except Exception as error:
        raise_as_http(error)


@router.get("/units/{unit_id}/word-suggestions")
def get_word_suggestions(
    unit_id: str,
    token_ids: str = Query(...),
    layer: str = Query(default="lyric"),
    translation_id: str | None = Query(default=None),
) -> dict:
    """Suggestions already generated for this word, if any; generating needs Codex."""
    try:
        ids = [token_id for token_id in token_ids.split(",") if token_id]
        cached = translation.cached_suggestions(unit_id, ids, layer, translation_id or None)
        return cached or {"unit_id": unit_id, "token_ids": ids, "layer": layer, "suggestions": []}
    except Exception as error:
        raise_as_http(error)
