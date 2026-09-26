from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import raise_as_http
from app.services import collections_service
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
            collection_id=str(payload.get("collection_id") or ""),
            created_by=payload.get("created_by", "reviewer"),
            created_via=payload.get("created_via", "human"),
        )
    except Exception as error:
        raise_as_http(error)


@router.post("/psalms/{psalm_id}/translations/move")
def move_translation(psalm_id: str, payload: dict) -> dict:
    """Put a translation (translation_id null for the main one) in another project."""
    try:
        return translations.move_translation(
            psalm_id,
            translation_id=payload.get("translation_id"),
            collection_id=str(payload.get("collection_id") or ""),
            created_by=payload.get("created_by", "reviewer"),
        )
    except Exception as error:
        raise_as_http(error)


@router.get("/collections")
def list_collections() -> list[dict]:
    """Every project, the default one first, with the psalms it has a translation of."""
    try:
        return translations.list_collections()
    except Exception as error:
        raise_as_http(error)


@router.post("/collections")
def create_collection(payload: dict) -> dict:
    try:
        return collections_service.create_collection(
            str(payload.get("title", "")),
            created_by=payload.get("created_by", "reviewer"),
        )
    except Exception as error:
        raise_as_http(error)


@router.patch("/collections/{collection_id}")
def rename_collection(collection_id: str, payload: dict) -> dict:
    try:
        return collections_service.rename_collection(collection_id, str(payload.get("title", "")))
    except Exception as error:
        raise_as_http(error)
