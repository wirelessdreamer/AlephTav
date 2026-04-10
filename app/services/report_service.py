from __future__ import annotations

from datetime import datetime
from typing import Any

from app.core.config import get_settings
from app.core.errors import ReleaseValidationError
from app.services import audit_service, registry_service, review_service
from scripts.validate_content import validate_all_content


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _review_summary(unit: dict[str, Any], target_id: str) -> dict[str, Any]:
    approvals = [
        {
            "reviewer": item["reviewer"],
            "reviewer_role": item["reviewer_role"],
            "timestamp": item["timestamp"],
        }
        for item in unit.get("review_decisions", [])
        if item.get("target_id") == target_id and item.get("decision") == "approve"
    ]
    return {"approval_count": len(approvals), "approvals": approvals}


def _rendering_snapshot(unit: dict[str, Any], rendering: dict[str, Any]) -> dict[str, Any]:
    snapshot = {
        "unit_id": unit["unit_id"],
        "rendering_id": rendering["rendering_id"],
        "layer": rendering["layer"],
        "status": rendering["status"],
        "text": rendering["text"],
        "alignment_ids": rendering.get("alignment_ids", []),
        "drift_flags": rendering.get("drift_flags", []),
        "provenance": rendering.get("provenance", {}),
        "review_summary": _review_summary(unit, rendering["rendering_id"]),
    }
    snapshot["fingerprint"] = registry_service.file_hash(snapshot)
    return snapshot


def _list_previous_release_reports(current_release_id: str) -> list[dict[str, Any]]:
    settings = get_settings()
    reports: list[tuple[datetime, dict[str, Any]]] = []
    for path in sorted(settings.release_reports_dir.glob("*/release_manifest.json")):
        report = registry_service.read_json(path)
        if report.get("release_id") == current_release_id:
            continue
        timestamp = _parse_timestamp(report.get("generated_at"))
        if timestamp is None:
            continue
        reports.append((timestamp, report))
    reports.sort(key=lambda item: (item[0], item[1]["release_id"]))
    return [report for _, report in reports]


def _latest_previous_release(current_release_id: str) -> dict[str, Any] | None:
    reports = _list_previous_release_reports(current_release_id)
    return reports[-1] if reports else None


def _change_set(
    current: list[dict[str, Any]], previous: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    previous_by_id = {item["rendering_id"]: item for item in previous}
    changed: list[dict[str, Any]] = []
    for item in current:
        baseline = previous_by_id.get(item["rendering_id"])
        if baseline is None or baseline.get("fingerprint") != item["fingerprint"]:
            changed.append(item)
    return changed


def _collect_contributor_credits() -> list[dict[str, Any]]:
    credits: dict[tuple[str, str], dict[str, Any]] = {}
    for unit in registry_service.list_units():
        for record in unit.get("audit_records", []):
            key = (record["created_by"], "audit")
            credits.setdefault(
                key, {"contributor": record["created_by"], "roles": set(), "units": set()}
            )
            credits[key]["roles"].add("audit")
            credits[key]["units"].add(unit["unit_id"])
        for record in unit.get("review_decisions", []):
            key = (record["reviewer"], record["reviewer_role"])
            credits.setdefault(
                key, {"contributor": record["reviewer"], "roles": set(), "units": set()}
            )
            credits[key]["roles"].add(record["reviewer_role"])
            credits[key]["units"].add(unit["unit_id"])
    rows = []
    for item in credits.values():
        rows.append(
            {
                "contributor": item["contributor"],
                "roles": sorted(item["roles"]),
                "units": sorted(item["units"]),
                "unit_count": len(item["units"]),
            }
        )
    return sorted(rows, key=lambda item: (item["contributor"], item["roles"]))


def _project_manifest_mismatches(project: dict[str, Any]) -> list[str]:
    raw_manifests = {
        path.parent.name: registry_service.read_json(path)
        for path in sorted(get_settings().raw_dir.glob("*/manifest.json"))
    }
    errors: list[str] = []
    project_manifests = {item["source_id"]: item for item in project.get("source_manifests", [])}
    if sorted(project_manifests) != sorted(raw_manifests):
        errors.append("project source_manifests do not match raw manifest inventory")
    for source_id, raw_manifest in raw_manifests.items():
        if project_manifests.get(source_id) != raw_manifest:
            errors.append(f"project source_manifest mismatch for {source_id}")
    if sorted(project.get("allowed_sources", [])) != sorted(project_manifests):
        errors.append("allowed_sources do not mirror source_manifests")
    return errors


def _exportable_source_ids(project: dict[str, Any]) -> set[str]:
    return {
        item["source_id"]
        for item in project.get("source_manifests", [])
        if item.get("allowed_for_export")
    }


def validate_release(release_id: str) -> dict[str, Any]:
    project = registry_service.load_project()
    license_audit = registry_service.audit_licenses()
    validation = validate_all_content()
    concerns = audit_service.open_concerns()
    exportable_sources = _exportable_source_ids(project)
    review_policy = project.get("review_policy", {})
    canonical_required = review_policy.get("canonical_required_approvals", 0)
    alternate_required = review_policy.get("alternate_required_approvals", 0)
    release_role = review_policy.get("release_required_role", "release reviewer")

    canonical_review_gaps: list[dict[str, Any]] = []
    alternate_review_gaps: list[dict[str, Any]] = []
    canonical_drift_gaps: list[dict[str, Any]] = []
    provenance_policy_gaps: list[dict[str, Any]] = []
    release_signoff_units: set[str] = set()

    for unit in registry_service.list_units():
        for decision in unit.get("review_decisions", []):
            if (
                decision.get("reviewer_role") == release_role
                and decision.get("decision") == "approve"
            ):
                release_signoff_units.add(unit["unit_id"])
        for rendering in unit.get("renderings", []):
            provenance = rendering.get("provenance", {})
            source_ids = provenance.get("source_ids", []) if isinstance(provenance, dict) else []
            unexportable_sources = sorted(
                source_id for source_id in source_ids if source_id not in exportable_sources
            )
            if unexportable_sources:
                provenance_policy_gaps.append(
                    {
                        "unit_id": unit["unit_id"],
                        "rendering_id": rendering["rendering_id"],
                        "source_ids": unexportable_sources,
                    }
                )
            approvals = _review_summary(unit, rendering["rendering_id"])["approval_count"]
            if rendering["status"] == "canonical":
                if approvals < canonical_required:
                    canonical_review_gaps.append(
                        {
                            "unit_id": unit["unit_id"],
                            "rendering_id": rendering["rendering_id"],
                            "approval_count": approvals,
                            "required": canonical_required,
                        }
                    )
                if rendering.get("drift_flags"):
                    canonical_drift_gaps.append(
                        {
                            "unit_id": unit["unit_id"],
                            "rendering_id": rendering["rendering_id"],
                            "drift_flags": rendering["drift_flags"],
                        }
                    )
            if rendering["status"] == "accepted_as_alternate" and approvals < alternate_required:
                alternate_review_gaps.append(
                    {
                        "unit_id": unit["unit_id"],
                        "rendering_id": rendering["rendering_id"],
                        "approval_count": approvals,
                        "required": alternate_required,
                    }
                )

    output_license = project.get("output_text_license", "").strip()
    source_manifest_gaps = _project_manifest_mismatches(project)
    checks = [
        {
            "name": "content_validation",
            "status": "pass" if not validation["errors"] else "fail",
            "details": validation["errors"],
        },
        {
            "name": "license_audit",
            "status": "pass" if license_audit["status"] == "ok" else "fail",
            "details": [item for item in license_audit["evaluations"] if item["warnings"]],
        },
        {
            "name": "source_manifest_completeness",
            "status": "pass" if not source_manifest_gaps else "fail",
            "details": source_manifest_gaps,
        },
        {
            "name": "output_text_license",
            "status": "pass" if output_license and "tbd" not in output_license.lower() else "fail",
            "details": []
            if output_license and "tbd" not in output_license.lower()
            else ["output_text_license must be release-specific"],
        },
        {
            "name": "canonical_drift",
            "status": "pass" if not canonical_drift_gaps else "fail",
            "details": canonical_drift_gaps,
        },
        {
            "name": "canonical_review_signoff",
            "status": "pass" if not canonical_review_gaps else "fail",
            "details": canonical_review_gaps,
        },
        {
            "name": "alternate_review_signoff",
            "status": "pass" if not alternate_review_gaps else "fail",
            "details": alternate_review_gaps,
        },
        {
            "name": "release_reviewer_signoff",
            "status": "pass"
            if len(release_signoff_units) == len(registry_service.list_units())
            else "fail",
            "details": [
                unit["unit_id"]
                for unit in registry_service.list_units()
                if unit["unit_id"] not in release_signoff_units
            ],
        },
        {
            "name": "provenance_completeness",
            "status": "pass"
            if not concerns["provenance_gaps"] and not provenance_policy_gaps
            else "fail",
            "details": concerns["provenance_gaps"] + provenance_policy_gaps,
        },
    ]
    status = "pass" if all(item["status"] == "pass" for item in checks) else "fail"
    return {
        "release_id": release_id,
        "status": status,
        "checks": checks,
    }


def generate_audit_reports() -> dict[str, Any]:
    settings = get_settings()
    concerns = audit_service.open_concerns()
    registry_service.write_json(
        settings.audit_reports_dir / "uncovered_tokens.json", concerns["uncovered_tokens"]
    )
    registry_service.write_json(
        settings.audit_reports_dir / "unaligned_spans.json", concerns["unaligned_spans"]
    )
    registry_service.write_json(
        settings.audit_reports_dir / "open_drift_flags.json", concerns["open_drift_flags"]
    )
    registry_service.write_json(
        settings.audit_reports_dir / "provenance_gaps.json", concerns["provenance_gaps"]
    )
    registry_service.write_json(
        settings.audit_reports_dir / "low_confidence_alignments.json", concerns["low_confidence_alignments"]
    )
    settings.audit_reports_dir.mkdir(parents=True, exist_ok=True)

    open_concerns_md = (
        "# Open Concerns\n\n"
        f"- Uncovered tokens: {len(concerns['uncovered_tokens'])}\n"
        f"- Unaligned spans: {len(concerns['unaligned_spans'])}\n"
        f"- Low-confidence alignments: {len(concerns['low_confidence_alignments'])}\n"
        f"- Drift flags: {len(concerns['open_drift_flags'])}\n"
        f"- Provenance gaps: {len(concerns['provenance_gaps'])}\n"
    )
    (settings.audit_reports_dir / "open_concerns.md").write_text(open_concerns_md, encoding="utf-8")
    (settings.audit_reports_dir / "open_concerns.html").write_text(
        "<html><body><h1>Open Concerns</h1>"
        f"<ul><li>Uncovered tokens: {len(concerns['uncovered_tokens'])}</li>"
        f"<li>Unaligned spans: {len(concerns['unaligned_spans'])}</li>"
        f"<li>Drift flags: {len(concerns['open_drift_flags'])}</li>"
        f"<li>Provenance gaps: {len(concerns['provenance_gaps'])}</li></ul></body></html>",
        encoding="utf-8",
    )

    change_lines = ["# Unit Change Log", ""]
    change_rows = ["<html><body><h1>Unit Change Log</h1>"]
    for unit in registry_service.list_units():
        change_lines.append(f"## {unit['unit_id']}")
        change_rows.append(f"<h2>{unit['unit_id']}</h2><ul>")
        for record in unit.get("audit_records", []):
            change_lines.append(
                f"- {record['created_at']}: {record['summary']} ({record['created_by']})"
            )
            change_rows.append(
                f"<li>{record['created_at']}: {record['summary']} ({record['created_by']})</li>"
            )
        change_lines.append("")
        change_rows.append("</ul>")
    change_rows.append("</body></html>")
    (settings.audit_reports_dir / "unit_change_log.md").write_text(
        "\n".join(change_lines), encoding="utf-8"
    )
    (settings.audit_reports_dir / "unit_change_log.html").write_text(
        "".join(change_rows), encoding="utf-8"
    )
    return concerns


def generate_release_report(release_id: str) -> dict[str, Any]:
    settings = get_settings()
    project = registry_service.load_project()
    concerns = generate_audit_reports()
    validation = validate_release(release_id)
    if validation["status"] != "pass":
        raise ReleaseValidationError(f"Release validation failed for {release_id}")

    canonical_renderings: list[dict[str, Any]] = []
    accepted_alternates: list[dict[str, Any]] = []
    render_count = 0
    signoff_details: list[dict[str, Any]] = []
    for unit in registry_service.list_units():
        review_service.hydrate_unit_review_state(unit)
        for rendering in unit.get("renderings", []):
            render_count += 1
            snapshot = _rendering_snapshot(unit, rendering)
            if rendering["status"] == "canonical":
                canonical_renderings.append(snapshot)
                signoff_details.append(
                    {
                        "unit_id": unit["unit_id"],
                        "rendering_id": rendering["rendering_id"],
                        "status": rendering["review_signoff"]["status"],
                        "approval_count": rendering["review_signoff"]["approval_count"],
                        "has_release_signoff": rendering["review_signoff"]["has_release_signoff"],
                        "publication_ready": rendering["review_signoff"]["publication_ready"],
                    }
                )
            if rendering["status"] == "accepted_as_alternate":
                accepted_alternates.append(snapshot)

    previous_release = _latest_previous_release(release_id)
    previous_inventory = previous_release.get("inventory", {}) if previous_release else {}
    canonical_changes = _change_set(
        canonical_renderings, previous_inventory.get("canonical_renderings", [])
    )
    alternate_changes = _change_set(
        accepted_alternates, previous_inventory.get("accepted_alternates", [])
    )
    contributor_credits = _collect_contributor_credits()

    manifest = {
        "release_id": release_id,
        "generated_at": audit_service.latest_change_timestamp(),
        "previous_release_id": previous_release.get("release_id") if previous_release else None,
        "source_manifests": project.get("source_manifests", []),
        "render_counts": {
            "total": render_count,
            "canonical": len(canonical_renderings),
            "alternates": len(accepted_alternates),
        },
        "unresolved_warnings": concerns,
        "signoff_summary": {
            **review_service.review_policy(project),
            "validation": validation,
            "canonical_renderings": signoff_details,
            "publication_ready_count": sum(1 for item in signoff_details if item["publication_ready"]),
        },
        "change_sets": {
            "canonical_changes_since_previous_release": canonical_changes,
            "accepted_alternates_since_previous_release": alternate_changes,
        },
        "inventory": {
            "canonical_renderings": canonical_renderings,
            "accepted_alternates": accepted_alternates,
        },
        "contributor_credits": contributor_credits,
    }

    release_dir = settings.release_reports_dir / release_id
    release_dir.mkdir(parents=True, exist_ok=True)
    registry_service.write_json(settings.release_reports_dir / "release_manifest.json", manifest)
    registry_service.write_json(release_dir / "release_manifest.json", manifest)
    registry_service.write_json(
        settings.audit_reports_dir / "canonical_changes_since_previous_release.json",
        canonical_changes,
    )
    registry_service.write_json(
        settings.audit_reports_dir / "accepted_alternates_since_previous_release.json",
        alternate_changes,
    )

    release_notes = (
        "# Release Notes\n\n"
        f"- Release: {release_id}\n"
        f"- Previous release: {manifest['previous_release_id'] or 'none'}\n"
        f"- Canonical renderings: {len(canonical_renderings)}\n"
        f"- Accepted alternates: {len(accepted_alternates)}\n"
        f"- Canonical changes since previous release: {len(canonical_changes)}\n"
        f"- Accepted alternates since previous release: {len(alternate_changes)}\n"
        f"- Unresolved concerns: {sum(len(v) for v in concerns.values())}\n"
        f"- Contributors credited: {len(contributor_credits)}\n"
    )
    (settings.release_reports_dir / "RELEASE_NOTES.md").write_text(release_notes, encoding="utf-8")
    (release_dir / "RELEASE_NOTES.md").write_text(release_notes, encoding="utf-8")

    audit_report = (
        "# Audit Report\n\n"
        f"Generated for {release_id} at {manifest['generated_at']}.\n\n"
        f"- Canonical changes since previous release: {len(canonical_changes)}\n"
        f"- Accepted alternates since previous release: {len(alternate_changes)}\n"
        f"- Uncovered tokens: {len(concerns['uncovered_tokens'])}\n"
        f"- Unaligned spans: {len(concerns['unaligned_spans'])}\n"
        f"- Drift flags: {len(concerns['open_drift_flags'])}\n"
        f"- Provenance gaps: {len(concerns['provenance_gaps'])}\n"
    )
    (settings.release_reports_dir / "AUDIT_REPORT.md").write_text(audit_report, encoding="utf-8")
    (release_dir / "AUDIT_REPORT.md").write_text(audit_report, encoding="utf-8")
    audit_html = (
        "<html><body><h1>Audit Report</h1>"
        f"<p>Generated for {release_id} at {manifest['generated_at']}.</p>"
        f"<ul><li>Canonical changes since previous release: {len(canonical_changes)}</li>"
        f"<li>Accepted alternates since previous release: {len(alternate_changes)}</li>"
        f"<li>Uncovered tokens: {len(concerns['uncovered_tokens'])}</li>"
        f"<li>Unaligned spans: {len(concerns['unaligned_spans'])}</li>"
        f"<li>Drift flags: {len(concerns['open_drift_flags'])}</li>"
        f"<li>Provenance gaps: {len(concerns['provenance_gaps'])}</li></ul></body></html>"
    )
    (settings.release_reports_dir / "AUDIT_REPORT.html").write_text(audit_html, encoding="utf-8")
    (release_dir / "AUDIT_REPORT.html").write_text(audit_html, encoding="utf-8")

    sources_md = ["# SOURCES", ""]
    for source in project.get("source_manifests", []):
        policy = "exportable" if source["allowed_for_export"] else "restricted from export"
        sources_md.append(
            f"- **{source['source_id']}** {source['name']} ({source['version']})"
            f" — {source['license']} [{policy}]"
        )
    sources_text = "\n".join(sources_md)
    (settings.release_reports_dir / "SOURCES.md").write_text(sources_text, encoding="utf-8")
    (release_dir / "SOURCES.md").write_text(sources_text, encoding="utf-8")
    (settings.release_reports_dir / "SOURCES.html").write_text(
        "<html><body><h1>SOURCES</h1><ul>"
        + "".join(
            (
                f"<li>{source['source_id']}: {source['name']} "
                f"({source['version']}) - {source['license']} "
                "["
                f"{'exportable' if source['allowed_for_export'] else 'restricted from export'}"
                "]</li>"
            )
            for source in project.get("source_manifests", [])
        )
        + "</ul></body></html>",
        encoding="utf-8",
    )
    return manifest
