from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from app.core.errors import NotFoundError, ReviewRequiredError, ValidationError
from app.core.ids import decision_id, unit_id_from_entity_id
from app.services import audit_service, registry_service, rendering_service
from app.services.review_evidence_service import is_legacy_review_decision

REVIEWER_ROLES = (
    "lexical reviewer",
    "Hebrew reviewer",
    "alignment reviewer",
    "lyric reviewer",
    "theology reviewer",
    "release reviewer",
)


def has_versioned_review_decisions(unit: dict[str, Any], target_id: str) -> bool:
    """Versioned targets cannot fall back to the unauthenticated legacy engine."""
    return any(
        isinstance(item, dict)
        and item.get("target_id") == target_id
        and "contract_version" in item
        for item in unit.get("review_decisions", [])
    )


def legacy_review_decisions(unit: dict[str, Any], target_id: str) -> list[dict[str, Any]]:
    if has_versioned_review_decisions(unit, target_id):
        return []
    return [
        item
        for item in unit.get("review_decisions", [])
        if is_legacy_review_decision(item) and item.get("target_id") == target_id
    ]


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
    versioned = has_versioned_review_decisions(unit, target_id)
    decisions = legacy_review_decisions(unit, target_id)
    existing = {} if versioned else dict(target.get("review_signoff", {}))
    approvals = _approver_entries(decisions, {"approve"})
    alternate_approvals = _approver_entries(decisions, {"approve", "accept-alternate"})
    release_signoff = dict(existing.get("release_signoff", {})) if isinstance(existing.get("release_signoff"), dict) else {}
    has_release_signoff = release_signoff.get("role") == policy["release_required_role"] and bool(release_signoff.get("reviewer"))
    approval_count = max(len(approvals), int(existing.get("approval_count", 0) or 0))
    alternate_approval_count = max(len(alternate_approvals), int(existing.get("alternate_approval_count", 0) or 0))
    canonical_required = int(policy["canonical_required_approvals"])
    alternate_required = int(policy["alternate_required_approvals"])
    eligible_for_alternate = not versioned and alternate_approval_count >= alternate_required
    eligible_for_canonical = not versioned and approval_count >= canonical_required
    latest_decision = max(decisions, key=lambda item: item["timestamp"], default=None)

    status = "unreviewed"
    if versioned:
        status = "under_review"
    elif target["status"] == "rejected" or (
        latest_decision and latest_decision["decision"] == "reject"
    ):
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
        **({"evidence_contract_status": "versioned_pending_activation"} if versioned else {}),
    }


def hydrate_unit_review_state(unit: dict[str, Any]) -> dict[str, Any]:
    for rendering in unit.get("renderings", []):
        rendering["review_signoff"] = summarize_rendering_review(unit, rendering["rendering_id"], rendering)
    return unit


def add_review_decision(
    target_id: str, decision: str, reviewer: str, reviewer_role: str, notes: str = ""
) -> dict[str, Any]:
    if decision not in {"approve", "accept-alternate", "reject", "request_changes"}:
        raise ValidationError(f"invalid review decision: {decision}")
    reviewer, reviewer_role = validate_reviewer_identity(reviewer, reviewer_role)
    unit_id = unit_id_from_entity_id("rendering_id", target_id)
    unit = registry_service.load_unit(unit_id)
    target = next(
        (item for item in unit.get("renderings", []) if item["rendering_id"] == target_id),
        None,
    )
    if target is None:
        raise NotFoundError(target_id)
    if has_versioned_review_decisions(unit, target_id):
        raise ReviewRequiredError(
            "Versioned evidence requires an authenticated versioned review workflow; "
            "legacy review cannot reattest or downgrade it"
        )
    if target["status"] == "canonical" and decision != "approve":
        raise ReviewRequiredError(
            "A canonical rendering changes only by promoting a reviewed alternate"
        )
    before = deepcopy(unit)
    existing_ids = [item["decision_id"] for item in unit.get("review_decisions", [])]
    record = {
        "decision_id": decision_id(unit_id, existing_ids),
        "target_id": target_id,
        "reviewer_role": reviewer_role,
        "reviewer": reviewer,
        "decision": decision,
        "notes": notes,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    unit.setdefault("review_decisions", []).append(record)
    if decision == "accept-alternate":
        summary = summarize_rendering_review(unit, target_id, target)
        if not summary["eligible_for_alternate"]:
            raise ReviewRequiredError(
                "A qualified reviewer signoff is required before accepting an alternate"
            )
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
        return rendering_service.set_alternate_status(
            target_id, "accepted_as_alternate", rationale=notes, created_by=reviewer
        )
    elif decision == "reject":
        return rendering_service.set_alternate_status(
            target_id, "rejected", rationale=notes, created_by=reviewer
        )
    elif decision == "request_changes":
        return rendering_service.set_alternate_status(
            target_id,
            "under_review",
            rationale=notes or "changes requested",
            created_by=reviewer,
        )
    return record
