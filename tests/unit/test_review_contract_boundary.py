from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from app.core.config import get_settings
from app.core.errors import ReviewRequiredError
from app.services import registry_service, rendering_service, report_service, review_service

pytestmark = pytest.mark.no_seeded_repo
UNIT_ID = "ps001.v001.a"
TARGET_ID = "rnd.ps001.v001.a.literal.can.0001"


def _legacy(index: int, target_id: str = TARGET_ID) -> dict[str, Any]:
    return {
        "decision_id": f"rev.{UNIT_ID}.{index:04d}",
        "target_id": target_id,
        "reviewer_role": "release reviewer",
        "reviewer": f"historical-{index}",
        "decision": "approve",
        "notes": "Historical approval remains verbatim",
        "timestamp": "2026-04-09T00:00:00Z",
    }


def _versioned(version: Any = 2, target_id: str = TARGET_ID) -> dict[str, Any]:
    return {
        **_legacy(3, target_id),
        "contract_version": version,
        "principal": {"principal_id": "person:three", "kind": "human"},
        "channel": "cli",
        "payload_digest": {"version": 2, "algorithm": "sha256", "value": "0" * 64},
        "policy_revision": "1" * 64,
    }


@pytest.fixture
def unit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    monkeypatch.setenv("ALEPHTAV_ROOT_DIR", str(tmp_path))
    registry_service.write_json(
        get_settings().project_file,
        {
            "source_manifests": [],
            "review_policy": {
                "alternate_required_approvals": 1,
                "canonical_required_approvals": 2,
                "release_required_role": "release reviewer",
                "reviewer_roles": ["release reviewer"],
            },
        },
    )
    return {
        "unit_id": UNIT_ID,
        "ref": "Authored review fixture",
        "tokens": [],
        "alignments": [],
        "audit_records": [],
        "audit_ids": [],
        "canonical_rendering_ids": [TARGET_ID],
        "alternate_rendering_ids": [],
        "renderings": [
            {
                "rendering_id": TARGET_ID,
                "layer": "literal",
                "status": "canonical",
                "text": "Unchanged canonical content",
                "target_spans": [],
                "metrics": {},
                "drift_flags": [],
                "review_signoff": {
                    "approval_count": 99,
                    "alternate_approval_count": 99,
                    "approvers": [{"reviewer": "cached"}],
                    "release_signoff": {"reviewer": "cached", "role": "release reviewer"},
                },
            }
        ],
        "review_decisions": [_legacy(1), _legacy(2)],
    }


def test_wholly_legacy_history_keeps_its_existing_interpretation(unit: dict[str, Any]) -> None:
    before = deepcopy(unit)

    summary = review_service.summarize_rendering_review(unit, TARGET_ID)

    assert summary["approval_count"] == 99
    assert summary["publication_ready"] is True
    assert report_service._review_summary(unit, TARGET_ID)["approval_count"] == 2
    assert unit == before


@pytest.mark.parametrize("version", [2, 3, None, False])
def test_versioned_target_cannot_borrow_legacy_or_cached_authority(
    unit: dict[str, Any], version: Any
) -> None:
    unit["review_decisions"].append(_versioned(version))
    before = deepcopy(unit)

    summary = review_service.summarize_rendering_review(unit, TARGET_ID)

    assert summary["approval_count"] == 0
    assert summary["alternate_approval_count"] == 0
    assert summary["eligible_for_alternate"] is False
    assert summary["eligible_for_canonical"] is False
    assert summary["has_release_signoff"] is False
    assert summary["publication_ready"] is False
    assert summary["status"] == "under_review"
    assert summary["evidence_contract_status"] == "versioned_pending_activation"
    assert report_service._review_summary(unit, TARGET_ID) == {"approval_count": 0, "approvals": []}
    assert rendering_service._approvals_for(unit, TARGET_ID) == 0
    assert unit == before


def test_versioned_evidence_cannot_enable_a_zero_threshold_policy(unit: dict[str, Any]) -> None:
    project = registry_service.load_project()
    project["review_policy"]["canonical_required_approvals"] = 0
    project["review_policy"]["alternate_required_approvals"] = 0
    registry_service.save_project(project)
    unit["review_decisions"] = [_versioned()]

    summary = review_service.summarize_rendering_review(unit, TARGET_ID)

    assert summary["eligible_for_canonical"] is False
    assert summary["eligible_for_alternate"] is False


def test_other_targets_versioned_records_do_not_reinterpret_legacy_history(
    unit: dict[str, Any],
) -> None:
    unit["review_decisions"].append(_versioned(target_id="rnd.ps001.v001.a.lyric.alt.0001"))

    assert review_service.summarize_rendering_review(unit, TARGET_ID)["publication_ready"] is True
    assert rendering_service._approvals_for(unit, TARGET_ID) == 2


@pytest.mark.parametrize("action", ["legacy_review", "promotion"])
def test_versioned_target_cannot_downgrade_and_refusal_preserves_history(
    unit: dict[str, Any], action: str
) -> None:
    unit["review_decisions"].append(_versioned())
    registry_service.save_unit(unit)
    path = registry_service.unit_path(UNIT_ID)
    before = path.read_bytes()

    with pytest.raises(ReviewRequiredError):
        if action == "legacy_review":
            review_service.add_review_decision(
                TARGET_ID, "approve", "another-claimed-reviewer", "release reviewer"
            )
        else:
            rendering_service.promote_rendering(TARGET_ID, "claimed-release", "release reviewer")

    assert path.read_bytes() == before


def test_hydration_changes_only_the_derived_view_and_never_rewrites_history(
    unit: dict[str, Any],
) -> None:
    unit["review_decisions"].append(_versioned())
    registry_service.save_unit(unit)
    path = registry_service.unit_path(UNIT_ID)
    before_bytes = path.read_bytes()
    history = deepcopy(unit["review_decisions"])

    review_service.hydrate_unit_review_state(unit)

    assert unit["review_decisions"] == history
    assert unit["renderings"][0]["text"] == "Unchanged canonical content"
    assert unit["renderings"][0]["status"] == "canonical"
    assert unit["renderings"][0]["review_signoff"]["publication_ready"] is False
    assert path.read_bytes() == before_bytes


def test_release_approved_reader_cannot_surface_a_quarantined_target(unit: dict[str, Any]) -> None:
    unit["review_decisions"].append(_versioned())
    registry_service.save_unit(unit)
    path = registry_service.unit_path(UNIT_ID)
    before = path.read_bytes()

    assert rendering_service.list_renderings(UNIT_ID, release_approved_only=True) == []
    assert path.read_bytes() == before
