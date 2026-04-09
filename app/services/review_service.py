from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.core.ids import decision_id
from app.services import audit_service, registry_service, rendering_service


def add_review_decision(target_id: str, decision: str, reviewer: str, reviewer_role: str, notes: str = "") -> dict[str, Any]:
    unit_id = ".".join(target_id.split(".")[1:4])
    before, unit = registry_service.update_unit(unit_id, lambda existing: existing)
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
    registry_service.save_unit(unit)
    if decision == "accept-alternate":
        rendering_service.update_rendering(target_id, {"status": "accepted_as_alternate", "rationale": notes}, created_by=reviewer)
    elif decision == "reject":
        rendering_service.update_rendering(target_id, {"status": "rejected", "rationale": notes}, created_by=reviewer)
    return record
