from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import raise_as_http
from app.services import registry_service, visual_flow_service

router = APIRouter(tags=["psalms"])


@router.get("/psalms")
def list_psalms() -> list[dict]:
    try:
        return [registry_service.load_psalm(psalm_id) for psalm_id in registry_service.list_psalm_ids()]
    except Exception as error:  # pragma: no cover
        raise_as_http(error)


@router.get("/psalms/{psalm_id}/visual-flow")
def get_visual_flow(psalm_id: str) -> dict:
    try:
        return visual_flow_service.get_visual_flow(psalm_id)
    except Exception as error:  # pragma: no cover
        raise_as_http(error)


@router.get("/psalms/{psalm_id}/cloud")
def get_cloud(psalm_id: str, scope: str = Query(default="selected_psalm"), limit: int = Query(default=24, ge=1, le=96)) -> dict:
    try:
        return visual_flow_service.get_cloud(psalm_id=psalm_id, scope=scope, limit=limit)
    except Exception as error:  # pragma: no cover
        raise_as_http(error)


@router.get("/psalms/{psalm_id}/retrieval")
def get_retrieval(
    psalm_id: str,
    node_id: str,
    scope: str = Query(default="selected_psalm"),
    include_cross_psalm: bool = Query(default=True),
    limit: int = Query(default=12, ge=1, le=96),
) -> dict:
    try:
        return visual_flow_service.get_retrieval(
            psalm_id=psalm_id,
            node_id=node_id,
            scope=scope,
            include_cross_psalm=include_cross_psalm,
            limit=limit,
        )
    except Exception as error:  # pragma: no cover
        raise_as_http(error)


@router.get("/psalms/{psalm_id}")
def get_psalm(psalm_id: str) -> dict:
    try:
        return registry_service.load_psalm(psalm_id)
    except Exception as error:  # pragma: no cover
        raise_as_http(error)
