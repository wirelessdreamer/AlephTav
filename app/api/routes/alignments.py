from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import raise_as_http
from app.services import alignment_service

router = APIRouter(tags=["alignments"])


@router.get("/units/{unit_id}/alignments")
def get_alignments(unit_id: str) -> list[dict]:
    try:
        return alignment_service.list_alignments(unit_id)
    except Exception as error:  # pragma: no cover
        raise_as_http(error)


@router.post("/alignments")
def post_alignment(payload: dict) -> dict:
    try:
        return alignment_service.create_alignment(payload["unit_id"], payload)
    except Exception as error:  # pragma: no cover
        raise_as_http(error)


@router.patch("/alignments/{alignment_id}")
def patch_alignment(alignment_id: str, payload: dict) -> dict:
    try:
        return alignment_service.update_alignment(alignment_id, payload)
    except Exception as error:  # pragma: no cover
        raise_as_http(error)


@router.delete("/alignments/{alignment_id}")
def delete_alignment(alignment_id: str) -> dict:
    try:
        return alignment_service.delete_alignment(alignment_id)
    except Exception as error:  # pragma: no cover
        raise_as_http(error)
