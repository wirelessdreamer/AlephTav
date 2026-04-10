from __future__ import annotations

from typing import Any

from app.core.errors import NotFoundError, ReviewRequiredError
from app.core.ids import rendering_id
from app.services import audit_service, registry_service


def list_renderings(unit_id: str, alternates_only: bool = False) -> list[dict[str, Any]]:
    renderings = registry_service.load_unit(unit_id).get("renderings", [])
    if alternates_only:
        return [item for item in renderings if item["status"] in {"accepted_as_alternate", "proposed", "deprecated"}]
    return renderings


def create_rendering(
    unit_id: str,
    layer: str,
    text: str,
    status: str,
    rationale: str,
    created_by: str,
    style_tags: list[str] | None = None,
    target_spans: list[dict[str, Any]] | None = None,
    alignment_ids: list[str] | None = None,
    drift_flags: list[str] | None = None,
    metrics: dict[str, Any] | None = None,
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    before, unit = registry_service.update_unit(unit_id, lambda existing: existing)
    hint = "can" if status == "canonical" else "alt"
    existing_ids = [item["rendering_id"] for item in unit.get("renderings", [])]
    item = {
        "rendering_id": rendering_id(unit_id, layer, hint, existing_ids),
        "unit_id": unit_id,
        "layer": layer,
        "status": status,
        "text": text,
        "style_tags": style_tags or [layer],
        "target_spans": target_spans or [],
        "alignment_ids": alignment_ids or [],
        "drift_flags": drift_flags or [],
        "metrics": metrics or {},
        "rationale": rationale,
        "provenance": provenance or {"source_ids": ["uxlc", "oshb", "macula"], "generator": created_by},
    }
    unit.setdefault("renderings", []).append(item)
    key = "canonical_rendering_ids" if status == "canonical" else "alternate_rendering_ids"
    unit.setdefault(key, []).append(item["rendering_id"])
    audit_service.create_audit_record(
        unit,
        before_hash=registry_service.file_hash(before),
        after_hash=registry_service.file_hash(unit),
        summary="Create rendering",
        rationale=rationale,
        created_by=created_by,
        entity_type="rendering",
        entity_id=item["rendering_id"],
        change_type="create",
    )
    registry_service.save_unit(unit)
    return item


def update_rendering(rendering_id_value: str, payload: dict[str, Any], created_by: str = "api") -> dict[str, Any]:
    unit_id = ".".join(rendering_id_value.split(".")[1:4])
    before, unit = registry_service.update_unit(unit_id, lambda existing: existing)
    for rendering in unit.get("renderings", []):
        if rendering["rendering_id"] == rendering_id_value:
            rendering.update(payload)
            audit_service.create_audit_record(
                unit,
                before_hash=registry_service.file_hash(before),
                after_hash=registry_service.file_hash(unit),
                summary="Update rendering",
                rationale=payload.get("rationale", "rendering update"),
                created_by=created_by,
                entity_type="rendering",
                entity_id=rendering_id_value,
            )
            registry_service.save_unit(unit)
            return rendering
    raise NotFoundError(rendering_id_value)


def _approvals_for(unit: dict[str, Any], target_id: str) -> int:
    return sum(1 for item in unit.get("review_decisions", []) if item["target_id"] == target_id and item["decision"] == "approve")


def promote_rendering(rendering_id_value: str, reviewer: str, reviewer_role: str) -> dict[str, Any]:
    unit_id = ".".join(rendering_id_value.split(".")[1:4])
    before, unit = registry_service.update_unit(unit_id, lambda existing: existing)
    if _approvals_for(unit, rendering_id_value) < registry_service.load_project()["review_policy"]["canonical_required_approvals"]:
        raise ReviewRequiredError("Human review is required before promotion to canonical")
    target = None
    for rendering in unit.get("renderings", []):
        if rendering["rendering_id"] == rendering_id_value:
            target = rendering
            break
    if target is None:
        raise NotFoundError(rendering_id_value)
    for rendering in unit.get("renderings", []):
        if rendering["layer"] == target["layer"] and rendering["status"] == "canonical":
            rendering["status"] = "accepted_as_alternate"
            if rendering["rendering_id"] not in unit["alternate_rendering_ids"]:
                unit["alternate_rendering_ids"].append(rendering["rendering_id"])
    target["status"] = "canonical"
    if target["rendering_id"] not in unit["canonical_rendering_ids"]:
        unit["canonical_rendering_ids"].append(target["rendering_id"])
    if target["rendering_id"] in unit["alternate_rendering_ids"]:
        unit["alternate_rendering_ids"].remove(target["rendering_id"])
    audit_service.create_audit_record(
        unit,
        before_hash=registry_service.file_hash(before),
        after_hash=registry_service.file_hash(unit),
        summary="Promote rendering to canonical",
        rationale=f"Approved by {reviewer_role}:{reviewer}",
        created_by=reviewer,
        entity_type="rendering",
        entity_id=rendering_id_value,
        review_signoff={"reviewer": reviewer, "role": reviewer_role},
    )
    registry_service.save_unit(unit)
    return target


def demote_rendering(rendering_id_value: str) -> dict[str, Any]:
    unit_id = ".".join(rendering_id_value.split(".")[1:4])
    before, unit = registry_service.update_unit(unit_id, lambda existing: existing)
    for rendering in unit.get("renderings", []):
        if rendering["rendering_id"] == rendering_id_value:
            rendering["status"] = "accepted_as_alternate"
            if rendering_id_value in unit.get("canonical_rendering_ids", []):
                unit["canonical_rendering_ids"].remove(rendering_id_value)
            if rendering_id_value not in unit.get("alternate_rendering_ids", []):
                unit["alternate_rendering_ids"].append(rendering_id_value)
            audit_service.create_audit_record(
                unit,
                before_hash=registry_service.file_hash(before),
                after_hash=registry_service.file_hash(unit),
                summary="Demote canonical rendering",
                rationale="manual demotion",
                created_by="api",
                entity_type="rendering",
                entity_id=rendering_id_value,
            )
            registry_service.save_unit(unit)
            return rendering
    raise NotFoundError(rendering_id_value)
