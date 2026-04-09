from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.core.config import get_settings
from app.services import audit_service, registry_service


def generate_audit_reports() -> dict[str, Any]:
    settings = get_settings()
    concerns = audit_service.open_concerns()
    registry_service.write_json(settings.audit_reports_dir / "uncovered_tokens.json", concerns["uncovered_tokens"])
    registry_service.write_json(settings.audit_reports_dir / "unaligned_spans.json", concerns["unaligned_spans"])
    registry_service.write_json(settings.audit_reports_dir / "open_drift_flags.json", concerns["open_drift_flags"])
    registry_service.write_json(settings.audit_reports_dir / "provenance_gaps.json", concerns["provenance_gaps"])
    settings.audit_reports_dir.mkdir(parents=True, exist_ok=True)
    (settings.audit_reports_dir / "open_concerns.md").write_text(
        "# Open Concerns\n\n"
        f"- Uncovered tokens: {len(concerns['uncovered_tokens'])}\n"
        f"- Unaligned spans: {len(concerns['unaligned_spans'])}\n"
        f"- Drift flags: {len(concerns['open_drift_flags'])}\n"
        f"- Provenance gaps: {len(concerns['provenance_gaps'])}\n",
        encoding="utf-8",
    )
    change_lines = ["# Unit Change Log", ""]
    for unit in registry_service.list_units():
        change_lines.append(f"## {unit['unit_id']}")
        for record in unit.get("audit_records", []):
            change_lines.append(f"- {record['created_at']}: {record['summary']} ({record['created_by']})")
        change_lines.append("")
    (settings.audit_reports_dir / "unit_change_log.md").write_text("\n".join(change_lines), encoding="utf-8")
    return concerns


def generate_release_report(release_id: str) -> dict[str, Any]:
    settings = get_settings()
    project = registry_service.load_project()
    concerns = audit_service.open_concerns()
    render_count = 0
    canonical_changes = 0
    alternates = 0
    for unit in registry_service.list_units():
        for rendering in unit.get("renderings", []):
            render_count += 1
            if rendering["status"] == "canonical":
                canonical_changes += 1
            if rendering["status"] == "accepted_as_alternate":
                alternates += 1
    manifest = {
        "release_id": release_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_manifests": project.get("source_manifests", []),
        "render_counts": {"total": render_count, "canonical": canonical_changes, "alternates": alternates},
        "unresolved_warnings": concerns,
        "signoff_summary": project.get("review_policy", {}),
    }
    registry_service.write_json(settings.release_reports_dir / "release_manifest.json", manifest)
    (settings.release_reports_dir / "RELEASE_NOTES.md").write_text(
        "# Release Notes\n\n"
        f"- Release: {release_id}\n"
        f"- Canonical renderings: {canonical_changes}\n"
        f"- Accepted alternates: {alternates}\n"
        f"- Unresolved concerns: {sum(len(v) for v in concerns.values())}\n",
        encoding="utf-8",
    )
    (settings.release_reports_dir / "AUDIT_REPORT.md").write_text(
        "# Audit Report\n\n"
        f"Generated for {release_id}.\n\n"
        f"Outstanding uncovered tokens: {len(concerns['uncovered_tokens'])}\n",
        encoding="utf-8",
    )
    sources_md = ["# SOURCES", ""]
    for source in project.get("source_manifests", []):
        sources_md.append(f"- **{source['source_id']}** {source['name']} ({source['version']}) — {source['license']}")
    (settings.release_reports_dir / "SOURCES.md").write_text("\n".join(sources_md), encoding="utf-8")
    return manifest
