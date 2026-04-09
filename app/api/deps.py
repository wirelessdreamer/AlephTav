from __future__ import annotations

from fastapi import HTTPException

from app.core.errors import ContentError, LicensePolicyError, NotFoundError, ReviewRequiredError, ValidationError


def raise_as_http(error: Exception) -> None:
    if isinstance(error, NotFoundError):
        raise HTTPException(status_code=404, detail=str(error)) from error
    if isinstance(error, ReviewRequiredError):
        raise HTTPException(status_code=409, detail=str(error)) from error
    if isinstance(error, (ValidationError, LicensePolicyError, ContentError)):
        raise HTTPException(status_code=400, detail=str(error)) from error
    raise HTTPException(status_code=500, detail=str(error)) from error
