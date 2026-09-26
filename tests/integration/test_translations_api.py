from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.services import registry_service

client = TestClient(app)

PSALM_ID = "ps001"
UNIT_ID = "ps001.v001.a"


@pytest.fixture(autouse=True)
def _restore_psalm():
    meta = registry_service.load_psalm_meta(PSALM_ID)
    unit = registry_service.load_unit(UNIT_ID)
    yield
    registry_service.save_psalm_meta(PSALM_ID, meta)
    registry_service.save_unit(unit)


def _create(title: str = "Sung in 6/8") -> str:
    response = client.post(f"/psalms/{PSALM_ID}/translations", json={"title": title})
    assert response.status_code == 200
    return response.json()["translation_id"]


def _row(translation_id: str | None = None) -> dict:
    params = {"translation_id": translation_id} if translation_id else {}
    table = client.get(f"/psalms/{PSALM_ID}/comparison-table", params=params).json()
    return next(row for row in table["rows"] if UNIT_ID in row["unit_ids"])


def test_a_translation_is_created_listed_and_given_its_own_table() -> None:
    translation_id = _create()

    listed = client.get(f"/psalms/{PSALM_ID}/translations").json()
    assert [t["translation_id"] for t in listed] == [None, translation_id]
    table = client.get(
        f"/psalms/{PSALM_ID}/comparison-table", params={"translation_id": translation_id}
    ).json()
    assert table["translation_id"] == translation_id
    row = _row(translation_id)
    assert row["literal_text"] == _row()["literal_text"]
    assert row["english_text"] is None


def test_guidance_is_read_and_written_per_translation() -> None:
    translation_id = _create()

    saved = client.put(
        f"/psalms/{PSALM_ID}/translation-guidance",
        json={"translation_guidance": "Meter: 6/8", "translation_id": translation_id},
    )

    assert saved.status_code == 200
    read = client.get(
        f"/psalms/{PSALM_ID}/translation-guidance", params={"translation_id": translation_id}
    ).json()
    assert read["translation_guidance"] == "Meter: 6/8"
    main = client.get(f"/psalms/{PSALM_ID}/translation-guidance").json()
    assert main["translation_guidance"] != "Meter: 6/8"


def test_notes_and_song_settings_show_only_in_their_translation() -> None:
    translation_id = _create()

    note = client.post(
        f"/units/{UNIT_ID}/verse-notes",
        json={"text": "Keep it in 6/8.", "translation_id": translation_id},
    ).json()
    setting = client.post(
        f"/psalms/{PSALM_ID}/arrangements",
        json={"layer": "lyric", "title": "In 6/8", "translation_id": translation_id},
    ).json()

    assert [n["note_id"] for n in _row(translation_id)["verse_notes"]] == [note["note_id"]]
    assert note["note_id"] not in {n["note_id"] for n in _row()["verse_notes"]}
    arrangement_id = setting["arrangement"]["arrangement_id"]
    listed = client.get(
        f"/psalms/{PSALM_ID}/arrangements", params={"translation_id": translation_id}
    ).json()
    assert [a["arrangement_id"] for a in listed["arrangements"]] == [arrangement_id]
    main = client.get(f"/psalms/{PSALM_ID}/arrangements").json()
    assert arrangement_id not in {a["arrangement_id"] for a in main["arrangements"]}


def test_an_assessment_written_by_hand_belongs_to_its_translation() -> None:
    translation_id = _create()

    created = client.post(
        "/comparison-assessments",
        json={
            "unit_id": UNIT_ID,
            "literal_rendering_id": None,
            "english_rendering_id": None,
            "accuracy_rating": "adapted",
            "translation_id": translation_id,
        },
    )

    assert created.status_code == 200
    assert created.json()["translation_id"] == translation_id
    assert _row(translation_id)["accuracy_rating"] == "adapted"
    assert _row()["comparison_id"] != created.json()["comparison_id"]


def test_an_unknown_translation_is_not_found_and_an_unnamed_one_is_refused() -> None:
    missing = client.get(
        f"/psalms/{PSALM_ID}/comparison-table", params={"translation_id": "tr.ps001.0042"}
    )
    unnamed = client.post(f"/psalms/{PSALM_ID}/translations", json={"title": " "})

    assert missing.status_code == 404
    assert unnamed.status_code == 400
