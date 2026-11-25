"""Record editorial intent without granting review or source authority."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict, Field

from app.api.deps import raise_as_http
from app.services import translation_choices_service as choices

router = APIRouter(tags=["translation-choices"])
BASE = "/psalms/{psalm_id}/translation-choices"
Identity = Annotated[str, Field(strict=True, min_length=1, max_length=200, pattern=r"\S")]


class ChoiceTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["rendering", "arrangement_line"]
    id: Identity
    arrangement_id: Identity | None = None
    expected_revision: Annotated[
        str, Field(strict=True, min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    ]


class RecordChoice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    translation_id: Identity | None = None
    targets: Annotated[list[ChoiceTarget], Field(min_length=1, max_length=20)]
    decision: Annotated[str, Field(strict=True, min_length=1, max_length=2000, pattern=r"\S")]
    rationale: Annotated[str, Field(strict=True, min_length=1, max_length=8000, pattern=r"\S")]
    context_status: Literal["not_established", "provided_by_translator"]
    context_note: Annotated[str, Field(strict=True, min_length=1, max_length=4000, pattern=r"\S")]
    created_by: Identity
    supersedes_audit_id: Identity | None = None


@router.get(BASE)
def list_translation_choices(
    psalm_id: str,
    translation_id: str | None = Query(default=None),
    unit_id: str | None = Query(default=None),
    arrangement_id: str | None = Query(default=None),
) -> dict:
    try:
        return choices.choices_view(
            psalm_id,
            translation_id or None,
            unit_id=unit_id,
            arrangement_id=arrangement_id,
        )
    except Exception as error:
        raise_as_http(error)


@router.post(BASE)
def record_translation_choice(psalm_id: str, payload: RecordChoice) -> dict:
    """Append a current-wording decision; earlier decisions remain inspectable."""
    try:
        return choices.record_choice(
            psalm_id,
            payload.translation_id,
            targets=[target.model_dump(exclude_none=True) for target in payload.targets],
            decision=payload.decision,
            rationale=payload.rationale,
            context_status=payload.context_status,
            context_note=payload.context_note,
            created_by=payload.created_by,
            supersedes_audit_id=payload.supersedes_audit_id,
        )
    except Exception as error:
        raise_as_http(error)
