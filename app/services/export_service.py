from __future__ import annotations

import hashlib
from pathlib import Path

from app.core.config import get_settings
from app.core.errors import LicensePolicyError, PublicationConstraintError
from app.services import poetic_analysis_service, registry_service, report_service


def _ensure_exportable() -> None:
    audit = registry_service.audit_licenses()
    if any("forbidden_for_export" in item["warnings"] for item in audit["evaluations"]):
        raise LicensePolicyError("Export blocked by forbidden source license policy")
    _ensure_canonical_publication_constraints()


def _ensure_canonical_publication_constraints() -> None:
    violations: list[str] = []
    for unit in registry_service.list_units():
        for rendering in unit.get("renderings", []):
            if rendering.get("status") != "canonical":
                continue
            missing_metrics = poetic_analysis_service.missing_required_lyric_metrics(rendering)
            if missing_metrics:
                violations.append(
                    f"{rendering['rendering_id']}: missing lyric metrics {', '.join(missing_metrics)}"
                )
            if poetic_analysis_service.has_blocking_drift(rendering):
                violations.append(
                    f"{rendering['rendering_id']}: unresolved high-severity drift"
                )
    if violations:
        raise PublicationConstraintError(
            "Export blocked by canonical publication constraints: " + "; ".join(violations)
        )


def _exportable_source_ids() -> set[str]:
    project = registry_service.load_project()
    return {
        item["source_id"]
        for item in project.get("source_manifests", [])
        if item.get("allowed_for_export")
    }


def _filter_exportable_units(psalm: dict[str, object]) -> dict[str, object]:
    allowed_source_ids = _exportable_source_ids()
    units = []
    for unit in psalm["units"]:
        renderings = []
        for rendering in unit.get("renderings", []):
            provenance = rendering.get("provenance", {})
            source_ids = provenance.get("source_ids", []) if isinstance(provenance, dict) else []
            if any(source_id not in allowed_source_ids for source_id in source_ids):
                continue
            renderings.append(rendering)
        export_unit = {
            "unit_id": unit["unit_id"],
            "ref": unit["ref"],
            "source_hebrew": unit["source_hebrew"],
            "source_transliteration": unit["source_transliteration"],
            "canonical_renderings": [item for item in renderings if item["status"] == "canonical"],
            "alternate_renderings": [
                item for item in renderings if item["status"] == "accepted_as_alternate"
            ],
            "audit_records": unit.get("audit_records", []),
            "review_decisions": unit.get("review_decisions", []),
            "witnesses": [
                item
                for item in unit.get("witnesses", [])
                if item.get("source_id") in allowed_source_ids
            ],
        }
        units.append(export_unit)
    return {"psalm_id": psalm["psalm_id"], "title": psalm["title"], "units": units}


def _release_text_payload() -> list[dict[str, object]]:
    return [
        _filter_exportable_units(registry_service.load_psalm(item))
        for item in registry_service.list_psalm_ids()
    ]


def _plain_text_release(export_payload: list[dict[str, object]]) -> str:
    lines: list[str] = []
    for psalm in export_payload:
        lines.append(f"{psalm['title']} ({psalm['psalm_id']})")
        for unit in psalm["units"]:
            lines.append(f"{unit['ref']} [{unit['unit_id']}]")
            for rendering in unit["canonical_renderings"]:
                lines.append(f"CANONICAL {rendering['layer']}: {rendering['text']}")
            for rendering in unit["alternate_renderings"]:
                lines.append(f"ALTERNATE {rendering['layer']}: {rendering['text']}")
            lines.append("")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def _markdown_release(export_payload: list[dict[str, object]]) -> str:
    lines = ["# Release Text", ""]
    for psalm in export_payload:
        lines.append(f"## {psalm['title']} ({psalm['psalm_id']})")
        lines.append("")
        for unit in psalm["units"]:
            lines.append(f"### {unit['ref']}")
            for rendering in unit["canonical_renderings"]:
                lines.append(f"- Canonical `{rendering['layer']}`: {rendering['text']}")
            for rendering in unit["alternate_renderings"]:
                lines.append(f"- Alternate `{rendering['layer']}`: {rendering['text']}")
            lines.append("")
    return "\n".join(lines)


def _html_release(export_payload: list[dict[str, object]]) -> str:
    chunks = ["<html><body><h1>Release Text</h1>"]
    for psalm in export_payload:
        chunks.append(f"<h2>{psalm['title']} ({psalm['psalm_id']})</h2>")
        for unit in psalm["units"]:
            chunks.append(f"<h3>{unit['ref']}</h3><ul>")
            for rendering in unit["canonical_renderings"]:
                chunks.append(f"<li>Canonical {rendering['layer']}: {rendering['text']}</li>")
            for rendering in unit["alternate_renderings"]:
                chunks.append(f"<li>Alternate {rendering['layer']}: {rendering['text']}</li>")
            chunks.append("</ul>")
    chunks.append("</body></html>")
    return "".join(chunks)


def _render_license(project: dict[str, object], release_id: str) -> str:
    return (
        f"Release {release_id}\n\n"
        f"Text license: {project['output_text_license']}\n"
        f"Code license: {project['code_license']}\n"
        f"Release channel: {project['release_channel']}\n"
    )


def _render_notice(project: dict[str, object], release_id: str) -> str:
    return (
        f"Notice for release {release_id}\n\n"
        "This distribution includes canonical JSON content, derived export formats, "
        "audit reports, provenance metadata, and source manifest references.\n\n"
        "Included sources:\n"
        + "".join(
            f"- {source['source_id']}: {source['name']} ({source['license']})\n"
            for source in project.get("source_manifests", [])
        )
    )


def _write_bundle_manifest(
    destination: Path, release_id: str, release_report: dict[str, object]
) -> None:
    files = []
    for path in sorted(item for item in destination.iterdir() if item.is_file()):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        files.append({"path": path.name, "sha256": digest})
    manifest = {
        "release_id": release_id,
        "generated_at": release_report["generated_at"],
        "bundle_hash": registry_service.file_hash(files),
        "files": files,
    }
    registry_service.write_json(destination / "bundle_manifest.json", manifest)


def _write_provenance_manifest(
    destination: Path, export_payload: list[dict[str, object]]
) -> None:
    entries: list[dict[str, object]] = []
    for psalm in export_payload:
        for unit in psalm["units"]:
            for rendering in unit["canonical_renderings"] + unit["alternate_renderings"]:
                entries.append(
                    {
                        "unit_id": unit["unit_id"],
                        "rendering_id": rendering["rendering_id"],
                        "layer": rendering["layer"],
                        "status": rendering["status"],
                        "source_ids": rendering.get("provenance", {}).get("source_ids", []),
                        "generator": rendering.get("provenance", {}).get("generator"),
                        "alignment_ids": rendering.get("alignment_ids", []),
                    }
                )
    registry_service.write_json(destination / "provenance_manifest.json", entries)


def export_book(psalm_id: str | None = None, output_dir: Path | None = None) -> Path:
    _ensure_exportable()
    settings = get_settings()
    destination = output_dir or settings.release_reports_dir / "book-export"
    destination.mkdir(parents=True, exist_ok=True)
    psalms = (
        [registry_service.load_psalm(psalm_id)]
        if psalm_id
        else [registry_service.load_psalm(item) for item in registry_service.list_psalm_ids()]
    )
    export_payload = [_filter_exportable_units(psalm) for psalm in psalms]
    registry_service.write_json(destination / "book.json", export_payload)
    (destination / "book.md").write_text(_markdown_release(export_payload), encoding="utf-8")
    (destination / "book.txt").write_text(_plain_text_release(export_payload), encoding="utf-8")
    (destination / "book.html").write_text(_html_release(export_payload), encoding="utf-8")
    _write_provenance_manifest(destination, export_payload)
    return destination


def export_release(release_id: str) -> Path:
    _ensure_exportable()
    settings = get_settings()
    destination = settings.release_reports_dir / release_id / "bundle"
    destination.mkdir(parents=True, exist_ok=True)

    release_report = report_service.generate_release_report(release_id)
    export_payload = _release_text_payload()
    project = registry_service.load_project()

    registry_service.write_json(destination / "text.json", export_payload)
    (destination / "text.md").write_text(_markdown_release(export_payload), encoding="utf-8")
    (destination / "text.txt").write_text(_plain_text_release(export_payload), encoding="utf-8")
    (destination / "text.html").write_text(_html_release(export_payload), encoding="utf-8")
    registry_service.write_json(destination / "AUDIT_REPORT.json", release_report)
    registry_service.write_json(
        destination / "OPEN_CONCERNS.json", release_report["unresolved_warnings"]
    )
    registry_service.write_json(destination / "release_manifest.json", release_report)
    (destination / "AUDIT_REPORT.md").write_text(
        (settings.release_reports_dir / "AUDIT_REPORT.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (destination / "AUDIT_REPORT.html").write_text(
        (settings.release_reports_dir / "AUDIT_REPORT.html").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (destination / "OPEN_CONCERNS.md").write_text(
        (settings.audit_reports_dir / "open_concerns.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (destination / "OPEN_CONCERNS.html").write_text(
        (settings.audit_reports_dir / "open_concerns.html").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (destination / "SOURCES.md").write_text(
        (settings.release_reports_dir / "SOURCES.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (destination / "SOURCES.html").write_text(
        (settings.release_reports_dir / "SOURCES.html").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (destination / "RELEASE_NOTES.md").write_text(
        (settings.release_reports_dir / "RELEASE_NOTES.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (destination / "LICENSE").write_text(_render_license(project, release_id), encoding="utf-8")
    (destination / "NOTICE").write_text(_render_notice(project, release_id), encoding="utf-8")
    _write_provenance_manifest(destination, export_payload)
    _write_bundle_manifest(destination, release_id, release_report)
    return destination
