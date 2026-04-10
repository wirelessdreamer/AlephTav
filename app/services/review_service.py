from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.core.errors import ReviewRequiredError, ValidationError
from app.core.ids import decision_id
from app.services import audit_service, registry_service, rendering_service

REVIEWER_ROLES = (
    "lexical reviewer",
    "Hebrew reviewer",
    "alignment reviewer",
    "lyric reviewer",
    "theology reviewer",
    "release reviewer",
)


def review_policy(project: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = project or registry_service.load_project()
    policy = dict(payload.get("review_policy", {}))
    policy.setdefault("canonical_required_approvals", 2)
    policy.setdefault("alternate_required_approvals", 1)
    policy.setdefault("release_required_role", "release reviewer")
    policy.setdefault("reviewer_roles", list(REVIEWER_ROLES))
    return policy


def validate_reviewer_identity(reviewer: str, reviewer_role: str, project: dict[str, Any] | None = None) -> tuple[str, str]:
    normalized_reviewer = reviewer.strip()
    normalized_role = reviewer_role.strip()
    if not normalized_reviewer:
        raise ValidationError("reviewer is required")
    if normalized_role not in review_policy(project)["reviewer_roles"]:
        raise ValidationError(f"invalid reviewer role: {normalized_role}")
    return normalized_reviewer, normalized_role


def _approver_entries(decisions: list[dict[str, Any]], accepted_decisions: set[str]) -> list[dict[str, str]]:
    unique: dict[str, dict[str, str]] = {}
    for decision in decisions:
        if decision["decision"] not in accepted_decisions:
            continue
        unique[decision["reviewer"]] = {
            "reviewer": decision["reviewer"],
            "reviewer_role": decision["reviewer_role"],
        }
    return sorted(unique.values(), key=lambda item: item["reviewer"])


def summarize_rendering_review(unit: dict[str, Any], target_id: str, rendering: dict[str, Any] | None = None) -> dict[str, Any]:
    project = registry_service.load_project()
    policy = review_policy(project)
    target = rendering or next(item for item in unit.get("renderings", []) if item["rendering_id"] == target_id)
    decisions = [item for item in unit.get("review_decisions", []) if item["target_id"] == target_id]
    existing = dict(target.get("review_signoff", {}))
    approvals = _approver_entries(decisions, {"approve"})
    alternate_approvals = _approver_entries(decisions, {"approve", "accept-alternate"})
    release_signoff = dict(existing.get("release_signoff", {})) if isinstance(existing.get("release_signoff"), dict) else {}
    has_release_signoff = release_signoff.get("role") == policy["release_required_role"] and bool(release_signoff.get("reviewer"))
    approval_count = max(len(approvals), int(existing.get("approval_count", 0) or 0))
    alternate_approval_count = max(len(alternate_approvals), int(existing.get("alternate_approval_count", 0) or 0))
    canonical_required = int(policy["canonical_required_approvals"])
    alternate_required = int(policy["alternate_required_approvals"])
    eligible_for_alternate = alternate_approval_count >= alternate_required
    eligible_for_canonical = approval_count >= canonical_required
    latest_decision = max(decisions, key=lambda item: item["timestamp"], default=None)

    status = "unreviewed"
    if target["status"] == "rejected" or (latest_decision and latest_decision["decision"] == "reject"):
        status = "rejected"
    elif latest_decision and latest_decision["decision"] == "request_changes":
        status = "changes_requested"
    elif target["status"] == "canonical" and eligible_for_canonical and has_release_signoff:
        status = "canonical_signed_off"
    elif eligible_for_canonical:
        status = "approved_for_canonical"
    elif target["status"] == "accepted_as_alternate" or eligible_for_alternate:
        status = "approved_for_alternate"
    elif decisions:
        status = "under_review"

    return {
        "status": status,
        "approval_count": approval_count,
        "alternate_approval_count": alternate_approval_count,
        "required_approvals": {
            "alternate": alternate_required,
            "canonical": canonical_required,
        },
        "approvers": existing.get("approvers", approvals) or approvals,
        "alternate_approvers": existing.get("alternate_approvers", alternate_approvals) or alternate_approvals,
        "reviewer_roles": policy["reviewer_roles"],
        "release_required_role": policy["release_required_role"],
        "has_release_signoff": has_release_signoff,
        "release_signoff": release_signoff,
        "eligible_for_alternate": eligible_for_alternate,
        "eligible_for_canonical": eligible_for_canonical,
        "publication_ready": target["status"] == "canonical" and eligible_for_canonical and has_release_signoff,
        "latest_decision": latest_decision["decision"] if latest_decision else None,
        "updated_at": latest_decision["timestamp"] if latest_decision else existing.get("updated_at"),
    }


def hydrate_unit_review_state(unit: dict[str, Any]) -> dict[str, Any]:
    for rendering in unit.get("renderings", []):
        rendering["review_signoff"] = summarize_rendering_review(unit, rendering["rendering_id"], rendering)
    return unit


def add_review_decision(target_id: str, decision: str, reviewer: str, reviewer_role: str, notes: str = "") -> dict[str, Any]:
    unit_id = ".".join(target_id.split(".")[1:4])
    before, unit = registry_service.update_unit(unit_id, lambda existing: existing)
    reviewer, reviewer_role = validate_reviewer_identity(reviewer, reviewer_role)
    existing_ids = [item["decision_id"] for item in unit.get("review_decisions", [])]
    record = {
        "decision_id": decision_id(unit_id, existing_ids),
        "target_id": target_id,
        "reviewer_role": reviewer_role,
        "reviewer": reviewer,
        "decision": decision,
        "notes": notes,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    unit.setdefault("review_decisions", []).append(record)
    audit_service.create_audit_record(
        unit,
        before_hash=registry_service.file_hash(before),
        after_hash=registry_service.file_hash(unit),
        summary=f"Review decision: {decision}",
        rationale=notes or f"{reviewer_role} {decision}",
        created_by=reviewer,
        entity_type="review_decision",
        entity_id=record["decision_id"],
        change_type="create",
        review_signoff={"decision": decision, "reviewer": reviewer, "role": reviewer_role},
    )
    hydrate_unit_review_state(unit)
    registry_service.save_unit(unit)
    if decision == "accept-alternate":
        summary = summarize_rendering_review(unit, target_id)
        if not summary["eligible_for_alternate"]:
            raise ReviewRequiredError("A qualified reviewer signoff is required before accepting an alternate")
        return rendering_service.update_rendering(target_id, {"status": "accepted_as_alternate", "rationale": notes}, created_by=reviewer)
    elif decision == "reject":
        return rendering_service.update_rendering(target_id, {"status": "rejected", "rationale": notes}, created_by=reviewer)
    elif decision == "request_changes":
        return rendering_service.update_rendering(target_id, {"status": "under_review", "rationale": notes or "changes requested"}, created_by=reviewer)
    return record
