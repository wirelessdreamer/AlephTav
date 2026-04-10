from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import raise_as_http
from app.services import lexical_service, search_service

router = APIRouter(tags=["search"])


@router.get("/search/concordance")
def search_concordance(query: str = Query(...), field: str = Query("lemma")) -> list[dict]:
    try:
        return lexical_service.search_concordance(query, field=field)
    except Exception as error:  # pragma: no cover
        raise_as_http(error)


@router.get("/search/advanced")
def advanced_search(
    query: str = Query(...),
    scope: str = Query("all"),
    include_witnesses: bool = Query(False),
) -> list[dict]:
    try:
        return search_service.advanced_search(query, scope=scope, include_witnesses=include_witnesses)
    except Exception as error:  # pragma: no cover
        raise_as_http(error)


@router.get("/search/presets/{name}")
def preset_view(name: str, release_id: str | None = Query(None)) -> list[dict]:
    try:
        return search_service.preset_view(name, release_id=release_id)
    except Exception as error:  # pragma: no cover
        raise_as_http(error)
