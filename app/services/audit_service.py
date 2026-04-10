from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.core.ids import audit_id
from app.services import registry_service


def create_audit_record(
    unit: dict[str, Any],
    before_hash: str,
    after_hash: str,
    summary: str,
    rationale: str,
    created_by: str,
    entity_type: str = "unit",
    entity_id: str | None = None,
    change_type: str = "update",
    triggered_by_issue: str | None = None,
    triggered_by_pr: str | None = None,
    checks: list[str] | None = None,
    review_signoff: dict[str, Any] | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    existing_ids = [record["audit_id"] for record in unit.get("audit_records", [])]
    record = {
        "audit_id": audit_id(unit["unit_id"], existing_ids),
        "entity_type": entity_type,
        "entity_id": entity_id or unit["unit_id"],
        "change_type": change_type,
        "before_hash": before_hash,
        "after_hash": after_hash,
        "summary": summary,
        "rationale": rationale,
        "triggered_by_issue": triggered_by_issue,
        "triggered_by_pr": triggered_by_pr,
        "created_by": created_by,
        "created_at": created_at or datetime.now(timezone.utc).isoformat(),
        "checks": checks or [],
        "review_signoff": review_signoff or {},
    }
    unit.setdefault("audit_records", []).append(record)
    unit.setdefault("audit_ids", []).append(record["audit_id"])
    return record


def audit_for_unit(unit_id: str) -> list[dict[str, Any]]:
    unit = registry_service.load_unit(unit_id)
    return unit.get("audit_records", [])


def open_concerns() -> dict[str, Any]:
    uncovered_tokens: list[dict[str, Any]] = []
    unaligned_spans: list[dict[str, Any]] = []
    drift_flags: list[dict[str, Any]] = []
    provenance_gaps: list[dict[str, Any]] = []
    for unit in registry_service.list_units():
        aligned_tokens = {token_id for alignment in unit.get("alignments", []) for token_id in alignment.get("source_token_ids", [])}
        for token_id in unit.get("token_ids", []):
            if token_id not in aligned_tokens:
                uncovered_tokens.append({"unit_id": unit["unit_id"], "token_id": token_id})
        for rendering in unit.get("renderings", []):
            if not rendering.get("alignment_ids"):
                unaligned_spans.append({"unit_id": unit["unit_id"], "rendering_id": rendering["rendering_id"]})
            for flag in rendering.get("drift_flags", []):
                drift_flags.append({"unit_id": unit["unit_id"], "rendering_id": rendering["rendering_id"], "flag": flag})
            if not rendering.get("provenance"):
                provenance_gaps.append({"unit_id": unit["unit_id"], "rendering_id": rendering["rendering_id"]})
    return {
        "uncovered_tokens": uncovered_tokens,
        "unaligned_spans": unaligned_spans,
        "open_drift_flags": drift_flags,
        "provenance_gaps": provenance_gaps,
    }
