from __future__ import annotations

import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from jsonschema import Draft202012Validator

from app.core.errors import GenerationError, NotFoundError, ValidationError
from app.llm.adapters import build_adapter
from app.llm.base import GenerationRequest
from app.services import (
    alignment_service,
    audit_service,
    export_service,
    generation_service,
    lexical_service,
    registry_service,
    rendering_service,
    review_service,
    search_service,
    settings_service,
)

ActionExecutor = Callable[[dict[str, Any]], Any]

_SESSIONS: dict[str, dict[str, Any]] = {}
_CONFIRMATIONS: dict[str, dict[str, Any]] = {}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso_now() -> str:
    return _utcnow().isoformat()


def _preview_json(payload: Any, limit: int = 500) -> str:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    if len(text) <= limit:
        return text
    return f"{text[: limit - 3]}..."


def _model_profile(model_profile_id: str | None = None) -> dict[str, Any]:
    project = registry_service.load_project()
    target_id = model_profile_id or settings_service.load_settings().get("assistant", {}).get("model_profile_id") or project.get(
        "default_model_profile"
    )
    for item in project.get("local_model_profiles", []):
        if item["model_profile_id"] == target_id:
            return item
    raise NotFoundError(f"Unknown model profile: {target_id}")


def _required_properties(schema: dict[str, Any]) -> list[str]:
    return list(schema.get("required", []))


def _validate_payload(action: dict[str, Any], payload: dict[str, Any]) -> None:
    validator = Draft202012Validator(action["input_schema"])
    errors = sorted(validator.iter_errors(payload), key=lambda item: list(item.path))
    if errors:
        raise ValidationError(f"{action['action_id']} input invalid: {errors[0].message}")


def _navigate_route(payload: dict[str, Any]) -> dict[str, Any]:
    return {"route": payload["route"]}


def _navigate_unit(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "route": "workbench",
        "psalm_id": payload["psalm_id"],
        "unit_id": payload["unit_id"],
        "layer": payload.get("layer"),
    }


def _navigate_layer(payload: dict[str, Any]) -> dict[str, Any]:
    return {"route": "workbench", "layer": payload["layer"]}


def _patch_project(payload: dict[str, Any]) -> dict[str, Any]:
    project = registry_service.load_project()
    project.update(payload.get("patch", {}))
    registry_service.save_project(project)
    return project


def _list_psalms(_: dict[str, Any]) -> list[dict[str, Any]]:
    return [registry_service.load_psalm(psalm_id) for psalm_id in registry_service.list_psalm_ids()]


def _get_psalm(payload: dict[str, Any]) -> dict[str, Any]:
    return registry_service.load_psalm(payload["psalm_id"])


def _get_project(_: dict[str, Any]) -> dict[str, Any]:
    return registry_service.load_project()


def _get_unit(payload: dict[str, Any]) -> dict[str, Any]:
    return registry_service.load_unit(payload["unit_id"])


def _get_token(payload: dict[str, Any]) -> dict[str, Any]:
    return lexical_service.lexical_card(payload["token_id"])


def _search_concordance(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return lexical_service.search_concordance(payload["query"], field=payload.get("field", "lemma"))


def _advanced_search(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return search_service.advanced_search(
        payload["query"],
        scope=payload.get("scope", "all"),
        include_witnesses=payload.get("include_witnesses", False),
    )


def _preset_search(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return search_service.preset_view(payload["name"], release_id=payload.get("release_id"))


def _list_witnesses(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return search_service.list_witnesses(payload["unit_id"])


def _open_concerns(_: dict[str, Any]) -> dict[str, Any]:
    return audit_service.open_concerns()


def _unit_audit(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return audit_service.audit_for_unit(payload["unit_id"])


def _compare_renderings(payload: dict[str, Any]) -> dict[str, Any]:
    return rendering_service.compare_renderings(payload["unit_id"], payload["left_id"], payload["right_id"])


def _list_alternates(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return rendering_service.list_renderings(
        payload["unit_id"],
        alternates_only=True,
        layer=payload.get("layer"),
        style_filter=payload.get("style_filter"),
        release_approved_only=payload.get("release_approved_only", False),
    )


def _create_alignment(payload: dict[str, Any]) -> dict[str, Any]:
    return alignment_service.create_alignment(payload["unit_id"], payload)


def _update_alignment(payload: dict[str, Any]) -> dict[str, Any]:
    alignment_id = payload["alignment_id"]
    updates = {key: value for key, value in payload.items() if key != "alignment_id"}
    return alignment_service.update_alignment(alignment_id, updates)


def _delete_alignment(payload: dict[str, Any]) -> dict[str, Any]:
    return alignment_service.delete_alignment(payload["alignment_id"])


def _create_rendering(payload: dict[str, Any]) -> dict[str, Any]:
    return rendering_service.create_rendering(
        unit_id=payload["unit_id"],
        layer=payload["layer"],
        text=payload["text"],
        status=payload.get("status", "proposed"),
        rationale=payload.get("rationale", "assistant create rendering"),
        created_by=payload.get("created_by", "assistant"),
        style_tags=payload.get("style_tags"),
        target_spans=payload.get("target_spans"),
        alignment_ids=payload.get("alignment_ids"),
        drift_flags=payload.get("drift_flags"),
        metrics=payload.get("metrics"),
        provenance=payload.get("provenance"),
        style_goal=payload.get("style_goal"),
        metric_profile=payload.get("metric_profile"),
        issue_links=payload.get("issue_links"),
        pr_links=payload.get("pr_links"),
    )


def _update_rendering(payload: dict[str, Any]) -> dict[str, Any]:
    rendering_id = payload["rendering_id"]
    updates = {key: value for key, value in payload.items() if key != "rendering_id"}
    return rendering_service.update_rendering(rendering_id, updates)


def _promote_rendering(payload: dict[str, Any]) -> dict[str, Any]:
    return rendering_service.promote_rendering(
        payload["rendering_id"],
        reviewer=payload.get("reviewer", "assistant"),
        reviewer_role=payload.get("reviewer_role", "release reviewer"),
    )


def _demote_rendering(payload: dict[str, Any]) -> dict[str, Any]:
    return rendering_service.demote_rendering(payload["rendering_id"])


def _create_alternate(payload: dict[str, Any]) -> dict[str, Any]:
    return _create_rendering(payload)


def _review_action(payload: dict[str, Any]) -> dict[str, Any]:
    return review_service.add_review_decision(
        target_id=payload["target_id"],
        decision=payload["decision"],
        reviewer=payload.get("reviewer", "assistant"),
        reviewer_role=payload.get("reviewer_role", "alignment reviewer"),
        notes=payload.get("notes", ""),
    )


def _promote_alternate(payload: dict[str, Any]) -> dict[str, Any]:
    return rendering_service.promote_rendering(
        payload["rendering_id"],
        reviewer=payload.get("reviewer", "assistant"),
        reviewer_role=payload.get("reviewer_role", "release reviewer"),
    )


def _set_alternate_status(payload: dict[str, Any], status: str) -> dict[str, Any]:
    return rendering_service.set_alternate_status(
        payload["rendering_id"],
        status,
        rationale=payload.get("rationale", f"{status} alternate"),
        created_by=payload.get("created_by", "assistant"),
    )


def _export_release(payload: dict[str, Any]) -> dict[str, Any]:
    return {"path": str(export_service.export_release(payload["release_id"]))}


def _generate_job(payload: dict[str, Any]) -> dict[str, Any]:
    return generation_service.generate_for_unit(
        unit_id=payload["unit_id"],
        layer=payload["layer"],
        style_profile=payload.get("style_profile", "study_literal"),
        model_profile=payload.get("model_profile"),
        seed=payload.get("seed", 42),
        candidate_count=payload.get("candidate_count", 1),
    )


def _get_job(payload: dict[str, Any]) -> dict[str, Any]:
    return generation_service.get_job(payload["job_id"])


ACTION_DEFINITIONS: list[dict[str, Any]] = [
    {
        "action_id": "navigate.route",
        "label": "Navigate Route",
        "description": "Navigate to a top-level app route.",
        "kind": "client",
        "input_schema": {
            "type": "object",
            "properties": {"route": {"type": "string", "enum": ["welcome", "workbench"]}},
            "required": ["route"],
            "additionalProperties": False,
        },
        "executor": _navigate_route,
        "summary": lambda payload: f"Navigate to {payload['route']}",
    },
    {
        "action_id": "navigate.unit",
        "label": "Navigate To Unit",
        "description": "Open the workbench on a specific psalm and unit.",
        "kind": "client",
        "input_schema": {
            "type": "object",
            "properties": {
                "psalm_id": {"type": "string"},
                "unit_id": {"type": "string"},
                "layer": {"type": "string"},
            },
            "required": ["psalm_id", "unit_id"],
            "additionalProperties": False,
        },
        "executor": _navigate_unit,
        "summary": lambda payload: f"Open {payload['unit_id']}",
    },
    {
        "action_id": "navigate.layer",
        "label": "Switch Layer",
        "description": "Switch the active workbench layer.",
        "kind": "client",
        "input_schema": {
            "type": "object",
            "properties": {"layer": {"type": "string"}},
            "required": ["layer"],
            "additionalProperties": False,
        },
        "executor": _navigate_layer,
        "summary": lambda payload: f"Switch layer to {payload['layer']}",
    },
    {
        "action_id": "project.get",
        "label": "Get Project",
        "description": "Load the project configuration.",
        "kind": "read",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
        "executor": _get_project,
        "summary": lambda _: "Load project",
    },
    {
        "action_id": "project.patch",
        "label": "Patch Project",
        "description": "Update top-level project fields.",
        "kind": "write",
        "input_schema": {
            "type": "object",
            "properties": {"patch": {"type": "object"}},
            "required": ["patch"],
            "additionalProperties": False,
        },
        "executor": _patch_project,
        "summary": lambda payload: f"Patch project with {', '.join(sorted(payload['patch'].keys()))}",
    },
    {
        "action_id": "psalms.list",
        "label": "List Psalms",
        "description": "List all psalms in the project.",
        "kind": "read",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
        "executor": _list_psalms,
        "summary": lambda _: "List psalms",
    },
    {
        "action_id": "psalm.get",
        "label": "Get Psalm",
        "description": "Load a psalm and its units.",
        "kind": "read",
        "input_schema": {
            "type": "object",
            "properties": {"psalm_id": {"type": "string"}},
            "required": ["psalm_id"],
            "additionalProperties": False,
        },
        "executor": _get_psalm,
        "summary": lambda payload: f"Load psalm {payload['psalm_id']}",
    },
    {
        "action_id": "unit.get",
        "label": "Get Unit",
        "description": "Load a unit and its workbench payload.",
        "kind": "read",
        "input_schema": {
            "type": "object",
            "properties": {"unit_id": {"type": "string"}},
            "required": ["unit_id"],
            "additionalProperties": False,
        },
        "executor": _get_unit,
        "summary": lambda payload: f"Load unit {payload['unit_id']}",
    },
    {
        "action_id": "token.get",
        "label": "Get Token Card",
        "description": "Load a lexical token card.",
        "kind": "read",
        "input_schema": {
            "type": "object",
            "properties": {"token_id": {"type": "string"}},
            "required": ["token_id"],
            "additionalProperties": False,
        },
        "executor": _get_token,
        "summary": lambda payload: f"Inspect token {payload['token_id']}",
    },
    {
        "action_id": "search.concordance",
        "label": "Search Concordance",
        "description": "Search indexed token fields.",
        "kind": "read",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}, "field": {"type": "string"}},
            "required": ["query"],
            "additionalProperties": False,
        },
        "executor": _search_concordance,
        "summary": lambda payload: f"Search concordance for {payload['query']}",
    },
    {
        "action_id": "search.advanced",
        "label": "Advanced Search",
        "description": "Search renderings, notes, issues, and witnesses.",
        "kind": "read",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "scope": {"type": "string"},
                "include_witnesses": {"type": "boolean"},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        "executor": _advanced_search,
        "summary": lambda payload: f"Advanced search for {payload['query']}",
    },
    {
        "action_id": "search.preset",
        "label": "Preset Search",
        "description": "Run a canned search preset.",
        "kind": "read",
        "input_schema": {
            "type": "object",
            "properties": {"name": {"type": "string"}, "release_id": {"type": "string"}},
            "required": ["name"],
            "additionalProperties": False,
        },
        "executor": _preset_search,
        "summary": lambda payload: f"Run preset {payload['name']}",
    },
    {
        "action_id": "unit.witnesses",
        "label": "List Witnesses",
        "description": "Load source witnesses for a unit.",
        "kind": "read",
        "input_schema": {
            "type": "object",
            "properties": {"unit_id": {"type": "string"}},
            "required": ["unit_id"],
            "additionalProperties": False,
        },
        "executor": _list_witnesses,
        "summary": lambda payload: f"Load witnesses for {payload['unit_id']}",
    },
    {
        "action_id": "audit.open_concerns",
        "label": "Open Concerns",
        "description": "Load unresolved drift, alignment, and provenance warnings.",
        "kind": "read",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
        "executor": _open_concerns,
        "summary": lambda _: "Load open concerns",
    },
    {
        "action_id": "audit.unit",
        "label": "Unit Audit",
        "description": "Load audit records for a unit.",
        "kind": "read",
        "input_schema": {
            "type": "object",
            "properties": {"unit_id": {"type": "string"}},
            "required": ["unit_id"],
            "additionalProperties": False,
        },
        "executor": _unit_audit,
        "summary": lambda payload: f"Load audit for {payload['unit_id']}",
    },
    {
        "action_id": "renderings.compare",
        "label": "Compare Renderings",
        "description": "Compare two renderings inside a unit.",
        "kind": "read",
        "input_schema": {
            "type": "object",
            "properties": {
                "unit_id": {"type": "string"},
                "left_id": {"type": "string"},
                "right_id": {"type": "string"},
            },
            "required": ["unit_id", "left_id", "right_id"],
            "additionalProperties": False,
        },
        "executor": _compare_renderings,
        "summary": lambda payload: f"Compare {payload['left_id']} vs {payload['right_id']}",
    },
    {
        "action_id": "alternates.list",
        "label": "List Alternates",
        "description": "List alternate renderings for a unit.",
        "kind": "read",
        "input_schema": {
            "type": "object",
            "properties": {
                "unit_id": {"type": "string"},
                "layer": {"type": "string"},
                "style_filter": {"type": "string"},
                "release_approved_only": {"type": "boolean"},
            },
            "required": ["unit_id"],
            "additionalProperties": False,
        },
        "executor": _list_alternates,
        "summary": lambda payload: f"List alternates for {payload['unit_id']}",
    },
    {
        "action_id": "alignments.create",
        "label": "Create Alignment",
        "description": "Create an alignment between tokens and spans.",
        "kind": "write",
        "input_schema": {
            "type": "object",
            "properties": {
                "unit_id": {"type": "string"},
                "layer": {"type": "string"},
                "source_token_ids": {"type": "array", "items": {"type": "string"}},
                "target_span_ids": {"type": "array", "items": {"type": "string"}},
                "alignment_type": {"type": "string"},
                "confidence": {"type": "number"},
                "notes": {"type": "string"},
            },
            "required": ["unit_id", "layer", "source_token_ids", "target_span_ids", "alignment_type", "confidence"],
            "additionalProperties": False,
        },
        "executor": _create_alignment,
        "summary": lambda payload: f"Create alignment in {payload['unit_id']}",
    },
    {
        "action_id": "alignments.update",
        "label": "Update Alignment",
        "description": "Update an existing alignment.",
        "kind": "write",
        "input_schema": {
            "type": "object",
            "properties": {
                "alignment_id": {"type": "string"},
                "layer": {"type": "string"},
                "source_token_ids": {"type": "array", "items": {"type": "string"}},
                "target_span_ids": {"type": "array", "items": {"type": "string"}},
                "alignment_type": {"type": "string"},
                "confidence": {"type": "number"},
                "notes": {"type": "string"},
            },
            "required": ["alignment_id"],
            "additionalProperties": False,
        },
        "executor": _update_alignment,
        "summary": lambda payload: f"Update alignment {payload['alignment_id']}",
    },
    {
        "action_id": "alignments.delete",
        "label": "Delete Alignment",
        "description": "Delete an existing alignment.",
        "kind": "write",
        "input_schema": {
            "type": "object",
            "properties": {"alignment_id": {"type": "string"}},
            "required": ["alignment_id"],
            "additionalProperties": False,
        },
        "executor": _delete_alignment,
        "summary": lambda payload: f"Delete alignment {payload['alignment_id']}",
    },
    {
        "action_id": "renderings.create",
        "label": "Create Rendering",
        "description": "Create a new rendering or alternate.",
        "kind": "write",
        "input_schema": {
            "type": "object",
            "properties": {
                "unit_id": {"type": "string"},
                "layer": {"type": "string"},
                "text": {"type": "string"},
                "status": {"type": "string"},
                "rationale": {"type": "string"},
                "created_by": {"type": "string"},
                "style_tags": {"type": "array", "items": {"type": "string"}},
                "alignment_ids": {"type": "array", "items": {"type": "string"}},
                "style_goal": {"type": "string"},
                "metric_profile": {"type": "string"},
            },
            "required": ["unit_id", "layer", "text"],
            "additionalProperties": True,
        },
        "executor": _create_rendering,
        "summary": lambda payload: f"Create {payload['layer']} rendering in {payload['unit_id']}",
    },
    {
        "action_id": "renderings.update",
        "label": "Update Rendering",
        "description": "Patch an existing rendering.",
        "kind": "write",
        "input_schema": {
            "type": "object",
            "properties": {"rendering_id": {"type": "string"}},
            "required": ["rendering_id"],
            "additionalProperties": True,
        },
        "executor": _update_rendering,
        "summary": lambda payload: f"Update rendering {payload['rendering_id']}",
    },
    {
        "action_id": "renderings.promote",
        "label": "Promote Rendering",
        "description": "Promote a rendering to canonical.",
        "kind": "write",
        "input_schema": {
            "type": "object",
            "properties": {
                "rendering_id": {"type": "string"},
                "reviewer": {"type": "string"},
                "reviewer_role": {"type": "string"},
            },
            "required": ["rendering_id"],
            "additionalProperties": False,
        },
        "executor": _promote_rendering,
        "summary": lambda payload: f"Promote rendering {payload['rendering_id']}",
    },
    {
        "action_id": "renderings.demote",
        "label": "Demote Rendering",
        "description": "Demote a canonical rendering.",
        "kind": "write",
        "input_schema": {
            "type": "object",
            "properties": {"rendering_id": {"type": "string"}},
            "required": ["rendering_id"],
            "additionalProperties": False,
        },
        "executor": _demote_rendering,
        "summary": lambda payload: f"Demote rendering {payload['rendering_id']}",
    },
    {
        "action_id": "alternates.create",
        "label": "Create Alternate",
        "description": "Create a proposed alternate rendering.",
        "kind": "write",
        "input_schema": {
            "type": "object",
            "properties": {
                "unit_id": {"type": "string"},
                "layer": {"type": "string"},
                "text": {"type": "string"},
                "rationale": {"type": "string"},
                "created_by": {"type": "string"},
            },
            "required": ["unit_id", "layer", "text"],
            "additionalProperties": True,
        },
        "executor": _create_alternate,
        "summary": lambda payload: f"Create alternate in {payload['unit_id']}",
    },
    {
        "action_id": "alternates.accept",
        "label": "Accept Alternate",
        "description": "Accept an alternate without promoting it to canonical.",
        "kind": "write",
        "input_schema": {
            "type": "object",
            "properties": {"rendering_id": {"type": "string"}, "reviewer": {"type": "string"}, "reviewer_role": {"type": "string"}, "notes": {"type": "string"}},
            "required": ["rendering_id"],
            "additionalProperties": False,
        },
        "executor": lambda payload: _review_action({**payload, "target_id": payload["rendering_id"], "decision": "accept-alternate"}),
        "summary": lambda payload: f"Accept alternate {payload['rendering_id']}",
    },
    {
        "action_id": "alternates.reject",
        "label": "Reject Alternate",
        "description": "Reject an alternate rendering.",
        "kind": "write",
        "input_schema": {
            "type": "object",
            "properties": {"rendering_id": {"type": "string"}, "reviewer": {"type": "string"}, "reviewer_role": {"type": "string"}, "notes": {"type": "string"}},
            "required": ["rendering_id"],
            "additionalProperties": False,
        },
        "executor": lambda payload: _review_action({**payload, "target_id": payload["rendering_id"], "decision": "reject"}),
        "summary": lambda payload: f"Reject alternate {payload['rendering_id']}",
    },
    {
        "action_id": "alternates.deprecate",
        "label": "Deprecate Alternate",
        "description": "Deprecate an alternate rendering.",
        "kind": "write",
        "input_schema": {
            "type": "object",
            "properties": {"rendering_id": {"type": "string"}, "rationale": {"type": "string"}, "created_by": {"type": "string"}},
            "required": ["rendering_id"],
            "additionalProperties": False,
        },
        "executor": lambda payload: _set_alternate_status(payload, "deprecated"),
        "summary": lambda payload: f"Deprecate alternate {payload['rendering_id']}",
    },
    {
        "action_id": "alternates.promote",
        "label": "Promote Alternate",
        "description": "Promote an alternate to canonical.",
        "kind": "write",
        "input_schema": {
            "type": "object",
            "properties": {"rendering_id": {"type": "string"}, "reviewer": {"type": "string"}, "reviewer_role": {"type": "string"}},
            "required": ["rendering_id"],
            "additionalProperties": False,
        },
        "executor": _promote_alternate,
        "summary": lambda payload: f"Promote alternate {payload['rendering_id']}",
    },
    {
        "action_id": "review.submit",
        "label": "Submit Review",
        "description": "Submit an approval or rejection decision.",
        "kind": "write",
        "input_schema": {
            "type": "object",
            "properties": {
                "target_id": {"type": "string"},
                "decision": {"type": "string"},
                "reviewer": {"type": "string"},
                "reviewer_role": {"type": "string"},
                "notes": {"type": "string"},
            },
            "required": ["target_id", "decision"],
            "additionalProperties": False,
        },
        "executor": _review_action,
        "summary": lambda payload: f"Submit {payload['decision']} for {payload['target_id']}",
    },
    {
        "action_id": "export.release",
        "label": "Export Release",
        "description": "Build a release export bundle.",
        "kind": "write",
        "input_schema": {
            "type": "object",
            "properties": {"release_id": {"type": "string"}},
            "required": ["release_id"],
            "additionalProperties": False,
        },
        "executor": _export_release,
        "summary": lambda payload: f"Export release {payload['release_id']}",
    },
    {
        "action_id": "jobs.generate",
        "label": "Generate Layer",
        "description": "Run model generation for a unit layer.",
        "kind": "write",
        "input_schema": {
            "type": "object",
            "properties": {
                "unit_id": {"type": "string"},
                "layer": {"type": "string"},
                "style_profile": {"type": "string"},
                "model_profile": {"type": "string"},
                "seed": {"type": "integer"},
                "candidate_count": {"type": "integer"},
            },
            "required": ["unit_id", "layer"],
            "additionalProperties": False,
        },
        "executor": _generate_job,
        "summary": lambda payload: f"Generate {payload['layer']} for {payload['unit_id']}",
    },
    {
        "action_id": "jobs.get",
        "label": "Get Generation Job",
        "description": "Load a saved generation job.",
        "kind": "read",
        "input_schema": {
            "type": "object",
            "properties": {"job_id": {"type": "string"}},
            "required": ["job_id"],
            "additionalProperties": False,
        },
        "executor": _get_job,
        "summary": lambda payload: f"Load generation job {payload['job_id']}",
    },
]

_ACTION_INDEX = {item["action_id"]: item for item in ACTION_DEFINITIONS}


def _public_action_definition(action: dict[str, Any]) -> dict[str, Any]:
    return {
        "action_id": action["action_id"],
        "label": action["label"],
        "description": action["description"],
        "kind": action["kind"],
        "requires_confirmation": action["kind"] == "write",
        "input_schema": action["input_schema"],
        "required_fields": _required_properties(action["input_schema"]),
    }


def list_actions() -> list[dict[str, Any]]:
    return [_public_action_definition(action) for action in ACTION_DEFINITIONS]


def _execute_action(action_id: str, payload: dict[str, Any]) -> Any:
    action = _ACTION_INDEX.get(action_id)
    if action is None:
        raise NotFoundError(f"Unknown assistant action: {action_id}")
    _validate_payload(action, payload)
    return action["executor"](payload)


def preview_action(action_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    action = _ACTION_INDEX.get(action_id)
    if action is None:
        raise NotFoundError(f"Unknown assistant action: {action_id}")
    if action["kind"] != "write":
        raise ValidationError(f"{action_id} does not require confirmation")
    _validate_payload(action, payload)
    token = secrets.token_urlsafe(24)
    expires_at = _utcnow() + timedelta(minutes=10)
    _CONFIRMATIONS[token] = {
        "action_id": action_id,
        "payload": payload,
        "expires_at": expires_at,
    }
    return {
        "action_id": action_id,
        "kind": action["kind"],
        "summary": action["summary"](payload),
        "input": payload,
        "input_preview": _preview_json(payload),
        "confirmation_token": token,
        "expires_at": expires_at.isoformat(),
    }


def execute_action(action_id: str, payload: dict[str, Any], confirmation_token: str | None = None) -> dict[str, Any]:
    action = _ACTION_INDEX.get(action_id)
    if action is None:
        raise NotFoundError(f"Unknown assistant action: {action_id}")
    if action["kind"] == "write":
        if not confirmation_token:
            raise ValidationError(f"{action_id} requires confirmation")
        confirmation = _CONFIRMATIONS.get(confirmation_token)
        if confirmation is None:
            raise ValidationError("Confirmation token is invalid")
        if confirmation["expires_at"] < _utcnow():
            _CONFIRMATIONS.pop(confirmation_token, None)
            raise ValidationError("Confirmation token has expired")
        if confirmation["action_id"] != action_id or confirmation["payload"] != payload:
            raise ValidationError("Confirmation token does not match the requested action")
        _CONFIRMATIONS.pop(confirmation_token, None)
    result = _execute_action(action_id, payload)
    return {
        "action_id": action_id,
        "kind": action["kind"],
        "summary": action["summary"](payload),
        "result": result,
    }


def create_session() -> dict[str, Any]:
    session_id = f"asst.{secrets.token_hex(8)}"
    session = {"session_id": session_id, "created_at": _iso_now(), "messages": []}
    _SESSIONS[session_id] = session
    return session


def _get_session(session_id: str) -> dict[str, Any]:
    session = _SESSIONS.get(session_id)
    if session is None:
        raise NotFoundError(f"Assistant session not found: {session_id}")
    return session


def _tool_prompt() -> str:
    return json.dumps(list_actions(), ensure_ascii=False, indent=2)


def _context_prompt(context: dict[str, Any] | None) -> str:
    return json.dumps(context or {}, ensure_ascii=False, indent=2)


def _conversation_prompt(session: dict[str, Any]) -> str:
    return json.dumps(session["messages"][-8:], ensure_ascii=False, indent=2)


def _assistant_contract() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "reply": {"type": "string"},
            "tool_calls": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "action_id": {"type": "string"},
                        "input": {"type": "object"},
                    },
                    "required": ["action_id", "input"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["reply", "tool_calls"],
        "additionalProperties": False,
    }


def _run_assistant_model(session: dict[str, Any], message: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
    profile = _model_profile()
    adapter = build_adapter(profile)
    prompt = (
        "You are the AlephTav assistant. Use the available tools when needed.\n"
        "Rules:\n"
        "- Prefer precise tool calls over guessing.\n"
        "- Use client navigation actions when the user wants the UI to move.\n"
        "- Use write actions only when the user clearly wants a state change.\n"
        "- Keep reply concise.\n\n"
        f"Context:\n{_context_prompt(context)}\n\n"
        f"Tools:\n{_tool_prompt()}\n\n"
        f"Recent conversation:\n{_conversation_prompt(session)}\n\n"
        f"User message:\n{message}"
    )
    generation = adapter.generate_json(
        GenerationRequest(
            prompt=prompt,
            contract=_assistant_contract(),
            model=profile["model"],
            seed=7,
            temperature=0.1,
            max_tokens=700,
            timeout_seconds=profile.get("timeout_seconds", 30),
            metadata={"feature": "assistant-chat"},
        )
    )
    payload = generation.payload
    if not isinstance(payload, dict) or "reply" not in payload or "tool_calls" not in payload:
        raise GenerationError("Assistant model returned an invalid response payload")
    return payload


def _fallback_response(message: str) -> dict[str, Any]:
    lower = message.lower()
    if "open" in lower and "workbench" in lower:
        return {"reply": "Opening the workbench.", "tool_calls": [{"action_id": "navigate.route", "input": {"route": "workbench"}}]}
    if "project" in lower:
        return {"reply": "Loading the project configuration.", "tool_calls": [{"action_id": "project.get", "input": {}}]}
    return {"reply": "I can inspect the project, navigate the workbench, and prepare write actions for confirmation.", "tool_calls": []}


def post_message(session_id: str, message: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
    session = _get_session(session_id)
    user_message = {"role": "user", "content": message, "created_at": _iso_now()}
    session["messages"].append(user_message)

    try:
        model_response = _run_assistant_model(session, message, context)
    except Exception:
        model_response = _fallback_response(message)

    tool_results: list[dict[str, Any]] = []
    pending_actions: list[dict[str, Any]] = []
    client_actions: list[dict[str, Any]] = []
    for tool_call in model_response.get("tool_calls", []):
        action_id = tool_call.get("action_id")
        payload = tool_call.get("input", {})
        action = _ACTION_INDEX.get(action_id)
        if action is None:
            tool_results.append({"action_id": action_id, "error": f"Unknown action {action_id}"})
            continue
        try:
            if action["kind"] == "read":
                result = execute_action(action_id, payload)
                tool_results.append(result)
            elif action["kind"] == "write":
                pending_actions.append(preview_action(action_id, payload))
            else:
                _validate_payload(action, payload)
                client_actions.append(
                    {
                        "action_id": action_id,
                        "kind": action["kind"],
                        "summary": action["summary"](payload),
                        "payload": action["executor"](payload),
                    }
                )
        except Exception as error:
            tool_results.append({"action_id": action_id, "error": str(error)})

    assistant_message = {
        "role": "assistant",
        "content": model_response.get("reply", ""),
        "created_at": _iso_now(),
        "tool_results": tool_results,
        "pending_actions": pending_actions,
        "client_actions": client_actions,
    }
    session["messages"].append(assistant_message)
    return {"session_id": session_id, "message": assistant_message}
