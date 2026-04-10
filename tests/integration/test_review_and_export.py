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
        status="accepted_as_alternate",
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


def test_release_export_generates_bundle() -> None:
    destination = export_service.export_release("v0.1.0")
    assert (destination / "text.json").exists()
    assert (destination / "AUDIT_REPORT.json").exists()
    assert (destination / "OPEN_CONCERNS.md").exists()


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
