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
def get_lemma_occurrences(lemma: str) -> dict:
    try:
        return lexical_service.lemma_occurrences(lemma)
    except Exception as error:  # pragma: no cover
        raise_as_http(error)


@router.get("/lexicon/strong/{strong}")
def get_strong_occurrences(strong: str) -> dict:
    try:
        return lexical_service.strong_occurrences(strong)
    except Exception as error:  # pragma: no cover
        raise_as_http(error)


@router.get("/state/lexical-card")
def get_pinned_lexical_card() -> dict:
    try:
        return lexical_service.get_pinned_lexical_card()
    except Exception as error:  # pragma: no cover
        raise_as_http(error)


@router.put("/state/lexical-card")
def set_pinned_lexical_card(payload: dict) -> dict:
    try:
        return lexical_service.set_pinned_lexical_card(payload.get("token_id"))
    except Exception as error:  # pragma: no cover
        raise_as_http(error)
