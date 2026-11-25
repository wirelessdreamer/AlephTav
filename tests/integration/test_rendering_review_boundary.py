from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.services import registry_service, rendering_service

UNIT_ID = "ps001.v001.a"
CANONICAL_ID = "rnd.ps001.v001.a.literal.can.0001"


def _proposal() -> dict[str, Any]:
    return rendering_service.create_rendering(
        UNIT_ID,
        "literal",
        "Blessed is the one",
        "proposed",
        "boundary regression",
        "test",
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"status": "canonical"},
        {"status": "accepted_as_alternate"},
        {"review_signoff": {"approval_count": 2, "publication_ready": True}},
        {"metrics": {"coverage": 1.0}},
        {"drift_flags": []},
        {"rendering_id": "rnd.ps001.v001.a.literal.alt.9999"},
        {"provenance": {"source_ids": ["uxlc"], "generator": "forged"}},
    ],
)
def test_http_cannot_inject_rendering_authority(changes: dict[str, Any]) -> None:
    proposal = _proposal()
    path = registry_service.unit_path(UNIT_ID)
    before = path.read_bytes()

    response = TestClient(app).patch(f"/renderings/{proposal['rendering_id']}", json=changes)

    assert response.status_code in {400, 409}, response.text
    assert path.read_bytes() == before


def test_http_cannot_edit_or_demote_canonical_content() -> None:
    path = registry_service.unit_path(UNIT_ID)
    before = path.read_bytes()
    client = TestClient(app)

    edit = client.patch(f"/renderings/{CANONICAL_ID}", json={"text": "Replaced"})
    demotion = client.post(f"/renderings/{CANONICAL_ID}/demote")

    assert edit.status_code == 409, edit.text
    assert demotion.status_code == 409, demotion.text
    assert path.read_bytes() == before


@pytest.mark.parametrize("decision", ["reject", "request-changes", "accept-alternate"])
def test_review_routes_cannot_demote_canonical_content(decision: str) -> None:
    path = registry_service.unit_path(UNIT_ID)
    before = path.read_bytes()

    response = TestClient(app).post(
        f"/review/{CANONICAL_ID}/{decision}",
        json={"reviewer": "test-reviewer", "reviewer_role": "Hebrew reviewer"},
    )

    assert response.status_code == 409, response.text
    assert path.read_bytes() == before


def test_review_of_unknown_target_does_not_persist_a_decision() -> None:
    path = registry_service.unit_path(UNIT_ID)
    before = path.read_bytes()

    response = TestClient(app).post(
        "/review/rnd.ps001.v001.a.literal.alt.9999/approve",
        json={"reviewer": "test-reviewer", "reviewer_role": "Hebrew reviewer"},
    )

    assert response.status_code == 404, response.text
    assert path.read_bytes() == before


def test_ineligible_acceptance_does_not_record_a_partial_review() -> None:
    proposal = _proposal()
    # An isolated fixture policy makes a single acceptance insufficient.
    project = registry_service.load_project()
    project["review_policy"]["alternate_required_approvals"] = 2
    registry_service.save_project(project)
    path = registry_service.unit_path(UNIT_ID)
    before = path.read_bytes()

    response = TestClient(app).post(
        f"/review/{proposal['rendering_id']}/accept-alternate",
        json={"reviewer": "one-reviewer", "reviewer_role": "Hebrew reviewer"},
    )

    assert response.status_code == 409, response.text
    assert path.read_bytes() == before


def test_explicit_http_review_retains_the_proposal_workflow() -> None:
    proposal = _proposal()
    canonical_before = next(
        r
        for r in registry_service.load_unit(UNIT_ID)["renderings"]
        if r["rendering_id"] == CANONICAL_ID
    )
    client = TestClient(app)
    payload = {"reviewer": "hebrew-reviewer", "reviewer_role": "Hebrew reviewer"}

    request_changes = client.post(
        f"/review/{proposal['rendering_id']}/request-changes", json=payload
    )
    assert request_changes.status_code == 200, request_changes.text
    assert request_changes.json()["status"] == "under_review"
    edited = client.patch(
        f"/renderings/{proposal['rendering_id']}",
        json={"text": "Blessed is the man", "created_by": "human-editor"},
    )
    assert edited.status_code == 200, edited.text
    accepted = client.post(f"/review/{proposal['rendering_id']}/accept-alternate", json=payload)
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "accepted_as_alternate"
    unit = registry_service.load_unit(UNIT_ID)
    canonical_after = next(r for r in unit["renderings"] if r["rendering_id"] == CANONICAL_ID)
    assert canonical_after["text"] == canonical_before["text"]
    assert canonical_after["status"] == canonical_before["status"]
