from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.services import registry_service

client = TestClient(app)

PSALM_ID = "ps001"
UNIT_ID = "ps001.v001.a"
BASE = f"/psalms/{PSALM_ID}/arrangements"


@pytest.fixture(autouse=True)
def _restore_psalm():
    meta = registry_service.load_psalm_meta(PSALM_ID)
    unit = registry_service.load_unit(UNIT_ID)
    yield
    registry_service.save_psalm_meta(PSALM_ID, meta)
    registry_service.save_unit(unit)


def test_a_setting_is_built_reviewed_and_read_through_the_api() -> None:
    tokens = [t["token_id"] for t in registry_service.load_unit(UNIT_ID)["tokens"]]

    listed = client.get(BASE).json()
    assert listed["arrangements"] == []
    assert listed["required_approvals"]["dropped"] == 2

    created = client.post(BASE, json={"title": "Song", "layer": "lyric"})
    assert created.status_code == 200
    arrangement_id = created.json()["arrangement"]["arrangement_id"]

    section = client.post(
        f"{BASE}/{arrangement_id}/sections", json={"kind": "chorus", "label": "Chorus"}
    ).json()["arrangement"]["sections"][0]
    view = client.post(
        f"{BASE}/{arrangement_id}/sections/{section['section_id']}/lines",
        json={
            "text": "Happy the one",
            "anchors": [{"unit_id": UNIT_ID, "token_ids": tokens[:1]}],
            "liberty": "compressed",
            "rationale": "Folds the blessing into three words.",
        },
    ).json()
    line_id = view["arrangement"]["sections"][0]["lines"][0]["line_id"]
    client.post(
        f"{BASE}/{arrangement_id}/sections",
        json={"kind": "chorus", "label": "Chorus", "repeat_of": section["section_id"]},
    )

    approved = client.post(
        f"{BASE}/{arrangement_id}/lines/{line_id}/approvals",
        json={"reviewer": "Ana", "reviewer_role": "lyric reviewer"},
    ).json()
    item = next(i for i in approved["liberties"] if i["key"] == line_id)
    assert item["settled"] is True
    assert [s["time"] for s in approved["sung"]] == [1, 2]

    refused = client.patch(f"{BASE}/{arrangement_id}", json={"status": "accepted"})
    assert refused.status_code == 409  # the Hebrew the song leaves out is not yet approved

    bad = client.post(
        f"{BASE}/{arrangement_id}/lines/{line_id}/approvals",
        json={"reviewer": "Ana", "reviewer_role": "nobody"},
    )
    assert bad.status_code == 400

    assert client.get(f"{BASE}/arr.ps001.0099").status_code == 404
