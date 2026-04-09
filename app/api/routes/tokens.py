from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import raise_as_http
from app.services import lexical_service

router = APIRouter(tags=["tokens"])


@router.get("/tokens/{token_id}")
def get_token(token_id: str) -> dict:
    try:
        return lexical_service.lexical_card(token_id)
    except Exception as error:  # pragma: no cover
        raise_as_http(error)


@router.get("/tokens/{token_id}/occurrences")
def get_token_occurrences(token_id: str) -> dict:
    try:
        return lexical_service.token_occurrences(token_id)
    except Exception as error:  # pragma: no cover
        raise_as_http(error)


@router.get("/lexicon/lemma/{lemma}")
def get_lemma_occurrences(lemma: str) -> list[dict]:
    try:
        return lexical_service.search_concordance(lemma, field="lemma")
    except Exception as error:  # pragma: no cover
        raise_as_http(error)


@router.get("/lexicon/strong/{strong}")
def get_strong_occurrences(strong: str) -> list[dict]:
    try:
        return lexical_service.search_concordance(strong, field="strong")
    except Exception as error:  # pragma: no cover
        raise_as_http(error)
