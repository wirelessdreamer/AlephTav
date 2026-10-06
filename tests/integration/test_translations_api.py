from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.core.config import get_settings
from app.services import registry_service

client = TestClient(app)

PSALM_ID = "ps001"
UNIT_ID = "ps001.v001.a"


@pytest.fixture(autouse=True)
def _restore_psalm():
    get_settings().collections_file.unlink(missing_ok=True)
    meta = registry_service.load_psalm_meta(PSALM_ID)
    unit = registry_service.load_unit(UNIT_ID)
    yield
    registry_service.save_psalm_meta(PSALM_ID, meta)
    registry_service.save_unit(unit)
    get_settings().collections_file.unlink(missing_ok=True)


def _project(title: str) -> str:
    response = client.post("/collections", json={"title": title})
    assert response.status_code == 200
    return response.json()["collection_id"]


def _create(title: str = "Sung in 6/8") -> str:
    response = client.post(
        f"/psalms/{PSALM_ID}/translations",
        json={"title": title, "collection_id": _project(title)},
    )
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


def test_projects_are_listed_created_renamed_and_hold_their_translations() -> None:
    translation_id = _create("Bone and Ash")

    listed = client.get("/collections").json()
    renamed = client.patch(f"/collections/{listed[1]['collection_id']}", json={"title": "Ash"})
    duplicate = client.post("/collections", json={"title": "ash"})
    default = client.patch("/collections/col.default", json={"title": "Mine"})

    assert [c["title"] for c in listed] == ["Main translations", "Bone and Ash"]
    assert listed[1]["members"] == [
        {"psalm_id": PSALM_ID, "translation_id": translation_id, "title": "Bone and Ash"}
    ]
    assert renamed.status_code == 200 and renamed.json()["title"] == "Ash"
    assert duplicate.status_code == 400
    assert default.status_code == 400


def test_a_projects_output_text_license_is_managed_independently() -> None:
    bone_and_ash = _project("Bone and Ash")
    hymnal = _project("Hymnal")

    licensed = client.patch(f"/collections/{bone_and_ash}", json={"output_text_license": "CC0 1.0"})
    refused = client.patch(f"/collections/{hymnal}", json={"output_text_license": "CC0"})
    listed = {c["collection_id"]: c for c in client.get("/collections").json()}

    assert licensed.status_code == 200
    assert listed[bone_and_ash]["output_text_license"] == "CC0 1.0"
    assert "output_text_license" not in listed[hymnal]
    assert refused.status_code == 400


def test_a_translation_moves_between_projects_but_not_into_one_with_the_psalm() -> None:
    translation_id = _create("Bone and Ash")
    hymnal = _project("Hymnal")

    moved = client.post(
        f"/psalms/{PSALM_ID}/translations/move",
        json={"translation_id": translation_id, "collection_id": hymnal},
    )
    refused = client.post(
        f"/psalms/{PSALM_ID}/translations/move",
        json={"translation_id": None, "collection_id": hymnal},
    )

    assert moved.status_code == 200 and moved.json()["collection_id"] == hymnal
    assert refused.status_code == 400
    listed = {c["collection_id"]: c for c in client.get("/collections").json()}
    assert [m["translation_id"] for m in listed[hymnal]["members"]] == [translation_id]


def test_a_translation_without_a_project_is_refused() -> None:
    missing = client.post(f"/psalms/{PSALM_ID}/translations", json={"title": "Loose"})
    unknown = client.post(
        f"/psalms/{PSALM_ID}/translations", json={"title": "Loose", "collection_id": "col.0042"}
    )

    assert missing.status_code == 400
    assert unknown.status_code == 404
