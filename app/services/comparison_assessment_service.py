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

from app.core import versification
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
    # The only value asserting the ABSENCE of a source relationship: performance
    # or arrangement apparatus with no counterpart in the Hebrew. Guarded below,
    # and deliberately absent from the translation contract's "literalness" enum
    # so a translating model can never label its own invented material.
    "no_source_basis",
)

NO_SOURCE_BASIS = "no_source_basis"

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


def _validate(
    accuracy_rating: str | None,
    created_via: str,
    status: str,
    non_source_material: list[dict[str, Any]] | None = None,
) -> None:
    if accuracy_rating is not None and accuracy_rating not in ACCURACY_RATINGS:
        raise ValidationError(f"Unknown accuracy_rating: {accuracy_rating}")
    if accuracy_rating == NO_SOURCE_BASIS and not non_source_material:
        # The rating must be backed by the material it names, or it decays into
        # meaning "very loose paraphrase".
        raise ValidationError(
            f"accuracy_rating '{NO_SOURCE_BASIS}' requires a non-empty non_source_material"
        )
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


#: Token fields worth showing in the hover study card, in display order.
_STUDY_FIELDS = (
    "token_id",
    "surface",
    "transliteration",
    "lemma",
    "strong",
    "morph_readable",
    "part_of_speech",
    "stem",
    "display_gloss",
    "gloss_parts",
    "word_sense",
    "semantic_role",
    "syntax_role",
    "referent",
    "greek",
    "greek_strong",
    "ref",
)


def study_token(token: dict[str, Any]) -> dict[str, Any]:
    """Trim a corpus token to the fields the study card renders.

    Empty fields are dropped so the card shows only what the corpus actually
    knows, rather than a wall of nulls.
    """
    card = {key: token[key] for key in _STUDY_FIELDS if token.get(key)}
    card["token_id"] = token["token_id"]
    card["surface"] = token["surface"]
    occurrences = token.get("corpus_occurrence_refs") or []
    card["occurrence_count"] = len(occurrences)
    card["occurrence_refs"] = occurrences[:12]
    return card


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
    literal_backbone: list[str] | None = None,
    word_notes: list[dict[str, Any]] | None = None,
    non_source_material: list[dict[str, Any]] | None = None,
    analyzed_text_hash: str | None = None,
) -> dict[str, Any]:
    _validate(accuracy_rating, created_via, status, non_source_material)
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
        "literal_backbone": list(literal_backbone or []),
        "word_notes": list(word_notes or []),
        "non_source_material": list(non_source_material or []),
        "analyzed_text_hash": analyzed_text_hash,
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
        # Evidence describes the same audited rendering, so it survives review.
        # A reviewer revises the verdict, not the findings behind it.
        literal_backbone=original.get("literal_backbone"),
        word_notes=original.get("word_notes"),
        non_source_material=original.get("non_source_material"),
        analyzed_text_hash=original.get("analyzed_text_hash"),
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
        tokens: list[dict[str, Any]] = []

        for unit in units:
            hebrew_parts.append(unit["source_hebrew"])
            active_note = _active_assessment(unit)
            notes_by_token = _notes_by_token(active_note)
            for token in unit.get("tokens", []):
                card = study_token(token)
                note = notes_by_token.get(card["token_id"])
                if note is not None:
                    card["note"] = note
                tokens.append(card)
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
        mt_verse, _segment = _unit_sort_key(first["unit_id"])
        rows.append(
            {
                "mt_reference": first["ref"],
                # English numbering comes from the committed versification table,
                # not from the model and not from MT by default.
                "display_reference": versification.display_reference(
                    psalm_id, first["ref"], mt_verse
                ),
                "unit_ids": [unit["unit_id"] for unit in units],
                "hebrew_text": " ".join(hebrew_parts),
                # Per-word study payload so the Hebrew column can be hovered
                # word by word rather than rendered as one opaque string.
                "tokens": tokens,
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
                "literal_backbone": (assessment or {}).get("literal_backbone", []),
                "non_source_material": (assessment or {}).get("non_source_material", []),
                # An assessment written against text that has since been edited
                # in place is stale, even though its rendering ids still match.
                "stale": _is_stale(assessment, units, literal_layer, english_layer),
            }
        )

    return {
        "psalm_id": psalm_id,
        "title": psalm.get("title", ""),
        "literal_layer": literal_layer,
        "english_layer": english_layer,
        "canonical_numbering": versification.canonical_numbering(psalm_id),
        "analysis": _active_psalm_analysis(psalm),
        "rows": rows,
    }


def _active_assessment(unit: dict[str, Any]) -> dict[str, Any] | None:
    active = [
        item for item in unit.get("comparison_assessments", []) if item["status"] != "superseded"
    ]
    return active[-1] if active else None


def _notes_by_token(assessment: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    """Index word notes by token so each study card can find its own."""
    if not assessment:
        return {}
    index: dict[str, dict[str, Any]] = {}
    for note in assessment.get("word_notes", []):
        for token_id in note.get("token_ids", []):
            index.setdefault(token_id, note)
    return index


def _is_stale(
    assessment: dict[str, Any] | None,
    units: list[dict[str, Any]],
    literal_layer: str,
    english_layer: str,
) -> bool:
    """True when the audited text has changed since the analysis ran.

    An assessment belongs to one unit, so it is that unit's current text the
    fingerprint is compared against.
    """
    if not assessment:
        return False
    recorded = assessment.get("analyzed_text_hash")
    if not recorded:
        # Human-authored assessments carry no fingerprint and are never stale.
        return False
    owner = next((u for u in units if u["unit_id"] == assessment["unit_id"]), None)
    if owner is None:
        return False

    from app.services import codex_analysis_service

    current = codex_analysis_service.verse_fingerprint(
        owner,
        [select_rendering(owner, literal_layer), select_rendering(owner, english_layer)],
    )
    return current != recorded


def _active_psalm_analysis(psalm: dict[str, Any]) -> dict[str, Any] | None:
    for record in reversed(psalm.get("analyses", [])):
        if record.get("status") != "superseded":
            return record
    return None
