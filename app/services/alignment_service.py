from __future__ import annotations

from typing import Any

from app.core.ids import alignment_id
from app.services import audit_service, registry_service


def list_alignments(unit_id: str) -> list[dict[str, Any]]:
    return registry_service.load_unit(unit_id).get("alignments", [])


def coverage(unit: dict[str, Any]) -> dict[str, list[str]]:
    aligned_tokens = {token_id for item in unit.get("alignments", []) for token_id in item.get("source_token_ids", [])}
    uncovered = [token_id for token_id in unit.get("token_ids", []) if token_id not in aligned_tokens]
    unaligned_renderings = [
        rendering["rendering_id"] for rendering in unit.get("renderings", []) if not rendering.get("alignment_ids")
    ]
    return {"uncovered_tokens": uncovered, "unaligned_renderings": unaligned_renderings}


def create_alignment(unit_id: str, payload: dict[str, Any], created_by: str = "api") -> dict[str, Any]:
    before, unit = registry_service.update_unit(unit_id, lambda existing: existing)
    existing_ids = [item["alignment_id"] for item in unit.get("alignments", [])]
    record = {
        "alignment_id": alignment_id(unit_id, payload["layer"], existing_ids),
        "unit_id": unit_id,
        "layer": payload["layer"],
        "source_token_ids": payload["source_token_ids"],
        "target_span_ids": payload["target_span_ids"],
        "alignment_type": payload["alignment_type"],
        "confidence": payload.get("confidence", 0.5),
        "created_by": created_by,
        "created_via": payload.get("created_via", "manual"),
        "notes": payload.get("notes", ""),
    }
    unit.setdefault("alignments", []).append(record)
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
            item.update(payload)
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
