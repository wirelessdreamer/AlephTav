from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import raise_as_http
from app.services import source_translation_map_service

router = APIRouter(tags=["source map"])


@router.get("/psalms/{psalm_id}/source-map")
def get_source_translation_map(
    psalm_id: str,
    layer: str = Query(default="literal"),
    translation_source: str = Query(default="saved"),
    rendering_status: str = Query(default="preferred"),
    witness_source_id: str | None = Query(default=None),
) -> dict:
    try:
        return source_translation_map_service.get_source_translation_map(
            psalm_id=psalm_id,
            layer=layer,
            translation_source=translation_source,
            rendering_status=rendering_status,
            witness_source_id=witness_source_id,
        )
    except Exception as error:  # pragma: no cover
        raise_as_http(error)
