from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import raise_as_http
from app.services import raw_mutation_policy_service, registry_service

router = APIRouter(tags=["project"])


@router.get("/project")
def get_project() -> dict:
    try:
        return registry_service.load_project()
    except Exception as error:  # pragma: no cover
        raise_as_http(error)


@router.patch("/project")
def patch_project(payload: dict) -> dict:
    try:
        raw_mutation_policy_service.reject_project_update()
    except Exception as error:  # pragma: no cover
        raise_as_http(error)
