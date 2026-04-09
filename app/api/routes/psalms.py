from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import raise_as_http
from app.services import registry_service

router = APIRouter(tags=["psalms"])


@router.get("/psalms")
def list_psalms() -> list[dict]:
    try:
        return [registry_service.load_psalm(psalm_id) for psalm_id in registry_service.list_psalm_ids()]
    except Exception as error:  # pragma: no cover
        raise_as_http(error)


@router.get("/psalms/{psalm_id}")
def get_psalm(psalm_id: str) -> dict:
    try:
        return registry_service.load_psalm(psalm_id)
    except Exception as error:  # pragma: no cover
        raise_as_http(error)
