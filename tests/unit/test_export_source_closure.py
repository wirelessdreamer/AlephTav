"""Legacy exports enforce current source permissions without copying local notes."""

from __future__ import annotations

import json
from copy import deepcopy

import pytest

from app.core.errors import LicensePolicyError
from app.services import export_service as export

pytestmark = pytest.mark.no_seeded_repo


@pytest.fixture
def legacy_export(tmp_path, monkeypatch):
    monkeypatch.setenv("ALEPHTAV_ROOT_DIR", str(tmp_path))
    project = {
        "output_text_license": "CC BY-SA 4.0",
        "code_license": "MIT",
        "release_channel": "test",
        "source_manifests": [
            {
                "source_id": name,
                "allowed_for_export": True,
                "name": name,
                "license": "Public Domain",
            }
            for name in ("uxlc", "macula", "lxx")
        ],
    }
    good = {
        "rendering_id": "rnd.ps001.v001.a.literal.can.0001",
        "layer": "literal",
        "status": "canonical",
        "text": "Permitted English",
        "alignment_ids": [],
        "provenance": {
            "source_ids": ["uxlc"],
            "generator": "human",
            "cached_prompt": "SECRET_LOCAL_NOTE",
        },
        "review_signoff": {"publication_ready": True, "notes": "SECRET_LOCAL_NOTE"},
        "rationale": "SECRET_LOCAL_NOTE",
    }
    greek = {
        **good,
        "rendering_id": "rnd.ps001.v001.a.literal.alt.0001",
        "status": "accepted_as_alternate",
        "text": "SECRET_GREEK",
        "provenance": {"source_ids": ["lxx"], "generator": "human"},
    }
    nested = {
        **greek,
        "provenance": {
            "source_ids": ["uxlc"],
            "generator": "human",
            "translation_basis": {"source_ids": ["lxx"]},
        },
    }
    macula = {
        **greek,
        "provenance": {"source_ids": ["macula"], "generator": "human"},
        "source_anchor": {"source_language": "grc", "source_text": "SECRET_GREEK"},
    }
    psalm = {
        "psalm_id": "ps001",
        "title": "Psalm 1",
        "units": [
            {
                "unit_id": "ps001.v001.a",
                "ref": "Psalm 1:1",
                "source_hebrew": "דָּבָר",
                "source_transliteration": "davar",
                "renderings": [good, greek, nested, macula],
                "audit_records": [{"summary": "SECRET_LOCAL_NOTE"}],
                "review_decisions": [{"note": "SECRET_LOCAL_NOTE"}],
                "witnesses": [
                    {"source_id": "lxx", "text": "SECRET_GREEK"},
                    {"source_id": "macula", "language": "grc", "text": "SECRET_GREEK"},
                ],
            }
        ],
    }
    monkeypatch.setattr(export.registry_service, "load_project", lambda: project)
    monkeypatch.setattr(export.registry_service, "load_psalm", lambda _: deepcopy(psalm))
    monkeypatch.setattr(export.registry_service, "list_psalm_ids", lambda: ["ps001"])
    monkeypatch.setattr(export, "_ensure_exportable", lambda: None)
    monkeypatch.setattr(export.review_service, "hydrate_unit_review_state", lambda _: None)
    monkeypatch.setattr(export.source_capability_service, "policy_revision", lambda: "policy.test")
    monkeypatch.setattr(
        export.source_capability_service,
        "effective_capabilities",
        lambda source, component=None: {"export": source != "lxx" and component != "greek"},
    )
    return tmp_path, psalm


def test_manifest_booleans_cannot_restore_revoked_lxx(legacy_export):
    _, psalm = legacy_export
    assert export._exportable_source_ids() == {"uxlc", "macula"}
    result = export._filter_exportable_units(psalm)
    assert result["units"][0]["source_hebrew"] == "דָּבָר"
    assert len(result["units"][0]["canonical_renderings"]) == 1
    assert result["units"][0]["alternate_renderings"] == []
    assert "SECRET" not in json.dumps(result)
    assert result["units"][0]["audit_export_state"] == "unscoped_local_history_omitted"


def test_book_output_keeps_permitted_hebrew_without_notes_or_revoked_witness(legacy_export):
    root, _ = legacy_export
    destination = export.export_book("ps001", root / "book")
    assert "דָּבָר" in (destination / "book.json").read_text(encoding="utf-8")
    assert "Permitted English" in (destination / "book.txt").read_text(encoding="utf-8")
    assert all("SECRET" not in path.read_text(encoding="utf-8") for path in destination.iterdir())


def test_release_outputs_use_scoped_inventory_instead_of_source_wide_reports(
    legacy_export, monkeypatch
):
    root, _ = legacy_export
    settings = export.get_settings()
    for directory, names in (
        (
            settings.release_reports_dir,
            [
                "AUDIT_REPORT.md",
                "AUDIT_REPORT.html",
                "SOURCES.md",
                "SOURCES.html",
                "RELEASE_NOTES.md",
            ],
        ),
        (settings.audit_reports_dir, ["open_concerns.md", "open_concerns.html"]),
    ):
        for name in names:
            (directory / name).write_text("SECRET_LOCAL_REPORT", encoding="utf-8")
    monkeypatch.setattr(
        export.report_service,
        "generate_release_report",
        lambda _: {
            "release_id": "test-release",
            "generated_at": "2026-10-17T00:00:00Z",
            "unresolved_warnings": {"source_text": "SECRET_LOCAL_REPORT"},
            "inventory": {"canonical_renderings": [{"text": "SECRET_GREEK"}]},
        },
    )
    destination = export.export_release("test-release")
    assert destination.is_relative_to(root)
    assert all("SECRET" not in path.read_text(encoding="utf-8") for path in destination.iterdir())
    report = json.loads((destination / "release_manifest.json").read_text(encoding="utf-8"))
    assert report["render_counts"] == {"total": 1, "canonical": 1, "alternates": 0}
    assert {source["source_id"] for source in report["source_manifests"]} == {"uxlc", "macula"}


def test_current_hebrew_revocation_and_policy_races_block_export(legacy_export, monkeypatch):
    root, psalm = legacy_export
    monkeypatch.setattr(
        export.source_capability_service, "effective_capabilities", lambda *args: {"export": False}
    )
    with pytest.raises(LicensePolicyError, match="MT source"):
        export._filter_exportable_units(psalm)
    monkeypatch.setattr(
        export.source_capability_service, "effective_capabilities", lambda *args: {"export": True}
    )
    policies = iter(["policy.before", "policy.after"])
    monkeypatch.setattr(export.source_capability_service, "policy_revision", lambda: next(policies))
    with pytest.raises(LicensePolicyError, match="changed"):
        export.export_book("ps001", root / "book")
    assert not (root / "book" / "book.json").exists()


def test_source_policy_publication_waits_until_export_serialization_finishes(
    legacy_export, monkeypatch
):
    from threading import Event, Thread

    from app.services.immutable_file_service import workspace_lock

    root, _ = legacy_export
    serializing, attempted, published = Event(), Event(), Event()
    policy = ["policy.before"]
    monkeypatch.setattr(export.source_capability_service, "policy_revision", lambda: policy[0])
    original_write = export.registry_service.write_json

    def write(path, payload):
        if path.name == "book.json":
            serializing.set()
            assert attempted.wait(2)
            assert not published.wait(0.1), "policy changed while final export files were written"
        return original_write(path, payload)

    def publish_policy():
        if not serializing.wait(2):
            return
        attempted.set()
        with workspace_lock(root / "data" / "local" / "study-publication.lock"):
            policy[0] = "policy.after"
            published.set()

    monkeypatch.setattr(export.registry_service, "write_json", write)
    publisher = Thread(target=publish_policy)
    publisher.start()
    try:
        destination = export.export_book("ps001", root / "book")
    finally:
        publisher.join(5)
    assert published.is_set() and not publisher.is_alive()
    assert (destination / "book.json").exists()


def test_export_directory_cannot_mix_unscoped_existing_files(legacy_export):
    root, _ = legacy_export
    destination = root / "book"
    destination.mkdir()
    (destination / "unscoped.json").write_text("SECRET", encoding="utf-8")
    with pytest.raises(LicensePolicyError, match="unscoped files"):
        export.export_book("ps001", destination)
    assert not (destination / "book.json").exists()
    assert (destination / "unscoped.json").read_text(encoding="utf-8") == "SECRET"


def test_project_cannot_grant_export_to_a_forbidden_license_before_release_validation(monkeypatch):
    monkeypatch.setattr(
        export.registry_service,
        "load_project",
        lambda: {
            "source_manifests": [
                {
                    "source_id": "sefaria",
                    "license": "Custom-Restricted-Witness",
                    "allowed_for_export": True,
                }
            ]
        },
    )
    monkeypatch.setattr(export.registry_service, "audit_licenses", lambda: {"evaluations": []})
    # Use the real guard, rather than the lean fixture's isolated policy stub.
    with pytest.raises(LicensePolicyError, match="forbidden source license policy"):
        export._ensure_exportable()
