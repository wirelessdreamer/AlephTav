from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.main import app
from app.services import registry_service

client = TestClient(app)


def test_alignment_rendering_review_and_export_endpoints_cover_core_workflow() -> None:
    alignment_response = client.post(
        "/alignments",
        json={
            "unit_id": "ps019.v001.a",
            "layer": "phrase",
            "source_token_ids": ["ps019.v001.t001", "ps019.v001.t002"],
            "target_span_ids": ["spn.ps019.v001.a.phrase.0001"],
            "alignment_type": "grouped",
            "confidence": 0.88,
            "notes": "API coverage test",
        },
    )
    assert alignment_response.status_code == 200
    alignment_id = alignment_response.json()["alignment_id"]

    rendering_response = client.post(
        "/units/ps023.v001.a/renderings",
        json={
            "layer": "lyric",
            "text": "My shepherd-LORD will stay with me",
            "status": "proposed",
            "rationale": "API alternate coverage test",
            "created_by": "integration-test",
            "style_tags": ["lyric", "metered_common_meter"],
        },
    )
    assert rendering_response.status_code == 200
    rendering_id = rendering_response.json()["rendering_id"]

    for reviewer in ("reviewer-a", "reviewer-b"):
        review_response = client.post(
            f"/review/{rendering_id}/approve",
            json={
                "reviewer": reviewer,
                "reviewer_role": "alignment reviewer",
                "notes": "Looks good",
            },
        )
        assert review_response.status_code == 200

    promote_response = client.post(
        f"/renderings/{rendering_id}/promote",
        json={"reviewer": "release-check", "reviewer_role": "release reviewer"},
    )
    assert promote_response.status_code == 200
    assert promote_response.json()["status"] == "canonical"

    export_response = client.post("/export/release", json={"release_id": "v0.1.0-api"})
    assert export_response.status_code == 200
    assert export_response.json()["path"].endswith("/reports/release/v0.1.0-api/bundle")

    delete_response = client.delete(f"/alignments/{alignment_id}")
    assert delete_response.status_code == 200
    assert delete_response.json() == {"deleted": alignment_id}


def test_release_export_endpoint_blocks_forbidden_source_licenses() -> None:
    project = client.get("/project").json()
    for source in project["source_manifests"]:
        if source["source_id"] == "sefaria":
            source["allowed_for_export"] = True
    patch = client.patch("/project", json={"source_manifests": project["source_manifests"]})
    assert patch.status_code == 200

    export_response = client.post("/export/release", json={"release_id": "blocked-release"})

    assert export_response.status_code == 400
    assert "forbidden source license policy" in export_response.json()["detail"]


def test_editing_a_rendering_records_the_editor_in_the_audit_trail() -> None:
    created = client.post(
        "/units/ps023.v001.a/renderings",
        json={
            "layer": "lyric",
            "text": "A first draft line",
            "status": "proposed",
            "rationale": "edit tracking coverage",
            "created_by": "integration-test",
        },
    ).json()

    edited = client.patch(
        f"/renderings/{created['rendering_id']}",
        json={"text": "A line written by hand", "created_by": "nathanael"},
    )

    assert edited.status_code == 200, edited.text
    assert edited.json()["text"] == "A line written by hand"
    # The text changed in place; who changed it is recorded in the audit trail.
    assert edited.json()["rendering_id"] == created["rendering_id"]

    unit = registry_service.load_unit("ps023.v001.a")
    mine = [
        record for record in unit["audit_records"] if record["entity_id"] == created["rendering_id"]
    ]
    assert mine[-1]["created_by"] == "nathanael"
    assert mine[-1]["summary"] == "Update rendering"
