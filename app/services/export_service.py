from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.core.errors import LicensePolicyError
from app.services import audit_service, registry_service, report_service


def _ensure_exportable() -> None:
    audit = registry_service.audit_licenses()
    if any("forbidden_for_export" in item["warnings"] for item in audit["evaluations"]):
        raise LicensePolicyError("Export blocked by forbidden source license policy")


def export_book(psalm_id: str | None = None, output_dir: Path | None = None) -> Path:
    _ensure_exportable()
    settings = get_settings()
    destination = output_dir or settings.release_reports_dir / "book-export"
    destination.mkdir(parents=True, exist_ok=True)
    psalms = [registry_service.load_psalm(psalm_id)] if psalm_id else [registry_service.load_psalm(item) for item in registry_service.list_psalm_ids()]
    export = []
    for psalm in psalms:
        export.append(
            {
                "psalm_id": psalm["psalm_id"],
                "units": [
                    {
                        "unit_id": unit["unit_id"],
                        "source_hebrew": unit["source_hebrew"],
                        "canonical_renderings": [
                            rendering for rendering in unit.get("renderings", []) if rendering["status"] == "canonical"
                        ],
                        "alternate_renderings": [
                            rendering for rendering in unit.get("renderings", []) if rendering["status"] == "accepted_as_alternate"
                        ],
                    }
                    for unit in psalm["units"]
                ],
            }
        )
    registry_service.write_json(destination / "book.json", export)
    return destination


def export_release(release_id: str) -> Path:
    _ensure_exportable()
    settings = get_settings()
    destination = settings.release_reports_dir / release_id / "bundle"
    destination.mkdir(parents=True, exist_ok=True)
    registry_service.write_json(destination / "text.json", [registry_service.load_psalm(item) for item in registry_service.list_psalm_ids()])
    report_service.generate_audit_reports()
    release_report = report_service.generate_release_report(release_id)
    registry_service.write_json(destination / "AUDIT_REPORT.json", release_report)
    (destination / "AUDIT_REPORT.md").write_text((settings.release_reports_dir / "AUDIT_REPORT.md").read_text(encoding="utf-8"), encoding="utf-8")
    (destination / "OPEN_CONCERNS.md").write_text((settings.audit_reports_dir / "open_concerns.md").read_text(encoding="utf-8"), encoding="utf-8")
    (destination / "SOURCES.md").write_text((settings.release_reports_dir / "SOURCES.md").read_text(encoding="utf-8"), encoding="utf-8")
    (destination / "LICENSE").write_text((settings.root_dir / "LICENSE-text-template").read_text(encoding="utf-8"), encoding="utf-8")
    (destination / "NOTICE").write_text((settings.root_dir / "NOTICE-template").read_text(encoding="utf-8"), encoding="utf-8")
    concerns = audit_service.open_concerns()
    registry_service.write_json(destination / "OPEN_CONCERNS.json", concerns)
    return destination
