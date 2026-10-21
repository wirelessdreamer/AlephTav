"""Read-only study interfaces. No import, acceptance, or generation side effects."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request

from app.api.deps import raise_as_http
from app.core.errors import LicensePolicyError, NotFoundError
from app.services import greek_study_service as study

router = APIRouter(tags=["greek-study"])


def _view(snapshot: str | None = None, policy: str | None = None) -> study.StudyView:
    try:
        return study.load_public_view(snapshot, policy)
    except study.StaleStudyError as error:
        raise HTTPException(
            409, {"code": "study_stale", "action": "restart", "message": str(error)}
        ) from error
    except LicensePolicyError as error:
        raise HTTPException(403, {"code": "source_unavailable", "message": str(error)}) from error
    except NotFoundError as error:
        if snapshot is not None:
            raise HTTPException(409, {"code": "study_stale", "action": "restart"}) from error
        raise_as_http(error)
    except Exception as error:
        raise_as_http(error)


@router.get("/lxx/editions")
def editions() -> dict:
    try:
        view = _view()
    except HTTPException as error:
        if error.status_code in {403, 404}:
            return {"editions": [], "availability": "unavailable"}
        raise
    # Publication proves coherence, not release permission. An explicit availability
    # record is required before exposing a production source picker.
    from app.services.greek_study_export_service import availability

    if not availability(view.descriptor):
        return {"editions": [], "availability": "awaiting_release_gates"}
    return {
        "editions": [
            {
                **view.identity(),
                "edition_id": view.descriptor["edition_id"],
                "text_revision_id": view.descriptor["text_revision_id"],
            }
        ]
    }


@router.get("/lxx/psalms")
def psalms(study_snapshot_id: str, policy_revision_id: str) -> dict:
    view = _view(study_snapshot_id, policy_revision_id)
    return {**view.identity(), "psalms": sorted({token["psalm"] for token in view.tokens.values()})}


@router.get("/lxx/units/{unit_id}")
def unit(unit_id: str, study_snapshot_id: str, policy_revision_id: str) -> dict:
    view = _view(study_snapshot_id, policy_revision_id)
    for candidate in view.payload.get("units", []):
        if candidate["unit_id"] == unit_id:
            return {**view.identity(), "unit": candidate}
    raise HTTPException(404, "Greek source unit not found")


@router.get("/lxx/reader")
def reader(psalm: int, study_snapshot_id: str, policy_revision_id: str) -> dict:
    view = _view(study_snapshot_id, policy_revision_id)
    ids = {token["unit_id"] for token in view.tokens.values() if token["psalm"] == psalm}
    return {
        **view.identity(),
        "units": [unit for unit in view.payload.get("units", []) if unit["unit_id"] in ids],
    }


@router.get("/greek/tokens/{token_id}/card")
def card(token_id: str, study_snapshot_id: str, policy_revision_id: str) -> dict:
    try:
        return _view(study_snapshot_id, policy_revision_id).card(token_id)
    except NotFoundError as error:
        raise_as_http(error)


@router.get("/greek/lexicon/entries/{entry_id}")
def entry(entry_id: str, study_snapshot_id: str, policy_revision_id: str) -> dict:
    try:
        return _view(study_snapshot_id, policy_revision_id).entry(entry_id)
    except NotFoundError as error:
        raise_as_http(error)


@router.get("/greek/lexicon/identifiers")
def identifiers(scheme: str, value: str, study_snapshot_id: str, policy_revision_id: str) -> dict:
    return _view(study_snapshot_id, policy_revision_id).identifiers(scheme, value)


@router.get("/greek/concordance")
def concordance(
    request: Request,
    study_snapshot_id: str,
    policy_revision_id: str,
    query_kind: Literal["lexeme_id", "lemma_text", "identifier", "surface"],
    value: str,
    identifier_scheme: str | None = None,
    analysis_scope: Literal["reviewed", "proposed", "all"] = "all",
    analysis_selection: Literal["selected", "possible"] = "possible",
    match_unit: Literal["token", "expression"] = "token",
    expand_components: bool = False,
    page_size: int = Query(50, ge=1, le=200),
    cursor: str | None = None,
) -> dict:
    allowed = {
        "study_snapshot_id",
        "policy_revision_id",
        "query_kind",
        "value",
        "identifier_scheme",
        "analysis_scope",
        "analysis_selection",
        "match_unit",
        "expand_components",
        "page_size",
        "cursor",
    }
    if set(request.query_params) - allowed:
        raise HTTPException(422, "Unknown concordance query field")
    view = _view(study_snapshot_id, policy_revision_id)
    try:
        query = study.ConcordanceQuery(
            study_snapshot_id=study_snapshot_id,
            policy_revision_id=policy_revision_id,
            query_kind=query_kind,
            value=value,
            identifier_scheme=identifier_scheme,
            analysis_scope=analysis_scope,
            analysis_selection=analysis_selection,
            match_unit=match_unit,
            expand_components=expand_components,
        )
        return view.concordance(query, page_size=page_size, cursor=cursor)
    except study.StaleStudyError as error:
        raise HTTPException(
            409, {"code": "study_stale", "action": "restart", "message": str(error)}
        ) from error
    except Exception as error:
        raise_as_http(error)
