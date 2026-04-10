import pytest

from app.core.errors import PublicationConstraintError, ReviewRequiredError
from app.services import export_service, registry_service, rendering_service, review_service


def test_review_gate_blocks_unreviewed_canonical_promotion() -> None:
    with pytest.raises(ReviewRequiredError):
        rendering_service.promote_rendering(
            "rnd.ps023.v001.a.lyric.alt.0001",
            reviewer="tester",
            reviewer_role="release reviewer",
        )


def test_promoting_alternate_preserves_id_and_rehomes_prior_canonical() -> None:
    created = rendering_service.create_rendering(
        unit_id="ps001.v001.a",
        layer="literal",
        text="Blessed is the man",
        status="proposed",
        rationale="alternate for promotion",
        created_by="test",
        style_tags=["most-literal"],
    )
    created_id = created["rendering_id"]

    review_service.add_review_decision(created_id, "approve", reviewer="reviewer-1", reviewer_role="release reviewer")
    review_service.add_review_decision(created_id, "approve", reviewer="reviewer-2", reviewer_role="release reviewer")
    rendering_service.promote_rendering(
        created_id,
        reviewer="reviewer-1",
        reviewer_role="release reviewer",
    )

    promoted_unit = registry_service.load_unit("ps001.v001.a")
    promoted = next(item for item in promoted_unit["renderings"] if item["rendering_id"] == created_id)
    prior_canonical = next(item for item in promoted_unit["renderings"] if item["rendering_id"] == "rnd.ps001.v001.a.literal.can.0001")

    assert promoted["status"] == "canonical"
    assert promoted["rendering_id"] == created_id
    assert prior_canonical["status"] == "accepted_as_alternate"
    assert promoted_unit["canonical_rendering_ids"] == ["rnd.ps001.v001.a.gloss.can.0001", created_id]
    assert "rnd.ps001.v001.a.literal.can.0001" in promoted_unit["alternate_rendering_ids"]
    assert promoted["review_signoff"]["publication_ready"] is True


def test_release_export_blocks_unsigned_canonical_renderings() -> None:
    created = rendering_service.create_rendering(
        unit_id="ps023.v001.a",
        layer="lyric",
        text="The shepherd-LORD remains near",
        status="proposed",
        rationale="candidate canonical line",
        created_by="test",
        style_tags=["lyric"],
    )
    review_service.add_review_decision(created["rendering_id"], "approve", reviewer="reviewer-1", reviewer_role="alignment reviewer")
    review_service.add_review_decision(created["rendering_id"], "approve", reviewer="reviewer-2", reviewer_role="Hebrew reviewer")
    rendering_service.promote_rendering(created["rendering_id"], reviewer="release-reviewer", reviewer_role="release reviewer")

    unit = registry_service.load_unit("ps023.v001.a")
    canonical = next(item for item in unit["renderings"] if item["rendering_id"] == created["rendering_id"])
    canonical["review_signoff"]["release_signoff"] = {}
    canonical["review_signoff"]["has_release_signoff"] = False
    canonical["review_signoff"]["publication_ready"] = False
    registry_service.save_unit(unit)

    with pytest.raises(ReviewRequiredError):
        export_service.export_release("v0.1.0-blocked")


def test_release_export_generates_bundle() -> None:
    destination = export_service.export_release("v0.1.0")
    assert (destination / "text.json").exists()
    assert (destination / "text.md").exists()
    assert (destination / "text.txt").exists()
    assert (destination / "text.html").exists()
    assert (destination / "AUDIT_REPORT.json").exists()
    assert (destination / "OPEN_CONCERNS.md").exists()
    assert (destination / "provenance_manifest.json").exists()
    assert (destination / "bundle_manifest.json").exists()


def test_high_drift_lyric_cannot_be_promoted_to_canonical() -> None:
    review_service.add_review_decision(
        "rnd.ps023.v001.a.lyric.alt.0001",
        decision="approve",
        reviewer="reviewer-1",
        reviewer_role="lyric reviewer",
    )
    review_service.add_review_decision(
        "rnd.ps023.v001.a.lyric.alt.0001",
        decision="approve",
        reviewer="reviewer-2",
        reviewer_role="theology reviewer",
    )
    rendering_service.update_rendering(
        "rnd.ps023.v001.a.lyric.alt.0001",
        {"text": "The gospel shepherd saves me"},
    )

    with pytest.raises(PublicationConstraintError):
        rendering_service.promote_rendering(
            "rnd.ps023.v001.a.lyric.alt.0001",
            reviewer="tester",
            reviewer_role="release reviewer",
        )


def test_export_blocks_canonical_high_severity_drift() -> None:
    _, unit = registry_service.update_unit("ps023.v001.a", lambda existing: existing)
    for rendering in unit["renderings"]:
        if rendering["rendering_id"] == "rnd.ps023.v001.a.literal.can.0001":
            rendering["drift_flags"] = [
                {
                    "code": "added_doctrine",
                    "severity": "high",
                    "confidence": 0.99,
                    "message": "Injected doctrine absent from source.",
                }
            ]
    registry_service.save_unit(unit)

    with pytest.raises(PublicationConstraintError):
        export_service.export_release("v0.1.0")


def test_release_export_is_reproducible_for_same_content() -> None:
    first = export_service.export_release("v0.1.0")
    first_report = (first / "release_manifest.json").read_text(encoding="utf-8")
    second = export_service.export_release("v0.1.0")
    second_report = (second / "release_manifest.json").read_text(encoding="utf-8")
    assert first_report == second_report
