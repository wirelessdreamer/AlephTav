from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import raise_as_http
from app.services import review_service

router = APIRouter(tags=["review"])


def _review(target_id: str, decision: str, payload: dict) -> dict:
    return review_service.add_review_decision(
        target_id=target_id,
        decision=decision,
        reviewer=payload.get("reviewer", "api-reviewer"),
        reviewer_role=payload.get("reviewer_role", "alignment reviewer"),
        notes=payload.get("notes", ""),
    )


@router.post("/review/{target_id}/approve")
def approve(target_id: str, payload: dict) -> dict:
    try:
        return _review(target_id, "approve", payload)
    except Exception as error:  # pragma: no cover
        raise_as_http(error)


@router.post("/review/{target_id}/request-changes")
def request_changes(target_id: str, payload: dict) -> dict:
    try:
        return _review(target_id, "request_changes", payload)
    except Exception as error:  # pragma: no cover
        raise_as_http(error)


@router.post("/review/{target_id}/accept-alternate")
def accept_alternate(target_id: str, payload: dict) -> dict:
    try:
        return _review(target_id, "accept-alternate", payload)
    except Exception as error:  # pragma: no cover
        raise_as_http(error)


@router.post("/review/{target_id}/reject")
def reject(target_id: str, payload: dict) -> dict:
    try:
        return _review(target_id, "reject", payload)
    except Exception as error:  # pragma: no cover
        raise_as_http(error)
