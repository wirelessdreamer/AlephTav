from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import raise_as_http
from app.services import psalm_translations_service as translations

router = APIRouter(tags=["translations"])


@router.get("/psalms/{psalm_id}/translations")
def list_translations(psalm_id: str) -> list[dict]:
    """The psalm's translations: its main one (translation_id null) first."""
    try:
        return translations.list_translations(psalm_id)
    except Exception as error:
        raise_as_http(error)


@router.post("/psalms/{psalm_id}/translations")
def create_translation(psalm_id: str, payload: dict) -> dict:
    try:
        return translations.create_translation(
            psalm_id,
            title=str(payload.get("title", "")),
            created_by=payload.get("created_by", "reviewer"),
            created_via=payload.get("created_via", "human"),
        )
    except Exception as error:
        raise_as_http(error)
