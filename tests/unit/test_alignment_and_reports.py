from __future__ import annotations

from app.core.config import get_settings
from app.services import alignment_service, registry_service, report_service


def test_alignment_coverage_flags_uncovered_tokens_and_unaligned_renderings() -> None:
    unit = registry_service.load_unit("ps019.v001.a")
    unit["alignments"] = []
    unit["renderings"][0]["alignment_ids"] = []

    result = alignment_service.coverage(unit)

    assert result["uncovered_tokens"] == ["ps019.v001.t001", "ps019.v001.t002"]
    assert result["unaligned_renderings"] == ["rnd.ps019.v001.a.literal.can.0001"]


def test_audit_and_release_reports_write_required_artifacts() -> None:
    settings = get_settings()

    concerns = report_service.generate_audit_reports()
    manifest = report_service.generate_release_report("v0.1.0-test")

    assert (settings.audit_reports_dir / "uncovered_tokens.json").exists()
    assert (settings.audit_reports_dir / "unaligned_spans.json").exists()
    assert (settings.audit_reports_dir / "open_drift_flags.json").exists()
    assert (settings.audit_reports_dir / "provenance_gaps.json").exists()
    assert (settings.audit_reports_dir / "open_concerns.md").exists()
    assert (settings.audit_reports_dir / "unit_change_log.md").exists()
    assert (settings.release_reports_dir / "release_manifest.json").exists()
    assert (settings.release_reports_dir / "RELEASE_NOTES.md").exists()
    assert (settings.release_reports_dir / "AUDIT_REPORT.md").exists()
    assert (settings.release_reports_dir / "SOURCES.md").exists()
    assert concerns["open_drift_flags"]
    assert manifest["release_id"] == "v0.1.0-test"
