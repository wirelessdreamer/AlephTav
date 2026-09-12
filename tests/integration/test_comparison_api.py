from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.main import app
from app.services import comparison_assessment_service, registry_service

client = TestClient(app)

UNIT_ID = "ps001.v001.a"


def _rendering_ids() -> tuple[str, str]:
    unit = registry_service.load_unit(UNIT_ID)
    literal = comparison_assessment_service.select_rendering(unit, "literal")
    english = comparison_assessment_service.select_rendering(unit, "lyric")
    assert literal is not None and english is not None
    return literal["rendering_id"], english["rendering_id"]


def test_comparison_table_endpoint_returns_the_five_semantic_columns() -> None:
    response = client.get("/psalms/ps001/comparison-table")
    assert response.status_code == 200

    table = response.json()
    assert table["psalm_id"] == "ps001"
    assert table["literal_layer"] == "literal"
    assert table["english_layer"] == "lyric"

    row = next(row for row in table["rows"] if UNIT_ID in row["unit_ids"])
    # The five semantic columns; the gutter is UI-only and never persisted.
    for field in (
        "hebrew_text",
        "literal_text",
        "english_text",
        "accuracy_rating",
        "creative_liberties_note",
    ):
        assert field in row
    assert "gutter" not in row
    assert row["mt_reference"]
    assert row["display_reference"]


def test_comparison_table_honors_a_requested_english_layer() -> None:
    response = client.get(
        "/psalms/ps001/comparison-table", params={"english_layer": "metered_lyric"}
    )
    assert response.status_code == 200

    table = response.json()
    assert table["english_layer"] == "metered_lyric"
    row = next(row for row in table["rows"] if UNIT_ID in row["unit_ids"])
    # Nothing exists at that layer, so the row reports itself incomplete.
    assert row["english_text"] is None
    assert row["incomplete"] is True


def test_create_and_revise_assessment_endpoints_preserve_the_original() -> None:
    literal_id, english_id = _rendering_ids()

    created = client.post(
        "/comparison-assessments",
        json={
            "unit_id": UNIT_ID,
            "literal_rendering_id": literal_id,
            "english_rendering_id": english_id,
            "accuracy_rating": "adapted",
            "accuracy_note": "Original generated note.",
            "creative_liberties_note": "Modernised diction.",
            "created_by": "codex-run",
            "created_via": "codex",
            "generator_provider": "codex-app-server",
            "status": "proposed",
        },
    )
    assert created.status_code == 200, created.text
    original = created.json()
    assert original["created_via"] == "codex"
    assert original["status"] == "proposed"

    revised = client.patch(
        f"/comparison-assessments/{original['comparison_id']}",
        json={
            "unit_id": UNIT_ID,
            "accuracy_rating": "close",
            "accuracy_note": "Reviewer adjusted.",
            "reviewer_id": "rev-7",
            "created_by": "reviewer",
        },
    )
    assert revised.status_code == 200, revised.text
    successor = revised.json()
    assert successor["revision_of"] == original["comparison_id"]
    assert successor["accuracy_rating"] == "close"
    assert successor["reviewer_id"] == "rev-7"

    listed = client.get("/psalms/ps001/comparison-assessments")
    assert listed.status_code == 200
    active = listed.json()
    assert [item["comparison_id"] for item in active] == [successor["comparison_id"]]

    everything = client.get(
        "/psalms/ps001/comparison-assessments", params={"include_superseded": True}
    ).json()
    by_id = {item["comparison_id"]: item for item in everything}
    assert by_id[original["comparison_id"]]["status"] == "superseded"
    assert by_id[original["comparison_id"]]["accuracy_note"] == "Original generated note."


def test_create_assessment_rejects_an_unknown_accuracy_rating() -> None:
    literal_id, english_id = _rendering_ids()

    response = client.post(
        "/comparison-assessments",
        json={
            "unit_id": UNIT_ID,
            "literal_rendering_id": literal_id,
            "english_rendering_id": english_id,
            "accuracy_rating": "not_a_rating",
        },
    )
    assert response.status_code == 400


def test_comparison_table_for_unknown_psalm_is_not_found() -> None:
    assert client.get("/psalms/ps999/comparison-table").status_code == 404
