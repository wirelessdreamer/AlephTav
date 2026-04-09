from fastapi.testclient import TestClient

from app.api.main import app


client = TestClient(app)


def test_health_and_project_endpoints() -> None:
    assert client.get("/health").json() == {"status": "ok"}
    project = client.get("/project")
    assert project.status_code == 200
    assert project.json()["project_id"] == "proj.main"


def test_unit_and_token_endpoints_return_fixture_data() -> None:
    unit = client.get("/units/ps001.v001.a")
    assert unit.status_code == 200
    assert unit.json()["unit_id"] == "ps001.v001.a"

    token = client.get("/tokens/ps001.v001.t001")
    assert token.status_code == 200
    assert token.json()["lemma"] == "אשר"
    assert token.json()["enrichment_sources"]["oshb"]["status"] == "complete"
    assert token.json()["same_psalm_occurrence_refs"] == ["Psalm 1:1b"]


def test_concordance_search_returns_local_results() -> None:
    response = client.get("/search/concordance", params={"query": "H7462", "field": "strong"})
    assert response.status_code == 200
    assert response.json()[0]["token_id"] == "ps023.v001.t002"

    stem = client.get("/search/concordance", params={"query": "piel", "field": "stem"})
    assert stem.status_code == 200
    assert stem.json()[0]["token_id"] == "ps019.v001.t002"


def test_missing_enrichments_are_explicit_in_token_card_and_occurrences() -> None:
    token = client.get("/tokens/ps019.v001.t002")
    assert token.status_code == 200
    assert token.json()["referent"] is None
    assert token.json()["missing_enrichments"] == ["macula:referent"]
    assert token.json()["enrichment_sources"]["macula"]["status"] == "partial"

    occurrences = client.get("/tokens/ps001.v001.t001/occurrences")
    assert occurrences.status_code == 200
    assert occurrences.json()["same_psalm"] == ["Psalm 1:1b"]
    assert occurrences.json()["same_psalms"] == ["Psalm 32:1"]
