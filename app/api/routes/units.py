from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import raise_as_http
from app.services import (
    alignment_service,
    composer_suggestion_service,
    raw_mutation_policy_service,
    registry_service,
    review_service,
    search_service,
)

router = APIRouter(tags=["units"])


@router.get("/units/{unit_id}")
def get_unit(unit_id: str) -> dict:
    try:
        unit = registry_service.load_unit(unit_id)
        review_service.hydrate_unit_review_state(unit)
        unit["coverage"] = alignment_service.coverage(unit)
        return unit
    except Exception as error:  # pragma: no cover
        raise_as_http(error)


@router.patch("/units/{unit_id}")
def patch_unit(unit_id: str, payload: dict) -> dict:
    try:
        raw_mutation_policy_service.reject_unit_update()
    except Exception as error:  # pragma: no cover
        raise_as_http(error)


@router.get("/units/{unit_id}/witnesses")
def get_unit_witnesses(unit_id: str) -> list[dict]:
    try:
        return search_service.list_witnesses(unit_id)
    except Exception as error:  # pragma: no cover
        raise_as_http(error)


@router.post("/units/{unit_id}/composer-suggestions")
def post_composer_suggestions(unit_id: str, payload: dict) -> dict:
    try:
        return composer_suggestion_service.suggest_for_unit(
            unit_id=unit_id,
            stage=str(payload.get("stage") or ""),
            chunks=list(payload.get("chunks") or []),
            candidate_count=int(payload.get("candidate_count", 3)),
            model_profile=payload.get("model_profile"),
            style_profile=payload.get("style_profile"),
            basis_filter=payload.get("basis_filter"),
        )
    except Exception as error:  # pragma: no cover
        raise_as_http(error)
