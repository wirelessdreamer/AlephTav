from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import raise_as_http
from app.services import lexical_service

router = APIRouter(tags=["search"])


@router.get("/search/concordance")
def search_concordance(query: str = Query(...), field: str = Query("lemma")) -> list[dict]:
    try:
        return lexical_service.search_concordance(query, field=field)
    except Exception as error:  # pragma: no cover
        raise_as_http(error)
