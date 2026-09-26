from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import raise_as_http
from app.services import arrangement_service as arrangements
from app.services import codex_app_server_service as codex
from app.services import codex_arrangement_service as drafting

router = APIRouter(tags=["arrangements"])

BASE = "/psalms/{psalm_id}/arrangements"


@router.get(BASE)
def list_arrangements(psalm_id: str, translation_id: str | None = Query(default=None)) -> dict:
    """A translation's song settings, newest last, with the refrains its Hebrew repeats."""
    try:
        return {
            "psalm_id": psalm_id,
            "arrangements": arrangements.list_arrangements(psalm_id, translation_id or None),
            "refrains": arrangements.detect_refrains(psalm_id),
            "required_approvals": arrangements.required_approvals(),
        }
    except Exception as error:
        raise_as_http(error)


@router.post(BASE)
def create_arrangement(psalm_id: str, payload: dict) -> dict:
    try:
        return arrangements.create_arrangement(
            psalm_id,
            layer=payload.get("layer", "lyric"),
            title=payload.get("title", "Song setting"),
            created_by=payload.get("created_by", "reviewer"),
            sections=payload.get("sections"),
            translation_id=payload.get("translation_id") or None,
        )
    except Exception as error:
        raise_as_http(error)


@router.get(BASE + "/{arrangement_id}")
def get_arrangement(psalm_id: str, arrangement_id: str) -> dict:
    try:
        return arrangements.arrangement_view(psalm_id, arrangement_id)
    except Exception as error:
        raise_as_http(error)


@router.patch(BASE + "/{arrangement_id}")
def update_arrangement(psalm_id: str, arrangement_id: str, payload: dict) -> dict:
    try:
        return arrangements.update_arrangement(
            psalm_id,
            arrangement_id,
            created_by=payload.get("created_by", "reviewer"),
            title=payload.get("title"),
            status=payload.get("status"),
        )
    except Exception as error:
        raise_as_http(error)


@router.post(BASE + "/{arrangement_id}/sections")
def add_section(psalm_id: str, arrangement_id: str, payload: dict) -> dict:
    try:
        return arrangements.add_section(
            psalm_id,
            arrangement_id,
            kind=payload.get("kind", "verse"),
            label=str(payload.get("label", "")),
            created_by=payload.get("created_by", "reviewer"),
            repeat_of=payload.get("repeat_of"),
            index=payload.get("index"),
        )
    except Exception as error:
        raise_as_http(error)


@router.patch(BASE + "/{arrangement_id}/sections/{section_id}")
def update_section(psalm_id: str, arrangement_id: str, section_id: str, payload: dict) -> dict:
    try:
        return arrangements.update_section(
            psalm_id,
            arrangement_id,
            section_id,
            created_by=payload.get("created_by", "reviewer"),
            kind=payload.get("kind"),
            label=payload.get("label"),
            index=payload.get("index"),
        )
    except Exception as error:
        raise_as_http(error)


@router.delete(BASE + "/{arrangement_id}/sections/{section_id}")
def remove_section(psalm_id: str, arrangement_id: str, section_id: str) -> dict:
    try:
        return arrangements.remove_section(
            psalm_id, arrangement_id, section_id, created_by="reviewer"
        )
    except Exception as error:
        raise_as_http(error)


@router.post(BASE + "/{arrangement_id}/sections/{section_id}/lines")
def add_line(psalm_id: str, arrangement_id: str, section_id: str, payload: dict) -> dict:
    try:
        return arrangements.add_line(
            psalm_id,
            arrangement_id,
            section_id,
            text=str(payload.get("text", "")),
            created_by=payload.get("created_by", "reviewer"),
            anchors=payload.get("anchors"),
            liberty=payload.get("liberty", "tracks"),
            rationale=str(payload.get("rationale", "")),
            index=payload.get("index"),
        )
    except Exception as error:
        raise_as_http(error)


@router.patch(BASE + "/{arrangement_id}/lines/{line_id}")
def update_line(psalm_id: str, arrangement_id: str, line_id: str, payload: dict) -> dict:
    try:
        return arrangements.update_line(
            psalm_id,
            arrangement_id,
            line_id,
            created_by=payload.get("created_by", "reviewer"),
            text=payload.get("text"),
            anchors=payload.get("anchors"),
            liberty=payload.get("liberty"),
            rationale=payload.get("rationale"),
            index=payload.get("index"),
        )
    except Exception as error:
        raise_as_http(error)


@router.delete(BASE + "/{arrangement_id}/lines/{line_id}")
def remove_line(psalm_id: str, arrangement_id: str, line_id: str) -> dict:
    try:
        return arrangements.remove_line(psalm_id, arrangement_id, line_id, created_by="reviewer")
    except Exception as error:
        raise_as_http(error)


@router.post(BASE + "/{arrangement_id}/lines/{line_id}/approvals")
def approve_line(psalm_id: str, arrangement_id: str, line_id: str, payload: dict) -> dict:
    try:
        return arrangements.approve_line(
            psalm_id,
            arrangement_id,
            line_id,
            reviewer=str(payload.get("reviewer", "")),
            reviewer_role=str(payload.get("reviewer_role", "")),
            note=str(payload.get("note", "")),
        )
    except Exception as error:
        raise_as_http(error)


@router.post(BASE + "/{arrangement_id}/omissions/approvals")
def approve_omission(psalm_id: str, arrangement_id: str, payload: dict) -> dict:
    try:
        return arrangements.approve_omission(
            psalm_id,
            arrangement_id,
            unit_id=str(payload.get("unit_id", "")),
            token_ids=list(payload.get("token_ids", [])),
            reviewer=str(payload.get("reviewer", "")),
            reviewer_role=str(payload.get("reviewer_role", "")),
            rationale=str(payload.get("rationale", "")),
            note=str(payload.get("note", "")),
        )
    except Exception as error:
        raise_as_http(error)


@router.post("/codex/psalms/{psalm_id}/arrangements/import")
def arrange_import(psalm_id: str, payload: dict) -> dict:
    """Analyse a pasted translation as a song setting, its lines kept as pasted."""
    try:
        return drafting.arrange_import(
            codex.require_client(),
            session_id=payload["session_id"],
            psalm_id=psalm_id,
            text=str(payload.get("text", "")),
            layer=payload.get("layer", "lyric"),
            created_by=payload.get("created_by", "import"),
        )
    except Exception as error:
        raise_as_http(error)


@router.post("/codex/psalms/{psalm_id}/arrangements/draft")
def draft_arrangement(psalm_id: str, payload: dict) -> dict:
    """Draft a whole-psalm song setting with Codex, stored as a proposal."""
    try:
        return drafting.draft_arrangement(
            codex.require_client(),
            session_id=payload["session_id"],
            psalm_id=psalm_id,
            layer=payload.get("layer", "lyric"),
            created_by=payload.get("created_by", "codex"),
        )
    except Exception as error:
        raise_as_http(error)
