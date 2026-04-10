from __future__ import annotations

from typing import Any

from app.core.errors import NotFoundError, ReviewRequiredError, ValidationError
from app.core.ids import rendering_id
from app.services import audit_service, registry_service


ALTERNATE_STATUSES = {"accepted_as_alternate", "proposed", "under_review", "rejected", "deprecated"}


def _rendering_unit_id(rendering_id_value: str) -> str:
    return ".".join(rendering_id_value.split(".")[1:4])


def _rendering_lookup(unit: dict[str, Any], rendering_id_value: str) -> dict[str, Any]:
    for rendering in unit.get("renderings", []):
        if rendering["rendering_id"] == rendering_id_value:
            return rendering
    raise NotFoundError(rendering_id_value)


def _sort_renderings(renderings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(renderings, key=lambda item: (item["layer"], item["status"] != "canonical", item["rendering_id"]))


def _sync_rendering_membership(unit: dict[str, Any]) -> None:
    canonical_ids = []
    alternate_ids = []
    canonical_by_layer: dict[str, str] = {}
    for rendering in _sort_renderings(unit.get("renderings", [])):
        if rendering["status"] == "canonical":
            previous = canonical_by_layer.get(rendering["layer"])
            if previous is not None:
                raise ValidationError(f"multiple canonical renderings for layer {rendering['layer']}")
            canonical_by_layer[rendering["layer"]] = rendering["rendering_id"]
            canonical_ids.append(rendering["rendering_id"])
            continue
        if rendering["status"] in ALTERNATE_STATUSES:
            alternate_ids.append(rendering["rendering_id"])
    unit["canonical_rendering_ids"] = canonical_ids
    unit["alternate_rendering_ids"] = alternate_ids


def _has_release_approval(rendering: dict[str, Any]) -> bool:
    return rendering["status"] in {"canonical", "accepted_as_alternate"}


def _matches_style_filter(rendering: dict[str, Any], style_filter: str | None) -> bool:
    if not style_filter:
        return True
    normalized = style_filter.casefold()
    style_goal = str(rendering.get("style_goal", "")).casefold()
    tags = {tag.casefold() for tag in rendering.get("style_tags", [])}
    metric_profile = str(rendering.get("metric_profile", "")).casefold()
    synonyms = {
        "most_literal": {"literal", "most-literal", "study_literal"},
        "best_lyric_flow": {"lyric-flow", "flow", "best-lyric-flow"},
        "best_meter_fit": {"meter-fit", "meter", "common-meter", "best-meter-fit"},
        "best_imagery_preservation": {"imagery", "imagery-preservation", "best-imagery-preservation"},
        "formal": {"formal", "liturgical"},
        "contemporary": {"contemporary", "modern"},
    }
    accepted = synonyms.get(normalized, {normalized.replace("_", "-"), normalized})
    return bool(accepted & tags) or style_goal in accepted or metric_profile in accepted


def list_renderings(
    unit_id: str,
    alternates_only: bool = False,
    layer: str | None = None,
    style_filter: str | None = None,
    release_approved_only: bool = False,
) -> list[dict[str, Any]]:
    unit = registry_service.load_unit(unit_id)
    _sync_rendering_membership(unit)
    renderings = unit.get("renderings", [])
    if alternates_only:
        renderings = [item for item in renderings if item["status"] in ALTERNATE_STATUSES]
    if layer:
        renderings = [item for item in renderings if item["layer"] == layer]
    if style_filter:
        renderings = [item for item in renderings if _matches_style_filter(item, style_filter)]
    if release_approved_only:
        renderings = [item for item in renderings if _has_release_approval(item)]
    return _sort_renderings(renderings)


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
    style_goal: str | None = None,
    metric_profile: str | None = None,
    issue_links: list[str] | None = None,
    pr_links: list[str] | None = None,
) -> dict[str, Any]:
    if status == "canonical":
        raise ReviewRequiredError("Create proposed or alternate renderings first, then promote after review")
    before, unit = registry_service.update_unit(unit_id, lambda existing: existing)
    hint = "alt"
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
        "style_goal": style_goal,
        "metric_profile": metric_profile,
        "issue_links": issue_links or [],
        "pr_links": pr_links or [],
    }
    unit.setdefault("renderings", []).append(item)
    _sync_rendering_membership(unit)
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
    unit_id = _rendering_unit_id(rendering_id_value)
    before, unit = registry_service.update_unit(unit_id, lambda existing: existing)
    rendering = _rendering_lookup(unit, rendering_id_value)
    previous_status = rendering["status"]
    rendering.update(payload)
    if rendering["status"] == "canonical":
        for candidate in unit.get("renderings", []):
            if candidate["rendering_id"] != rendering_id_value and candidate["layer"] == rendering["layer"] and candidate["status"] == "canonical":
                candidate["status"] = "accepted_as_alternate"
    elif previous_status == "canonical":
        replacement = next(
            (
                item
                for item in _sort_renderings(unit.get("renderings", []))
                if item["rendering_id"] != rendering_id_value and item["layer"] == rendering["layer"] and item["status"] == "canonical"
            ),
            None,
        )
        if replacement is None and payload.get("status") != "canonical":
            rendering["status"] = "accepted_as_alternate"
    _sync_rendering_membership(unit)
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


def _approvals_for(unit: dict[str, Any], target_id: str) -> int:
    return sum(1 for item in unit.get("review_decisions", []) if item["target_id"] == target_id and item["decision"] == "approve")


def promote_rendering(rendering_id_value: str, reviewer: str, reviewer_role: str) -> dict[str, Any]:
    unit_id = _rendering_unit_id(rendering_id_value)
    before, unit = registry_service.update_unit(unit_id, lambda existing: existing)
    if _approvals_for(unit, rendering_id_value) < registry_service.load_project()["review_policy"]["canonical_required_approvals"]:
        raise ReviewRequiredError("Human review is required before promotion to canonical")
    target = _rendering_lookup(unit, rendering_id_value)
    for rendering in unit.get("renderings", []):
        if rendering["rendering_id"] != target["rendering_id"] and rendering["layer"] == target["layer"] and rendering["status"] == "canonical":
            rendering["status"] = "accepted_as_alternate"
    target["status"] = "canonical"
    _sync_rendering_membership(unit)
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


def demote_rendering(rendering_id_value: str, created_by: str = "api") -> dict[str, Any]:
    unit_id = _rendering_unit_id(rendering_id_value)
    before, unit = registry_service.update_unit(unit_id, lambda existing: existing)
    rendering = _rendering_lookup(unit, rendering_id_value)
    rendering["status"] = "accepted_as_alternate"
    _sync_rendering_membership(unit)
    audit_service.create_audit_record(
        unit,
        before_hash=registry_service.file_hash(before),
        after_hash=registry_service.file_hash(unit),
        summary="Demote canonical rendering",
        rationale="manual demotion",
        created_by=created_by,
        entity_type="rendering",
        entity_id=rendering_id_value,
    )
    registry_service.save_unit(unit)
    return rendering


def set_alternate_status(
    rendering_id_value: str,
    status: str,
    rationale: str = "",
    created_by: str = "api",
) -> dict[str, Any]:
    if status not in ALTERNATE_STATUSES:
        raise ValidationError(f"invalid alternate status: {status}")
    rendering = _rendering_lookup(registry_service.load_unit(_rendering_unit_id(rendering_id_value)), rendering_id_value)
    if rendering["status"] == "canonical":
        raise ValidationError("canonical rendering must be demoted instead of using alternate actions")
    return update_rendering(
        rendering_id_value,
        {"status": status, "rationale": rationale or f"set alternate status to {status}"},
        created_by=created_by,
    )


def compare_renderings(unit_id: str, left_id: str, right_id: str) -> dict[str, Any]:
    unit = registry_service.load_unit(unit_id)
    left = _rendering_lookup(unit, left_id)
    right = _rendering_lookup(unit, right_id)
    return {
        "unit_id": unit_id,
        "left": left,
        "right": right,
        "comparison": {
            "same_layer": left["layer"] == right["layer"],
            "left_is_canonical": left["status"] == "canonical",
            "right_is_canonical": right["status"] == "canonical",
        },
    }
