from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.core.config import get_settings
from app.core.errors import ContentError, ReviewRequiredError, ValidationError
from app.services import registry_service, rendering_service, review_service

pytestmark = pytest.mark.no_seeded_repo

UNIT_ID = "ps001.v001.a"
CANONICAL_ID = "rnd.ps001.v001.a.literal.can.0001"
PROPOSED_ID = "rnd.ps001.v001.a.literal.alt.0001"


@pytest.fixture(autouse=True)
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("ALEPHTAV_ROOT_DIR", str(tmp_path))
    registry_service.write_json(get_settings().project_file, {"source_manifests": []})
    unit: dict[str, Any] = {
        "unit_id": UNIT_ID,
        "ref": "Authored fixture",
        "tokens": [],
        "renderings": [
            {
                "rendering_id": rendering_id,
                "unit_id": UNIT_ID,
                "layer": "literal",
                "status": status,
                "text": "Blessed is the man",
                "style_tags": ["literal"],
                "target_spans": [],
                "alignment_ids": [],
                "drift_flags": [],
                "metrics": {},
                "review_signoff": {},
            }
            for rendering_id, status in (
                (CANONICAL_ID, "canonical"),
                (PROPOSED_ID, "proposed"),
            )
        ],
        "alignments": [],
        "canonical_rendering_ids": [CANONICAL_ID],
        "alternate_rendering_ids": [PROPOSED_ID],
        "review_decisions": [],
        "audit_records": [],
        "audit_ids": [],
    }
    path = registry_service.unit_path(UNIT_ID)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Deliberately noncanonical formatting detects even a premature no-op save.
    path.write_text(json.dumps(unit), encoding="utf-8")
    return path


@pytest.mark.parametrize(
    "changes",
    [
        {"status": "canonical"},
        {"status": "accepted_as_alternate"},
        {"status": "rejected"},
        {"review_signoff": {"approval_count": 2, "publication_ready": True}},
        {"approval_count": 2},
        {"rendering_id": "rnd.ps001.v001.a.literal.alt.9999"},
        {"unit_id": "ps001.v002.a"},
        {"layer": "lyric"},
        {"translation_id": "tr.ps001.0001"},
        {"alignment_ids": ["aln.ps001.v001.a.0001"]},
        {"provenance": {"generator": "reviewed"}},
        {"translation_basis": {"basis_type": "hebrew_to_english"}},
        {"source_anchor": {"source_id": "fabricated"}},
        {"metrics": {"singability_score": 1}},
        {"drift_flags": []},
        {"grounding_confidence": 1},
        {"unknown_field": "unvalidated"},
    ],
)
def test_generic_edits_reject_protected_fields_without_writing(
    workspace: Path, changes: dict[str, Any]
) -> None:
    before = workspace.read_bytes()

    with pytest.raises(ContentError):
        rendering_service.update_rendering(PROPOSED_ID, changes, created_by="editor")

    assert workspace.read_bytes() == before


def test_canonical_text_cannot_be_edited_even_with_existing_approvals(workspace: Path) -> None:
    for reviewer in ("hebrew-one", "hebrew-two"):
        review_service.add_review_decision(CANONICAL_ID, "approve", reviewer, "Hebrew reviewer")
    before = workspace.read_bytes()

    with pytest.raises(ReviewRequiredError, match="canonical"):
        rendering_service.update_rendering(CANONICAL_ID, {"text": "Replacement"})

    assert workspace.read_bytes() == before


def test_mixed_allowed_and_protected_fields_fail_as_one_request(workspace: Path) -> None:
    before = workspace.read_bytes()

    with pytest.raises(ContentError):
        rendering_service.update_rendering(
            PROPOSED_ID, {"text": "Replacement", "review_signoff": {"approval_count": 2}}
        )

    assert workspace.read_bytes() == before


def test_proposed_text_edit_is_audited_and_reanalyzed() -> None:
    updated = rendering_service.update_rendering(
        PROPOSED_ID,
        {"text": "Blessed is the one", "style_tags": ["most-literal"], "rationale": "clarify"},
        created_by="editor",
    )

    unit = registry_service.load_unit(UNIT_ID)
    assert updated["text"] == "Blessed is the one"
    assert updated["status"] == "proposed"
    assert updated["rendering_id"] == PROPOSED_ID
    assert unit["renderings"][0]["text"] == "Blessed is the man"
    assert unit["audit_records"][-1]["created_by"] == "editor"
    assert unit["audit_records"][-1]["summary"] == "Update rendering"
    assert updated["review_signoff"]["publication_ready"] is False


@pytest.mark.parametrize("rendering_id", [CANONICAL_ID, PROPOSED_ID])
def test_direct_demotion_never_accepts_a_rendering(workspace: Path, rendering_id: str) -> None:
    before = workspace.read_bytes()

    with pytest.raises(ReviewRequiredError):
        rendering_service.demote_rendering(rendering_id)

    assert workspace.read_bytes() == before


def test_acceptance_without_review_leaves_file_and_audit_unchanged(workspace: Path) -> None:
    before = workspace.read_bytes()

    with pytest.raises(ReviewRequiredError):
        rendering_service.set_alternate_status(PROPOSED_ID, "accepted_as_alternate")

    assert workspace.read_bytes() == before


def test_unreviewed_promotion_leaves_file_and_audit_unchanged(workspace: Path) -> None:
    before = workspace.read_bytes()

    with pytest.raises(ReviewRequiredError):
        rendering_service.promote_rendering(PROPOSED_ID, "release", "release reviewer")

    assert workspace.read_bytes() == before


@pytest.mark.parametrize("status", ["accepted_as_alternate", "rejected", "under_review"])
def test_alternate_transitions_cannot_demote_canonical(workspace: Path, status: str) -> None:
    before = workspace.read_bytes()

    with pytest.raises(ContentError):
        rendering_service.set_alternate_status(CANONICAL_ID, status)

    assert workspace.read_bytes() == before


def test_reviewed_acceptance_and_promotion_preserve_the_supported_workflow() -> None:
    review_service.add_review_decision(
        PROPOSED_ID, "accept-alternate", "hebrew-one", "Hebrew reviewer"
    )
    accepted = rendering_service.list_renderings(UNIT_ID, alternates_only=True)[0]
    assert accepted["status"] == "accepted_as_alternate"
    for reviewer in ("hebrew-one", "hebrew-two"):
        review_service.add_review_decision(PROPOSED_ID, "approve", reviewer, "Hebrew reviewer")

    promoted = rendering_service.promote_rendering(PROPOSED_ID, "release", "release reviewer")

    unit = registry_service.load_unit(UNIT_ID)
    assert promoted["rendering_id"] == PROPOSED_ID
    assert promoted["status"] == "canonical"
    assert unit["canonical_rendering_ids"] == [PROPOSED_ID]
    assert unit["alternate_rendering_ids"] == [CANONICAL_ID]
    assert promoted["review_signoff"]["publication_ready"] is True


@pytest.mark.parametrize(
    "decision,status", [("reject", "rejected"), ("request_changes", "under_review")]
)
def test_explicit_negative_review_transitions_remain_supported(decision: str, status: str) -> None:
    reviewed = review_service.add_review_decision(
        PROPOSED_ID, decision, "reviewer", "Hebrew reviewer", "needs work"
    )

    assert reviewed["status"] == status
    assert registry_service.load_unit(UNIT_ID)["audit_records"][-1]["created_by"] == "reviewer"


def test_source_anchor_recovery_is_explicit_and_only_for_proposals(workspace: Path) -> None:
    anchor = {"source_id": "uxlc", "source_revision": "fixture"}
    restored = rendering_service.restore_proposed_source_anchor(
        PROPOSED_ID, anchor, audit_rationale="recover verified candidate"
    )
    assert restored["source_anchor"] == anchor
    assert registry_service.load_unit(UNIT_ID)["audit_records"][-1]["rationale"] == (
        "recover verified candidate"
    )
    before = workspace.read_bytes()

    with pytest.raises(ValidationError, match="existing anchor"):
        rendering_service.restore_proposed_source_anchor(
            PROPOSED_ID, {"source_id": "replacement"}, audit_rationale="cannot replace"
        )

    assert workspace.read_bytes() == before

    with pytest.raises(ReviewRequiredError):
        rendering_service.restore_proposed_source_anchor(
            CANONICAL_ID, anchor, audit_rationale="not permitted"
        )

    assert workspace.read_bytes() == before


def test_invalid_transition_does_not_write(workspace: Path) -> None:
    before = workspace.read_bytes()
    with pytest.raises(ValidationError):
        rendering_service.set_alternate_status(PROPOSED_ID, "canonical")
    assert workspace.read_bytes() == before


@pytest.mark.parametrize("status", ["canonical", "accepted_as_alternate", "ready"])
def test_invalid_creation_status_does_not_write(workspace: Path, status: str) -> None:
    before = workspace.read_bytes()
    with pytest.raises(ContentError):
        rendering_service.create_rendering(
            UNIT_ID, "literal", "A new proposal", status, "test", "editor"
        )
    assert workspace.read_bytes() == before
