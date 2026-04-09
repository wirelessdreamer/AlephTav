from __future__ import annotations

from app.core.ids import issue_link_id, pr_link_id
from app.services import audit_service, registry_service


def link_issue(unit_id: str, issue_number: int) -> dict[str, str]:
    before, unit = registry_service.update_unit(unit_id, lambda existing: existing)
    link_id = issue_link_id(issue_number)
    if link_id not in unit.get("issue_links", []):
        unit.setdefault("issue_links", []).append(link_id)
    audit_service.create_audit_record(
        unit,
        before_hash=registry_service.file_hash(before),
        after_hash=registry_service.file_hash(unit),
        summary="Link issue",
        rationale=f"Linked issue #{issue_number}",
        created_by="github-link-service",
        triggered_by_issue=link_id,
    )
    registry_service.save_unit(unit)
    return {"unit_id": unit_id, "issue_link_id": link_id}


def link_pr(unit_id: str, pr_number: int) -> dict[str, str]:
    before, unit = registry_service.update_unit(unit_id, lambda existing: existing)
    link_id = pr_link_id(pr_number)
    if link_id not in unit.get("pr_links", []):
        unit.setdefault("pr_links", []).append(link_id)
    audit_service.create_audit_record(
        unit,
        before_hash=registry_service.file_hash(before),
        after_hash=registry_service.file_hash(unit),
        summary="Link PR",
        rationale=f"Linked PR #{pr_number}",
        created_by="github-link-service",
        triggered_by_pr=link_id,
    )
    registry_service.save_unit(unit)
    return {"unit_id": unit_id, "pr_link_id": link_id}
