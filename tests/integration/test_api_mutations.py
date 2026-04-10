from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.main import app


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
