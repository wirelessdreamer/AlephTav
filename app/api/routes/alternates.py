from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import raise_as_http
from app.services import rendering_service

router = APIRouter(tags=["alternates"])


@router.get("/units/{unit_id}/alternates")
def list_alternates(unit_id: str) -> list[dict]:
    try:
        return rendering_service.list_renderings(unit_id, alternates_only=True)
    except Exception as error:  # pragma: no cover
        raise_as_http(error)
