from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import raise_as_http
from app.services import registry_service, rendering_service, review_service

router = APIRouter(tags=["alternates"])


@router.get("/units/{unit_id}/alternates")
def list_alternates(
    unit_id: str,
    layer: str | None = Query(default=None),
    style_filter: str | None = Query(default=None),
    release_approved_only: bool = Query(default=False),
) -> list[dict]:
    try:
        return rendering_service.list_renderings(
            unit_id,
            alternates_only=True,
            layer=layer,
            style_filter=style_filter,
            release_approved_only=release_approved_only,
        )
    except Exception as error:  # pragma: no cover
        raise_as_http(error)


@router.post("/units/{unit_id}/alternates")
def create_alternate(unit_id: str, payload: dict) -> dict:
    try:
        return rendering_service.create_rendering(
            unit_id=unit_id,
            layer=payload["layer"],
            text=payload["text"],
            status=payload.get("status", "proposed"),
            rationale=payload.get("rationale", "api add alternate"),
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


@router.post("/alternates/{rendering_id}/accept")
def accept_alternate(rendering_id: str, payload: dict | None = None) -> dict:
    try:
        request = payload or {}
        review_service.add_review_decision(
            target_id=rendering_id,
            decision="accept-alternate",
            reviewer=request.get("reviewer", request.get("created_by", "api-reviewer")),
            reviewer_role=request.get("reviewer_role", "alignment reviewer"),
            notes=request.get("rationale", "accepted alternate"),
        )
        unit = registry_service.load_unit(".".join(rendering_id.split(".")[1:4]))
        return next(item for item in unit.get("renderings", []) if item["rendering_id"] == rendering_id)
    except Exception as error:  # pragma: no cover
        raise_as_http(error)


@router.post("/alternates/{rendering_id}/reject")
def reject_alternate(rendering_id: str, payload: dict | None = None) -> dict:
    try:
        request = payload or {}
        review_service.add_review_decision(
            target_id=rendering_id,
            decision="reject",
            reviewer=request.get("reviewer", request.get("created_by", "api-reviewer")),
            reviewer_role=request.get("reviewer_role", "alignment reviewer"),
            notes=request.get("rationale", "rejected alternate"),
        )
        unit = registry_service.load_unit(".".join(rendering_id.split(".")[1:4]))
        return next(item for item in unit.get("renderings", []) if item["rendering_id"] == rendering_id)
    except Exception as error:  # pragma: no cover
        raise_as_http(error)


@router.post("/alternates/{rendering_id}/deprecate")
def deprecate_alternate(rendering_id: str, payload: dict | None = None) -> dict:
    try:
        request = payload or {}
        return rendering_service.set_alternate_status(
            rendering_id,
            "deprecated",
            rationale=request.get("rationale", "deprecated alternate"),
            created_by=request.get("created_by", "api"),
        )
    except Exception as error:  # pragma: no cover
        raise_as_http(error)


@router.post("/alternates/{rendering_id}/promote")
def promote_alternate(rendering_id: str, payload: dict | None = None) -> dict:
    try:
        request = payload or {}
        return rendering_service.promote_rendering(
            rendering_id,
            reviewer=request.get("reviewer", "api-reviewer"),
            reviewer_role=request.get("reviewer_role", "release reviewer"),
        )
    except Exception as error:  # pragma: no cover
        raise_as_http(error)
