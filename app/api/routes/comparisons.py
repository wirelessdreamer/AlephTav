from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import raise_as_http
from app.services import comparison_assessment_service

router = APIRouter(tags=["comparisons"])


@router.get("/psalms/{psalm_id}/comparison-table")
def get_comparison_table(
    psalm_id: str,
    literal_layer: str = Query(default="literal"),
    english_layer: str | None = Query(default=None),
) -> dict:
    try:
        return comparison_assessment_service.build_comparison_table(
            psalm_id,
            literal_layer=literal_layer,
            english_layer=english_layer,
        )
    except Exception as error:  # pragma: no cover
        raise_as_http(error)


@router.get("/psalms/{psalm_id}/comparison-assessments")
def list_comparison_assessments(
    psalm_id: str,
    status: str | None = Query(default=None),
    accuracy_rating: str | None = Query(default=None),
    reviewer_id: str | None = Query(default=None),
    include_superseded: bool = Query(default=False),
) -> list[dict]:
    try:
        return comparison_assessment_service.list_assessments(
            psalm_id,
            status=status,
            accuracy_rating=accuracy_rating,
            reviewer_id=reviewer_id,
            include_superseded=include_superseded,
        )
    except Exception as error:  # pragma: no cover
        raise_as_http(error)


@router.post("/comparison-assessments")
def create_comparison_assessment(payload: dict) -> dict:
    try:
        return comparison_assessment_service.create_assessment(
            unit_id=payload["unit_id"],
            literal_rendering_id=payload.get("literal_rendering_id"),
            english_rendering_id=payload.get("english_rendering_id"),
            accuracy_rating=payload.get("accuracy_rating"),
            accuracy_note=payload.get("accuracy_note", ""),
            creative_liberties_note=payload.get("creative_liberties_note", ""),
            created_by=payload.get("created_by", "api"),
            created_via=payload.get("created_via", "human"),
            generator_provider=payload.get("generator_provider"),
            generation_run_id=payload.get("generation_run_id"),
            status=payload.get("status", "draft"),
            display_reference=payload.get("display_reference"),
            rationale=payload.get("rationale", "api create comparison assessment"),
        )
    except Exception as error:  # pragma: no cover
        raise_as_http(error)


@router.patch("/comparison-assessments/{comparison_id}")
def revise_comparison_assessment(comparison_id: str, payload: dict) -> dict:
    """Revise an assessment.

    This never edits in place: the original is superseded and a linked successor
    is returned, so generated text survives review intact.
    """
    try:
        changes = {
            key: payload[key]
            for key in (
                "accuracy_rating",
                "accuracy_note",
                "creative_liberties_note",
                "status",
                "literal_rendering_id",
                "english_rendering_id",
                "display_reference",
            )
            if key in payload
        }
        return comparison_assessment_service.revise_assessment(
            unit_id=payload["unit_id"],
            comparison_id_value=comparison_id,
            created_by=payload.get("created_by", "api"),
            rationale=payload.get("rationale", "api revise comparison assessment"),
            reviewer_id=payload.get("reviewer_id"),
            **changes,
        )
    except Exception as error:  # pragma: no cover
        raise_as_http(error)
