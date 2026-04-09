from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import raise_as_http
from app.services import audit_service, report_service

router = APIRouter(tags=["audit"])


@router.get("/audit/unit/{unit_id}")
def get_unit_audit(unit_id: str) -> list[dict]:
    try:
        return audit_service.audit_for_unit(unit_id)
    except Exception as error:  # pragma: no cover
        raise_as_http(error)


@router.get("/audit/release/{release_id}")
def get_release_audit(release_id: str) -> dict:
    try:
        return report_service.generate_release_report(release_id)
    except Exception as error:  # pragma: no cover
        raise_as_http(error)


@router.get("/reports/open-concerns")
def get_open_concerns() -> dict:
    try:
        return audit_service.open_concerns()
    except Exception as error:  # pragma: no cover
        raise_as_http(error)
