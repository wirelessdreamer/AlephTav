from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.core.ids import audit_id
from app.services import poetic_analysis_service, registry_service


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def _rendering_has_provenance(rendering: dict[str, Any]) -> bool:
    provenance = rendering.get("provenance")
    if not isinstance(provenance, dict):
        return False
    source_ids = provenance.get("source_ids")
    generator = provenance.get("generator")
    return isinstance(source_ids, list) and len(source_ids) > 0 and bool(generator)


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


def latest_change_timestamp() -> str:
    timestamps: list[datetime] = []
    project = registry_service.load_project()
    for source in project.get("source_manifests", []):
        parsed = _parse_timestamp(source.get("imported_at"))
        if parsed is not None:
            timestamps.append(parsed)
    for unit in registry_service.list_units():
        for record in unit.get("audit_records", []):
            parsed = _parse_timestamp(record.get("created_at"))
            if parsed is not None:
                timestamps.append(parsed)
        for record in unit.get("review_decisions", []):
            parsed = _parse_timestamp(record.get("timestamp"))
            if parsed is not None:
                timestamps.append(parsed)
    if not timestamps:
        return datetime(1970, 1, 1, tzinfo=timezone.utc).isoformat()  # noqa: UP017
    return max(timestamps).astimezone(timezone.utc).isoformat()  # noqa: UP017


def open_concerns() -> dict[str, Any]:
    uncovered_tokens: list[dict[str, Any]] = []
    unaligned_spans: list[dict[str, Any]] = []
    drift_flags: list[dict[str, Any]] = []
    provenance_gaps: list[dict[str, Any]] = []
    for unit in registry_service.list_units():
        aligned_tokens = {
            token_id
            for alignment in unit.get("alignments", [])
            for token_id in alignment.get("source_token_ids", [])
        }
        for token_id in unit.get("token_ids", []):
            if token_id not in aligned_tokens:
                uncovered_tokens.append({"unit_id": unit["unit_id"], "token_id": token_id})
        for rendering in unit.get("renderings", []):
            if not rendering.get("alignment_ids"):
                unaligned_spans.append(
                    {"unit_id": unit["unit_id"], "rendering_id": rendering["rendering_id"]}
                )
            for flag in rendering.get("drift_flags", []):
                normalized = poetic_analysis_service.normalize_flag(flag)
                drift_flags.append(
                    {
                        "unit_id": unit["unit_id"],
                        "rendering_id": rendering["rendering_id"],
                        "status": rendering.get("status"),
                        "flag": normalized,
                    }
                )
            if not _rendering_has_provenance(rendering):
                provenance_gaps.append(
                    {
                        "unit_id": unit["unit_id"],
                        "rendering_id": rendering["rendering_id"],
                        "status": rendering.get("status"),
                    }
                )
    return {
        "uncovered_tokens": uncovered_tokens,
        "unaligned_spans": unaligned_spans,
        "open_drift_flags": drift_flags,
        "provenance_gaps": provenance_gaps,
    }
