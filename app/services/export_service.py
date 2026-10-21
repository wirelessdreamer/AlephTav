from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.core.errors import LicensePolicyError, PublicationConstraintError, ReviewRequiredError
from app.core.license_rules import evaluate_manifest
from app.services import (
    poetic_analysis_service,
    registry_service,
    report_service,
    review_service,
    source_capability_service,
)
from app.services.immutable_file_service import workspace_lock


def _ensure_exportable() -> None:
    project_evaluations = [
        evaluate_manifest(item)
        for item in registry_service.load_project().get("source_manifests", [])
    ]
    audit = registry_service.audit_licenses()
    if any(
        "forbidden_for_export" in item["warnings"]
        for item in [*project_evaluations, *audit["evaluations"]]
    ):
        raise LicensePolicyError("Export blocked by forbidden source license policy")
    _ensure_canonical_publication_constraints()
    missing_signoff: list[str] = []
    for unit in registry_service.list_units():
        review_service.hydrate_unit_review_state(unit)
        for rendering in unit.get("renderings", []):
            if rendering.get("status") != "canonical":
                continue
            if not rendering.get("review_signoff", {}).get("publication_ready"):
                missing_signoff.append(rendering["rendering_id"])
    if missing_signoff:
        raise ReviewRequiredError(
            "Export blocked until canonical signoff is complete: "
            + ", ".join(sorted(missing_signoff))
        )


def _ensure_canonical_publication_constraints() -> None:
    violations: list[str] = []
    for unit in registry_service.list_units():
        for rendering in unit.get("renderings", []):
            if rendering.get("status") != "canonical":
                continue
            missing_metrics = poetic_analysis_service.missing_required_lyric_metrics(rendering)
            if missing_metrics:
                missing = ", ".join(missing_metrics)
                violations.append(f"{rendering['rendering_id']}: missing lyric metrics {missing}")
            if poetic_analysis_service.has_blocking_drift(rendering):
                violations.append(f"{rendering['rendering_id']}: unresolved high-severity drift")
    if violations:
        raise PublicationConstraintError(
            "Export blocked by canonical publication constraints: " + "; ".join(violations)
        )


def _exportable_source_ids() -> set[str]:
    project = registry_service.load_project()
    return {
        item["source_id"]
        for item in project.get("source_manifests", [])
        if source_capability_service.effective_capabilities(item["source_id"])["export"]
    }


def _source_closure_exportable(value: Any, allowed: set[str]) -> bool:
    """Legacy exports cannot resolve a Greek snapshot or unscoped nested packages."""
    if isinstance(value, dict):
        if value.get("basis_type") == "septuagint_greek_to_english":
            return False
        if str(value.get("source_language", "")).lower() in {"grc", "greek"}:
            return False
        if str(value.get("language", "")).lower() in {"grc", "greek"}:
            return False
        if value.get("source_package_id"):
            return False
        if "source_ids" in value:
            ids = value["source_ids"]
            if not isinstance(ids, list) or not ids or any(item not in allowed for item in ids):
                return False
        if "source_id" in value:
            source_id = value["source_id"]
            if not isinstance(source_id, str) or source_id not in allowed:
                return False
            component = value.get("source_component", value.get("component"))
            if not source_capability_service.effective_capabilities(source_id, component)["export"]:
                return False
        return all(_source_closure_exportable(item, allowed) for item in value.values())
    if isinstance(value, list):
        return all(_source_closure_exportable(item, allowed) for item in value)
    return True


def _rendering_for_export(rendering: dict[str, Any]) -> dict[str, Any]:
    """Exclude unscoped notes, cached inputs and arbitrary nested provenance payloads."""
    provenance = rendering["provenance"]
    signoff = rendering.get("review_signoff", {})
    return {
        "rendering_id": rendering["rendering_id"],
        "layer": rendering["layer"],
        "status": rendering["status"],
        "text": rendering["text"],
        "alignment_ids": rendering.get("alignment_ids", []),
        "provenance": {
            "source_ids": provenance["source_ids"],
            "generator": provenance.get("generator"),
        },
        "review_signoff": {
            key: signoff[key]
            for key in ("status", "approval_count", "has_release_signoff", "publication_ready")
            if key in signoff
        },
    }


def _filter_exportable_units(psalm: dict[str, Any]) -> dict[str, Any]:
    allowed_source_ids = _exportable_source_ids()
    if "uxlc" not in allowed_source_ids:
        raise LicensePolicyError(
            "Legacy Hebrew export requires current permission for its MT source"
        )
    units = []
    for unit in psalm["units"]:
        renderings = []
        for rendering in unit.get("renderings", []):
            provenance = rendering.get("provenance", {})
            source_ids = provenance.get("source_ids", []) if isinstance(provenance, dict) else []
            if (
                not source_ids
                or any(source_id not in allowed_source_ids for source_id in source_ids)
                or not _source_closure_exportable(rendering, allowed_source_ids)
            ):
                continue
            renderings.append(_rendering_for_export(rendering))
        export_unit = {
            "unit_id": unit["unit_id"],
            "ref": unit["ref"],
            "source_hebrew": unit["source_hebrew"],
            "source_transliteration": unit["source_transliteration"],
            "canonical_renderings": [item for item in renderings if item["status"] == "canonical"],
            "alternate_renderings": [
                item for item in renderings if item["status"] == "accepted_as_alternate"
            ],
            # Local histories contain free-form quotes and unrelated targets, without
            # export provenance. They remain local until scoped evidence exists.
            "audit_records": [],
            "review_decisions": [],
            "audit_export_state": "unscoped_local_history_omitted",
            "witnesses": [
                item
                for item in unit.get("witnesses", [])
                if item.get("source_id") in allowed_source_ids
                and _source_closure_exportable(item, allowed_source_ids)
            ],
        }
        units.append(export_unit)
    return {"psalm_id": psalm["psalm_id"], "title": psalm["title"], "units": units}


def _release_text_payload() -> list[dict[str, Any]]:
    payload = []
    for item in registry_service.list_psalm_ids():
        psalm = registry_service.load_psalm(item)
        for unit in psalm["units"]:
            review_service.hydrate_unit_review_state(unit)
        payload.append(_filter_exportable_units(psalm))
    return payload


def _plain_text_release(export_payload: list[dict[str, Any]]) -> str:
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


def _markdown_release(export_payload: list[dict[str, Any]]) -> str:
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


def _html_release(export_payload: list[dict[str, Any]]) -> str:
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


def _render_license(project: dict[str, Any], release_id: str) -> str:
    return (
        f"Release {release_id}\n\n"
        f"Text license: {project['output_text_license']}\n"
        f"Code license: {project['code_license']}\n"
        f"Release channel: {project['release_channel']}\n"
    )


def _render_notice(project: dict[str, Any], release_id: str) -> str:
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
    destination: Path, release_id: str, release_report: dict[str, Any]
) -> None:
    files = []
    for path in sorted(
        item
        for item in destination.iterdir()
        if item.is_file() and item.name != "bundle_manifest.json"
    ):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        files.append({"path": path.name, "sha256": digest})
    manifest = {
        "release_id": release_id,
        "generated_at": release_report["generated_at"],
        "bundle_hash": registry_service.file_hash(files),
        "files": files,
    }
    registry_service.write_json(destination / "bundle_manifest.json", manifest)


def _write_provenance_manifest(destination: Path, export_payload: list[dict[str, Any]]) -> None:
    entries: list[dict[str, Any]] = []
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


def _require_unchanged_policy(expected: str) -> None:
    if source_capability_service.policy_revision() != expected:
        raise LicensePolicyError("Source policy changed during export; retry the complete export")


def _prepare_destination(destination: Path, names: set[str]) -> None:
    if destination.exists() and any(
        path.name not in names or not path.is_file() or path.is_symlink()
        for path in destination.iterdir()
    ):
        raise LicensePolicyError(
            "Export directory contains unscoped files; choose an empty directory"
        )
    destination.mkdir(parents=True, exist_ok=True)


def _scoped_release_report(
    report: dict[str, Any], payload: list[dict[str, Any]], project: dict[str, Any]
) -> dict[str, Any]:
    """Project-wide reports contain unscoped source quotes; publish only this export's inventory."""
    allowed = _exportable_source_ids()
    canonical = [
        item
        for psalm in payload
        for unit in psalm["units"]
        for item in unit["canonical_renderings"]
    ]
    alternates = [
        item
        for psalm in payload
        for unit in psalm["units"]
        for item in unit["alternate_renderings"]
    ]
    return {
        "release_id": report["release_id"],
        "generated_at": report["generated_at"],
        "source_manifests": [
            item for item in project.get("source_manifests", []) if item["source_id"] in allowed
        ],
        "render_counts": {
            "total": len(canonical) + len(alternates),
            "canonical": len(canonical),
            "alternates": len(alternates),
        },
        "inventory": {"canonical_renderings": canonical, "accepted_alternates": alternates},
        "unresolved_warnings": {},
        "audit_export_state": "unscoped_local_reports_and_history_omitted",
    }


def export_book(psalm_id: str | None = None, output_dir: Path | None = None) -> Path:
    settings = get_settings()
    with workspace_lock(settings.data_dir / "local" / "study-publication.lock"):
        return _export_book_locked(psalm_id, output_dir)


def _export_book_locked(psalm_id: str | None, output_dir: Path | None) -> Path:
    policy = source_capability_service.policy_revision()
    _ensure_exportable()
    settings = get_settings()
    destination = output_dir or settings.release_reports_dir / "book-export"
    _prepare_destination(
        destination, {"book.json", "book.md", "book.txt", "book.html", "provenance_manifest.json"}
    )
    psalms = (
        [registry_service.load_psalm(psalm_id)]
        if psalm_id
        else [registry_service.load_psalm(item) for item in registry_service.list_psalm_ids()]
    )
    for psalm in psalms:
        for unit in psalm["units"]:
            review_service.hydrate_unit_review_state(unit)
    export_payload = [_filter_exportable_units(psalm) for psalm in psalms]
    _require_unchanged_policy(policy)
    registry_service.write_json(destination / "book.json", export_payload)
    (destination / "book.md").write_text(_markdown_release(export_payload), encoding="utf-8")
    (destination / "book.txt").write_text(_plain_text_release(export_payload), encoding="utf-8")
    (destination / "book.html").write_text(_html_release(export_payload), encoding="utf-8")
    _write_provenance_manifest(destination, export_payload)
    _require_unchanged_policy(policy)
    return destination


def export_release(release_id: str) -> Path:
    settings = get_settings()
    with workspace_lock(settings.data_dir / "local" / "study-publication.lock"):
        return _export_release_locked(release_id)


def _export_release_locked(release_id: str) -> Path:
    policy = source_capability_service.policy_revision()
    _ensure_exportable()
    settings = get_settings()
    destination = settings.release_reports_dir / release_id / "bundle"
    _prepare_destination(
        destination,
        {
            "text.json",
            "text.md",
            "text.txt",
            "text.html",
            "AUDIT_REPORT.json",
            "AUDIT_REPORT.md",
            "AUDIT_REPORT.html",
            "OPEN_CONCERNS.json",
            "OPEN_CONCERNS.md",
            "OPEN_CONCERNS.html",
            "release_manifest.json",
            "SOURCES.md",
            "SOURCES.html",
            "RELEASE_NOTES.md",
            "LICENSE",
            "NOTICE",
            "provenance_manifest.json",
            "bundle_manifest.json",
        },
    )

    # Keep the existing validation/review gates. Their local reports are not an
    # export dependency: they can contain excluded witnesses and free-form quotes.
    report = report_service.generate_release_report(release_id)
    export_payload = _release_text_payload()
    project = registry_service.load_project()
    release_report = _scoped_release_report(report, export_payload, project)
    project = {**project, "source_manifests": release_report["source_manifests"]}
    _require_unchanged_policy(policy)

    registry_service.write_json(destination / "text.json", export_payload)
    (destination / "text.md").write_text(_markdown_release(export_payload), encoding="utf-8")
    (destination / "text.txt").write_text(_plain_text_release(export_payload), encoding="utf-8")
    (destination / "text.html").write_text(_html_release(export_payload), encoding="utf-8")
    registry_service.write_json(destination / "AUDIT_REPORT.json", release_report)
    registry_service.write_json(
        destination / "OPEN_CONCERNS.json", release_report["unresolved_warnings"]
    )
    registry_service.write_json(destination / "release_manifest.json", release_report)
    scope_note = (
        "Local audit/review notes and project-wide concern reports are omitted because "
        "their source provenance is not scoped to this export. This is not a complete audit export."
    )
    sources = _render_notice(project, release_id)
    summary = (
        f"Release {release_id}\n\n"
        f"Canonical renderings: {release_report['render_counts']['canonical']}\n"
        f"Accepted alternates: {release_report['render_counts']['alternates']}\n\n{scope_note}\n"
    )
    from html import escape

    for name, text in {
        "AUDIT_REPORT": summary,
        "OPEN_CONCERNS": scope_note,
        "SOURCES": sources,
    }.items():
        (destination / f"{name}.md").write_text(text, encoding="utf-8")
        (destination / f"{name}.html").write_text(
            f"<html><body><pre>{escape(text)}</pre></body></html>", encoding="utf-8"
        )
    (destination / "RELEASE_NOTES.md").write_text(summary, encoding="utf-8")
    (destination / "LICENSE").write_text(_render_license(project, release_id), encoding="utf-8")
    (destination / "NOTICE").write_text(_render_notice(project, release_id), encoding="utf-8")
    _write_provenance_manifest(destination, export_payload)
    _write_bundle_manifest(destination, release_id, release_report)
    _require_unchanged_policy(policy)
    return destination
