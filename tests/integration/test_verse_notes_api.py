from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.services import registry_service

client = TestClient(app)

UNIT_ID = "ps001.v001.a"


@pytest.fixture(autouse=True)
def _restore_unit():
    unit = registry_service.load_unit(UNIT_ID)
    yield
    registry_service.save_unit(unit)


def test_a_note_round_trips_through_the_api_and_shows_on_the_table_row() -> None:
    created = client.post(
        f"/units/{UNIT_ID}/verse-notes",
        json={"text": "Keep the “and”.", "applies_to": "both", "quote": "a semicolon"},
    )
    assert created.status_code == 200
    note_id = created.json()["note_id"]

    edited = client.patch(f"/units/{UNIT_ID}/verse-notes/{note_id}", json={"kind": "comment"})
    assert edited.json()["kind"] == "comment"

    row = next(
        row
        for row in client.get("/psalms/ps001/comparison-table").json()["rows"]
        if UNIT_ID in row["unit_ids"]
    )
    assert [n["note_id"] for n in row["verse_notes"]] == [note_id]
    assert row["pending_rebuild"] is None

    history = client.get(f"/units/{UNIT_ID}/verse-history").json()
    assert history["events"][0]["summary"] == "Update verse note"

    assert client.delete(f"/units/{UNIT_ID}/verse-notes/{note_id}").status_code == 200
    assert client.delete(f"/units/{UNIT_ID}/verse-notes/{note_id}").status_code == 404


def test_bad_notes_and_unknown_rebuilds_are_refused() -> None:
    bad = client.post(f"/units/{UNIT_ID}/verse-notes", json={"text": "x", "applies_to": "gloss"})
    assert bad.status_code == 400
    missing = client.post(f"/units/{UNIT_ID}/rebuilds/rb.{UNIT_ID}.0099/accept", json={})
    assert missing.status_code == 404


def test_word_suggestions_are_empty_until_generated() -> None:
    token_id = registry_service.load_unit(UNIT_ID)["tokens"][0]["token_id"]
    response = client.get(
        f"/units/{UNIT_ID}/word-suggestions", params={"token_ids": token_id, "layer": "lyric"}
    )
    assert response.status_code == 200
    assert response.json()["suggestions"] == []
