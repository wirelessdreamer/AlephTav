"""ComparisonAssessment records and the five-column comparison table.

An assessment evaluates one chosen English rendering against a literal rendering
for a single source unit. Assessments live on the unit JSON next to renderings so
they are committed content and share the unit's audit trail.

A review never overwrites an existing assessment: :func:`revise_assessment`
creates a successor linked through ``revision_of`` and marks the original
``superseded``.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from app.core.errors import NotFoundError, ValidationError
from app.core.ids import comparison_id as build_comparison_id
from app.services import audit_service, registry_service

ACCURACY_RATINGS = (
    "literal",
    "very_close",
    "close",
    "adapted",
    "interpretive",
    "omission",
)

CREATED_VIA = ("human", "codex", "local_model", "deterministic")

STATUSES = (
    "draft",
    "proposed",
    "reviewed",
    "accepted_as_alternate",
    "canonical",
    "rejected",
    "superseded",
)

LITERAL_LAYER = "literal"
ENGLISH_LAYERS = ("lyric", "metered_lyric", "parallelism_lyric", "concept", "phrase")


def _assessments(unit: dict[str, Any]) -> list[dict[str, Any]]:
    return unit.setdefault("comparison_assessments", [])


def _unit_sort_key(unit_id: str) -> tuple[int, str]:
    """Canonical source order: verse number, then segment letter."""
    parts = unit_id.split(".")
    try:
        verse = int(parts[1].lstrip("v"))
    except (IndexError, ValueError):
        verse = 0
    segment = parts[2] if len(parts) > 2 else ""
    return verse, segment


def _find(unit: dict[str, Any], comparison_id_value: str) -> dict[str, Any]:
    for item in _assessments(unit):
        if item["comparison_id"] == comparison_id_value:
            return item
    raise NotFoundError(f"Comparison assessment not found: {comparison_id_value}")


def _validate(accuracy_rating: str | None, created_via: str, status: str) -> None:
    if accuracy_rating is not None and accuracy_rating not in ACCURACY_RATINGS:
        raise ValidationError(f"Unknown accuracy_rating: {accuracy_rating}")
    if created_via not in CREATED_VIA:
        raise ValidationError(f"Unknown created_via: {created_via}")
    if status not in STATUSES:
        raise ValidationError(f"Unknown comparison status: {status}")


def _rendering_by_id(unit: dict[str, Any], rendering_id_value: str | None) -> dict[str, Any] | None:
    if not rendering_id_value:
        return None
    for rendering in unit.get("renderings", []):
        if rendering["rendering_id"] == rendering_id_value:
            return rendering
    return None


def select_rendering(unit: dict[str, Any], layer: str) -> dict[str, Any] | None:
    """Pick the rendering a table row should display for ``layer``.

    Canonical wins; otherwise the most recently accepted alternate. Returns None
    when the unit has nothing at that layer, so the row renders incomplete rather
    than inventing text (see the failure table in the requirements).
    """
    candidates = [r for r in unit.get("renderings", []) if r.get("layer") == layer]
    if not candidates:
        return None
    for status in ("canonical", "accepted_as_alternate", "under_review", "proposed", "draft"):
        matches = [r for r in candidates if r.get("status") == status]
        if matches:
            return matches[-1]
    return candidates[-1]


def create_assessment(
    unit_id: str,
    literal_rendering_id: str | None,
    english_rendering_id: str | None,
    accuracy_rating: str | None = None,
    accuracy_note: str = "",
    creative_liberties_note: str = "",
    created_by: str = "api",
    created_via: str = "human",
    generator_provider: str | None = None,
    generation_run_id: str | None = None,
    status: str = "draft",
    display_reference: str | None = None,
    revision_of: str | None = None,
    rationale: str = "Create comparison assessment",
) -> dict[str, Any]:
    _validate(accuracy_rating, created_via, status)
    unit = registry_service.load_unit(unit_id)
    before = deepcopy(unit)

    for label, rendering_id_value in (
        ("literal_rendering_id", literal_rendering_id),
        ("english_rendering_id", english_rendering_id),
    ):
        if rendering_id_value and _rendering_by_id(unit, rendering_id_value) is None:
            raise ValidationError(f"{label} is not a rendering of {unit_id}: {rendering_id_value}")

    existing = [item["comparison_id"] for item in _assessments(unit)]
    mt_reference = unit["ref"]
    item = {
        "comparison_id": build_comparison_id(unit_id, existing),
        "psalm_id": unit["psalm_id"],
        "unit_id": unit_id,
        "mt_reference": mt_reference,
        # The corpus stores MT numbering and carries no superscription marker, so
        # display numbering defaults to MT until that metadata exists.
        "display_reference": display_reference or mt_reference,
        "hebrew_text": unit["source_hebrew"],
        "literal_rendering_id": literal_rendering_id,
        "english_rendering_id": english_rendering_id,
        "accuracy_rating": accuracy_rating,
        "accuracy_note": accuracy_note,
        "creative_liberties_note": creative_liberties_note,
        "status": status,
        "created_by": created_by,
        "created_via": created_via,
        "generator_provider": generator_provider,
        "generation_run_id": generation_run_id,
        "reviewer_id": None,
        "reviewed_at": None,
        "revision_of": revision_of,
        "audit_ids": [],
    }
    _assessments(unit).append(item)
    record = audit_service.create_audit_record(
        unit,
        before_hash=registry_service.file_hash(before),
        after_hash=registry_service.file_hash(unit),
        summary="Create comparison assessment",
        rationale=rationale,
        created_by=created_by,
        entity_type="comparison_assessment",
        entity_id=item["comparison_id"],
        change_type="create",
    )
    item["audit_ids"] = [record["audit_id"]]
    registry_service.save_unit(unit)
    return item


def revise_assessment(
    unit_id: str,
    comparison_id_value: str,
    created_by: str = "api",
    rationale: str = "Revise comparison assessment",
    reviewer_id: str | None = None,
    **changes: Any,
) -> dict[str, Any]:
    """Supersede an assessment with a linked revision.

    The original is never mutated in place beyond its status, so Codex-suggested
    text survives review intact.
    """
    unit = registry_service.load_unit(unit_id)
    original = _find(unit, comparison_id_value)
    if original["status"] == "superseded":
        raise ValidationError(f"Assessment already superseded: {comparison_id_value}")

    allowed = {
        "accuracy_rating",
        "accuracy_note",
        "creative_liberties_note",
        "status",
        "literal_rendering_id",
        "english_rendering_id",
        "display_reference",
    }
    unknown = set(changes) - allowed
    if unknown:
        raise ValidationError(f"Cannot revise unknown fields: {sorted(unknown)}")

    # Status is not inherited: a revision is "reviewed" unless the caller says
    # otherwise, so a review of a draft does not silently stay a draft.
    successor_fields = {key: original[key] for key in allowed - {"status"} if key in original}
    successor_fields.update({k: v for k, v in changes.items() if v is not None})
    successor_fields.setdefault("status", "reviewed")

    before = deepcopy(unit)
    original["status"] = "superseded"
    registry_service.save_unit(unit)

    successor = create_assessment(
        unit_id=unit_id,
        literal_rendering_id=successor_fields.get("literal_rendering_id"),
        english_rendering_id=successor_fields.get("english_rendering_id"),
        accuracy_rating=successor_fields.get("accuracy_rating"),
        accuracy_note=successor_fields.get("accuracy_note", ""),
        creative_liberties_note=successor_fields.get("creative_liberties_note", ""),
        created_by=created_by,
        created_via=original["created_via"],
        generator_provider=original["generator_provider"],
        generation_run_id=original["generation_run_id"],
        status=successor_fields["status"],
        display_reference=successor_fields.get("display_reference"),
        revision_of=comparison_id_value,
        rationale=rationale,
    )

    if reviewer_id:
        unit = registry_service.load_unit(unit_id)
        stored = _find(unit, successor["comparison_id"])
        stored["reviewer_id"] = reviewer_id
        stored["reviewed_at"] = datetime.now(UTC).isoformat()
        registry_service.save_unit(unit)
        successor = stored

    # Keep the supersede edit auditable alongside the successor's own record.
    unit = registry_service.load_unit(unit_id)
    audit_service.create_audit_record(
        unit,
        before_hash=registry_service.file_hash(before),
        after_hash=registry_service.file_hash(unit),
        summary="Supersede comparison assessment",
        rationale=rationale,
        created_by=created_by,
        entity_type="comparison_assessment",
        entity_id=comparison_id_value,
        change_type="update",
    )
    registry_service.save_unit(unit)
    return successor


def list_assessments(
    psalm_id: str,
    status: str | None = None,
    accuracy_rating: str | None = None,
    reviewer_id: str | None = None,
    include_superseded: bool = False,
) -> list[dict[str, Any]]:
    psalm = registry_service.load_psalm(psalm_id)
    items: list[dict[str, Any]] = []
    for unit in sorted(psalm["units"], key=lambda u: _unit_sort_key(u["unit_id"])):
        for item in unit.get("comparison_assessments", []):
            if not include_superseded and item["status"] == "superseded":
                continue
            if status and item["status"] != status:
                continue
            if accuracy_rating and item["accuracy_rating"] != accuracy_rating:
                continue
            if reviewer_id and item["reviewer_id"] != reviewer_id:
                continue
            items.append(item)
    return items


def build_comparison_table(
    psalm_id: str,
    literal_layer: str = LITERAL_LAYER,
    english_layer: str | None = None,
    layer: str | None = None,
) -> dict[str, Any]:
    """Assemble the five-column table for a psalm.

    Units belonging to the same verse are combined in canonical source order
    while keeping links to each contributing unit id.
    """
    psalm = registry_service.load_psalm(psalm_id)
    english_layer = english_layer or layer or "lyric"

    grouped: dict[int, list[dict[str, Any]]] = {}
    for unit in psalm["units"]:
        verse, _segment = _unit_sort_key(unit["unit_id"])
        grouped.setdefault(verse, []).append(unit)

    rows: list[dict[str, Any]] = []
    for verse in sorted(grouped):
        units = sorted(grouped[verse], key=lambda u: _unit_sort_key(u["unit_id"]))
        literal_parts: list[str] = []
        english_parts: list[str] = []
        hebrew_parts: list[str] = []
        assessments: list[dict[str, Any]] = []
        literal_ids: list[str] = []
        english_ids: list[str] = []

        for unit in units:
            hebrew_parts.append(unit["source_hebrew"])
            literal = select_rendering(unit, literal_layer)
            english = select_rendering(unit, english_layer)
            if literal:
                literal_parts.append(literal["text"])
                literal_ids.append(literal["rendering_id"])
            if english:
                english_parts.append(english["text"])
                english_ids.append(english["rendering_id"])
            active = [
                item
                for item in unit.get("comparison_assessments", [])
                if item["status"] != "superseded"
            ]
            if active:
                assessments.append(active[-1])

        assessment = assessments[-1] if assessments else None
        first = units[0]
        rows.append(
            {
                "mt_reference": first["ref"],
                "display_reference": (assessment or {}).get("display_reference") or first["ref"],
                "unit_ids": [unit["unit_id"] for unit in units],
                "hebrew_text": " ".join(hebrew_parts),
                "literal_text": "\n".join(literal_parts) if literal_parts else None,
                "literal_rendering_ids": literal_ids,
                "english_text": "\n".join(english_parts) if english_parts else None,
                "english_rendering_ids": english_ids,
                "accuracy_rating": (assessment or {}).get("accuracy_rating"),
                "accuracy_note": (assessment or {}).get("accuracy_note", ""),
                "creative_liberties_note": (assessment or {}).get("creative_liberties_note", ""),
                "assessment_status": (assessment or {}).get("status"),
                "created_via": (assessment or {}).get("created_via"),
                "generator_provider": (assessment or {}).get("generator_provider"),
                "comparison_id": (assessment or {}).get("comparison_id"),
                "incomplete": not literal_parts or not english_parts,
            }
        )

    return {
        "psalm_id": psalm_id,
        "title": psalm.get("title", ""),
        "literal_layer": literal_layer,
        "english_layer": english_layer,
        "rows": rows,
    }
