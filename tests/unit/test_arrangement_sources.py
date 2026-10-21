"""Arrangement source reads keep Hebrew and edition-bound Greek beside every verse."""

from __future__ import annotations

from copy import deepcopy

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import arrangements as routes
from app.core.errors import LicensePolicyError, NotFoundError
from app.services import arrangement_service as arrangements
from app.services import briefing_source_service as sources
from tests.unit.test_briefing_sources import source_view as _source_view

pytestmark = pytest.mark.no_seeded_repo
source_view = _source_view


@pytest.fixture
def arrangement_psalm(source_view, monkeypatch):
    root, _, _ = source_view
    psalm = {
        "psalm_id": "ps025",
        "units": [
            {
                "unit_id": "ps025.v001.a",
                "ref": "Psalm 25:1",
                "tokens": [
                    {
                        "token_id": "ps025.v001.t001",
                        "surface": "דָּבָר",
                        "display_gloss": "word",
                        "greek": "FORBIDDEN-HEBREW-ORDER-HINT",
                    }
                ],
            },
            {
                "unit_id": "ps025.v002.a",
                "ref": "Psalm 25:2",
                "tokens": [
                    {"token_id": "ps025.v002.t001", "surface": "אֵל", "display_gloss": "God"}
                ],
            },
        ],
        "arrangements": [{"arrangement_id": "arr.ps025.0001", "sections": [], "omissions": []}],
    }
    monkeypatch.setattr(arrangements.registry_service, "load_psalm", lambda _: psalm)
    monkeypatch.setattr(
        arrangements, "required_approvals", lambda: arrangements.DEFAULT_REQUIRED_APPROVALS
    )
    return root, psalm


def test_arrangement_read_attaches_snapshot_bound_greek_without_mutating_sources(arrangement_psalm):
    root, psalm = arrangement_psalm
    before = deepcopy(psalm)
    files_before = {
        path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()
    }
    result = arrangements.arrangement_view("ps025", "arr.ps025.0001")
    assert [unit["tokens"][0]["surface"] for unit in result["coverage"]["units"]] == ["דָּבָר", "אֵל"]
    assert result["greek_sources"]["study_snapshot_id"] == "study.test"
    assert result["greek_sources"]["policy_revision_id"] == "policy.test"
    greek = result["greek_sources"]["by_mt_unit"]["ps025.v001.a"]["units"][0]
    assert greek["unit_id"] == "lxx.authored.r0001.ps024.v001.a"
    assert greek["source_greek"] == "λόγος"
    assert "ps025.v002.a" not in result["greek_sources"]["by_mt_unit"]
    assert "FORBIDDEN-HEBREW-ORDER-HINT" not in str(result["greek_sources"])
    assert before == psalm
    assert files_before == {
        path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()
    }


@pytest.mark.parametrize(
    "error",
    [
        NotFoundError("No active study snapshot"),
        LicensePolicyError("Authored source revocation"),
        ValueError("Authored corrupt source package"),
    ],
)
def test_arrangement_route_keeps_hebrew_when_greek_is_missing_or_blocked(
    arrangement_psalm, monkeypatch, error
):
    def unavailable():
        raise error

    monkeypatch.setattr(sources.greek_study_service, "load_view", unavailable)
    app = FastAPI()
    app.include_router(routes.router)
    with TestClient(app) as client:
        response = client.get("/psalms/ps025/arrangements/arr.ps025.0001")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["coverage"]["units"]) == 2
    assert payload["coverage"]["units"][0]["tokens"][0]["surface"] == "דָּבָר"
    assert payload["greek_sources"]["available"] is False
    assert payload["greek_sources"]["by_mt_unit"] == {}
    assert payload["greek_sources"]["message"]
    assert "FORBIDDEN-HEBREW-ORDER-HINT" not in response.text


def test_arrangement_route_returns_greek_for_the_correct_mt_unit(arrangement_psalm):
    app = FastAPI()
    app.include_router(routes.router)
    with TestClient(app) as client:
        response = client.get("/psalms/ps025/arrangements/arr.ps025.0001")
    assert response.status_code == 200
    greek = response.json()["greek_sources"]
    assert greek["edition_id"] == "authored" and greek["text_revision_id"] == "r0001"
    assert greek["by_mt_unit"]["ps025.v001.a"]["units"][0]["ref"] == "Greek Psalm 24:1"
    assert "ps025.v002.a" not in greek["by_mt_unit"]
