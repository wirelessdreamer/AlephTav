from __future__ import annotations

from typing import Any

from app.core.ids import alignment_id
from app.core.errors import NotFoundError, ValidationError
from app.services import audit_service, registry_service

LOW_CONFIDENCE_THRESHOLD = 0.75


def list_alignments(unit_id: str) -> list[dict[str, Any]]:
    return registry_service.load_unit(unit_id).get("alignments", [])


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _span_lookup(unit: dict[str, Any]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for rendering in unit.get("renderings", []):
        for span in rendering.get("target_spans", []):
            lookup[span["span_id"]] = {"rendering_id": rendering["rendering_id"], "layer": rendering["layer"], "span": span}
    return lookup


def _validate_alignment_payload(unit: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    token_ids = _dedupe(payload.get("source_token_ids", []))
    span_ids = _dedupe(payload.get("target_span_ids", []))
    if not token_ids:
        raise ValidationError("Alignment requires at least one source token")
    if not span_ids:
        raise ValidationError("Alignment requires at least one target span")

    missing_tokens = [token_id for token_id in token_ids if token_id not in unit.get("token_ids", [])]
    if missing_tokens:
        raise NotFoundError(f"Unknown source token(s): {', '.join(missing_tokens)}")

    lookup = _span_lookup(unit)
    layer = payload["layer"]
    allowed_prefix = f"spn.{unit['unit_id']}.{layer}."
    missing_spans = [span_id for span_id in span_ids if span_id not in lookup and not span_id.startswith(allowed_prefix)]
    if missing_spans:
        raise NotFoundError(f"Unknown target span(s): {', '.join(missing_spans)}")

    wrong_layer_spans = [span_id for span_id in span_ids if span_id in lookup and lookup[span_id]["layer"] != layer]
    if wrong_layer_spans:
        raise ValidationError(f"Target span layer mismatch for: {', '.join(wrong_layer_spans)}")

    confidence = float(payload.get("confidence", 0.5))
    if confidence < 0 or confidence > 1:
        raise ValidationError("Alignment confidence must be between 0 and 1")

    return {
        "source_token_ids": token_ids,
        "target_span_ids": span_ids,
        "confidence": confidence,
    }


def _sync_rendering_alignment_ids(unit: dict[str, Any]) -> None:
    for rendering in unit.get("renderings", []):
        span_ids = {span["span_id"] for span in rendering.get("target_spans", [])}
        rendering["alignment_ids"] = [
            alignment["alignment_id"]
            for alignment in unit.get("alignments", [])
            if any(span_id in span_ids for span_id in alignment.get("target_span_ids", []))
        ]


def coverage(unit: dict[str, Any]) -> dict[str, list[str]]:
    aligned_tokens = {token_id for item in unit.get("alignments", []) for token_id in item.get("source_token_ids", [])}
    aligned_spans = {span_id for item in unit.get("alignments", []) for span_id in item.get("target_span_ids", [])}
    uncovered = [token_id for token_id in unit.get("token_ids", []) if token_id not in aligned_tokens]
    unaligned_spans = [
        span["span_id"]
        for rendering in unit.get("renderings", [])
        for span in rendering.get("target_spans", [])
        if span["span_id"] not in aligned_spans
    ]
    unaligned_renderings = [
        rendering["rendering_id"]
        for rendering in unit.get("renderings", [])
        if rendering.get("target_spans") and not any(span["span_id"] in aligned_spans for span in rendering.get("target_spans", []))
    ]
    low_confidence_alignments = [
        item["alignment_id"]
        for item in unit.get("alignments", [])
        if float(item.get("confidence", 0)) < LOW_CONFIDENCE_THRESHOLD
    ]
    return {
        "uncovered_tokens": uncovered,
        "unaligned_spans": unaligned_spans,
        "unaligned_renderings": unaligned_renderings,
        "low_confidence_alignments": low_confidence_alignments,
    }


def create_alignment(unit_id: str, payload: dict[str, Any], created_by: str = "api") -> dict[str, Any]:
    before, unit = registry_service.update_unit(unit_id, lambda existing: existing)
    validated = _validate_alignment_payload(unit, payload)
    existing_ids = [item["alignment_id"] for item in unit.get("alignments", [])]
    record = {
        "alignment_id": alignment_id(unit_id, payload["layer"], existing_ids),
        "unit_id": unit_id,
        "layer": payload["layer"],
        "source_token_ids": validated["source_token_ids"],
        "target_span_ids": validated["target_span_ids"],
        "alignment_type": payload["alignment_type"],
        "confidence": validated["confidence"],
        "created_by": created_by,
        "created_via": payload.get("created_via", "manual"),
        "notes": payload.get("notes", ""),
    }
    unit.setdefault("alignments", []).append(record)
    _sync_rendering_alignment_ids(unit)
    audit_service.create_audit_record(
        unit,
        before_hash=registry_service.file_hash(before),
        after_hash=registry_service.file_hash(unit),
        summary="Create alignment",
        rationale=payload.get("notes", "manual alignment"),
        created_by=created_by,
        entity_type="alignment",
        entity_id=record["alignment_id"],
        change_type="create",
    )
    registry_service.save_unit(unit)
    return record


def update_alignment(alignment_id_value: str, payload: dict[str, Any]) -> dict[str, Any]:
    unit_id = alignment_id_value.split(".")[1:4]
    target_unit_id = ".".join(unit_id)
    before, unit = registry_service.update_unit(target_unit_id, lambda existing: existing)
    for item in unit.get("alignments", []):
        if item["alignment_id"] == alignment_id_value:
            merged = {**item, **payload}
            validated = _validate_alignment_payload(unit, merged)
            item.update(payload)
            item["source_token_ids"] = validated["source_token_ids"]
            item["target_span_ids"] = validated["target_span_ids"]
            item["confidence"] = validated["confidence"]
            _sync_rendering_alignment_ids(unit)
            audit_service.create_audit_record(
                unit,
                before_hash=registry_service.file_hash(before),
                after_hash=registry_service.file_hash(unit),
                summary="Update alignment",
                rationale=payload.get("notes", "alignment update"),
                created_by="api",
                entity_type="alignment",
                entity_id=alignment_id_value,
            )
            registry_service.save_unit(unit)
            return item
    raise KeyError(alignment_id_value)


def delete_alignment(alignment_id_value: str) -> dict[str, str]:
    target_unit_id = ".".join(alignment_id_value.split(".")[1:4])
    before, unit = registry_service.update_unit(target_unit_id, lambda existing: existing)
    unit["alignments"] = [item for item in unit.get("alignments", []) if item["alignment_id"] != alignment_id_value]
    _sync_rendering_alignment_ids(unit)
    audit_service.create_audit_record(
        unit,
        before_hash=registry_service.file_hash(before),
        after_hash=registry_service.file_hash(unit),
        summary="Delete alignment",
        rationale="manual deletion",
        created_by="api",
        entity_type="alignment",
        entity_id=alignment_id_value,
        change_type="delete",
    )
    registry_service.save_unit(unit)
    return {"deleted": alignment_id_value}
