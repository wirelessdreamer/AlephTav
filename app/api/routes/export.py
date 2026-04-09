from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import raise_as_http
from app.services import export_service

router = APIRouter(tags=["export"])


@router.post("/export/book")
def export_book(payload: dict | None = None) -> dict:
    try:
        request = payload or {}
        path = export_service.export_book(psalm_id=request.get("psalm_id"))
        return {"path": str(path)}
    except Exception as error:  # pragma: no cover
        raise_as_http(error)


@router.post("/export/release")
def export_release(payload: dict) -> dict:
    try:
        path = export_service.export_release(payload["release_id"])
        return {"path": str(path)}
    except Exception as error:  # pragma: no cover
        raise_as_http(error)
