from fastapi.testclient import TestClient

from app.api.main import app
from app.llm.base import GenerationResponse
from app.services import registry_service


client = TestClient(app)


class FakeAdapter:
    name = "fake-local"

    def __init__(self, profile: dict) -> None:
        self.profile = profile

    def generate_json(self, generation_request) -> GenerationResponse:
        layer = generation_request.metadata["layer"]
        unit_id = generation_request.metadata["unit_id"]
        candidate_count = generation_request.candidate_count
        return GenerationResponse(
            payload={
                "unit_id": unit_id,
                "layer": layer,
                "candidates": [
                    {
                        "text": f"{layer} candidate {index + 1}",
                        "rationale": f"{layer} rationale {index + 1}",
                        "alignment_hints": [f"aln.{unit_id}.{layer}.{index + 1:04d}"],
                        "drift_flags": [],
                        "metrics": {"syllables": 4 + index},
                    }
                    for index in range(candidate_count)
                ],
            },
            raw_text="{}",
            runtime_metadata={"provider": "fake"},
        )


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


def test_generation_job_is_reproducible_and_persists_output(monkeypatch) -> None:
    monkeypatch.setattr("app.services.generation_service.build_adapter", lambda profile: FakeAdapter(profile))

    payload = {
        "unit_id": "ps019.v001.a",
        "layer": "phrase",
        "style_profile": "study_literal",
        "candidate_count": 2,
        "seed": 77,
    }
    first = client.post("/jobs/generate", json=payload)
    second = client.post("/jobs/generate", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["job_id"] == second.json()["job_id"]
    assert first.json()["input_hash"] == second.json()["input_hash"]
    assert first.json()["runtime_metadata"]["candidate_count"] == 2
    assert len(first.json()["output"]["candidates"]) == 2

    unit = registry_service.load_unit("ps019.v001.a")
    phrase_renderings = [item for item in unit["renderings"] if item["layer"] == "phrase" and item["status"] == "proposed"]
    assert len(phrase_renderings) == 2


def test_rerun_invalidates_downstream_without_touching_locked_upstream(monkeypatch) -> None:
    monkeypatch.setattr("app.services.generation_service.build_adapter", lambda profile: FakeAdapter(profile))

    response = client.post(
        "/jobs/job.placeholder/retry",
        json={
            "unit_id": "ps001.v001.a",
            "layer": "literal",
            "style_profile": "study_literal",
            "seed": 42,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert "rnd.ps001.v001.a.lyric.alt.0001" in body["runtime_metadata"]["downstream_invalidated"]

    unit = registry_service.load_unit("ps001.v001.a")
    assert any(item["rendering_id"] == "rnd.ps001.v001.a.gloss.can.0001" for item in unit["renderings"])
    assert not any(item["rendering_id"] == "rnd.ps001.v001.a.lyric.alt.0001" for item in unit["renderings"])
    assert any(item["layer"] == "literal" and item["status"] == "proposed" for item in unit["renderings"])


def test_locked_layer_rejects_generation(monkeypatch) -> None:
    monkeypatch.setattr("app.services.generation_service.build_adapter", lambda profile: FakeAdapter(profile))

    response = client.post(
        "/jobs/generate",
        json={"unit_id": "ps001.v001.a", "layer": "gloss", "style_profile": "study_literal"},
    )

    assert response.status_code == 400
    assert "locked" in response.json()["detail"]
