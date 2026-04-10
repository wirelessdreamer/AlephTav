from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import raise_as_http
from app.services import rendering_service

router = APIRouter(tags=["renderings"])


@router.get("/units/{unit_id}/renderings")
def get_renderings(
    unit_id: str,
    layer: str | None = Query(default=None),
    style_filter: str | None = Query(default=None),
    release_approved_only: bool = Query(default=False),
) -> list[dict]:
    try:
        return rendering_service.list_renderings(
            unit_id,
            layer=layer,
            style_filter=style_filter,
            release_approved_only=release_approved_only,
        )
    except Exception as error:  # pragma: no cover
        raise_as_http(error)


@router.post("/units/{unit_id}/renderings")
def create_rendering(unit_id: str, payload: dict) -> dict:
    try:
        return rendering_service.create_rendering(
            unit_id=unit_id,
            layer=payload["layer"],
            text=payload["text"],
            status=payload.get("status", "proposed"),
            rationale=payload.get("rationale", "api create rendering"),
            created_by=payload.get("created_by", "api"),
            style_tags=payload.get("style_tags"),
            target_spans=payload.get("target_spans"),
            alignment_ids=payload.get("alignment_ids"),
            drift_flags=payload.get("drift_flags"),
            metrics=payload.get("metrics"),
            provenance=payload.get("provenance"),
            style_goal=payload.get("style_goal"),
            metric_profile=payload.get("metric_profile"),
            issue_links=payload.get("issue_links"),
            pr_links=payload.get("pr_links"),
        )
    except Exception as error:  # pragma: no cover
        raise_as_http(error)


@router.patch("/renderings/{rendering_id}")
def patch_rendering(rendering_id: str, payload: dict) -> dict:
    try:
        return rendering_service.update_rendering(rendering_id, payload)
    except Exception as error:  # pragma: no cover
        raise_as_http(error)


@router.post("/renderings/{rendering_id}/promote")
def promote_rendering(rendering_id: str, payload: dict | None = None) -> dict:
    try:
        request = payload or {}
        return rendering_service.promote_rendering(
            rendering_id,
            reviewer=request.get("reviewer", "api-reviewer"),
            reviewer_role=request.get("reviewer_role", "release reviewer"),
        )
    except Exception as error:  # pragma: no cover
        raise_as_http(error)


@router.post("/renderings/{rendering_id}/demote")
def demote_rendering(rendering_id: str) -> dict:
    try:
        return rendering_service.demote_rendering(rendering_id)
    except Exception as error:  # pragma: no cover
        raise_as_http(error)


@router.get("/units/{unit_id}/renderings/compare")
def compare_renderings(unit_id: str, left_id: str, right_id: str) -> dict:
    try:
        return rendering_service.compare_renderings(unit_id, left_id, right_id)
    except Exception as error:  # pragma: no cover
        raise_as_http(error)
