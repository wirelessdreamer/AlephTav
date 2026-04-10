import unicodedata

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
    assert token.json()["same_psalms"] == ["Psalm 32:1"]
    assert token.json()["wider_corpus"] == ["Psalm 32:1"]
    assert token.json()["concordance_entry"]["lemma"]["match_count"] >= 1
    expected_copy_reference = unicodedata.normalize("NFC", "Psalm 1:1a • אַשְׁרֵי • ps001.v001.t001")
    assert unicodedata.normalize("NFC", token.json()["copy_reference"]) == expected_copy_reference


def test_concordance_search_returns_local_results() -> None:
    response = client.get("/search/concordance", params={"query": "H7462", "field": "strong"})
    assert response.status_code == 200
    assert response.json()[0]["token_id"] == "ps023.v001.t002"
    assert response.json()[0]["gloss_list"] == ["shepherd", "my shepherd"]

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
    assert occurrences.json()["counts"]["wider_corpus"] == 1


def test_advanced_search_can_include_witness_namespace_without_mixing_it() -> None:
    canonical_only = client.get("/search/advanced", params={"query": "Optional", "scope": "all"})
    assert canonical_only.status_code == 200
    assert canonical_only.json() == []

    with_witnesses = client.get(
        "/search/advanced",
        params={"query": "Optional", "scope": "all", "include_witnesses": "true"},
    )
    assert with_witnesses.status_code == 200
    assert with_witnesses.json()[0]["namespace"] == "witness"
    assert with_witnesses.json()[0]["unit_id"] == "ps001.v001.a"


def test_advanced_search_and_preset_views_return_navigation_targets() -> None:
    search_response = client.get("/search/advanced", params={"query": "declaring", "scope": "english_renderings"})
    assert search_response.status_code == 200
    assert search_response.json()[0]["unit_id"] == "ps019.v001.a"
    assert search_response.json()[0]["kind"] == "rendering"

    drift_response = client.get("/search/presets/units_with_unresolved_drift")
    assert drift_response.status_code == 200
    unit_ids = {item["unit_id"] for item in drift_response.json()}
    assert "ps001.v001.a" in unit_ids
    assert "ps023.v001.a" in unit_ids

    meter_response = client.get("/search/presets/alternates_meter_fit")
    assert meter_response.status_code == 200
    assert {item["unit_id"] for item in meter_response.json()} == {"ps023.v001.a"}


def test_unit_witness_endpoint_returns_isolated_metadata() -> None:
    response = client.get("/units/ps001.v001.a/witnesses")
    assert response.status_code == 200
    witness = response.json()[0]
    assert witness["namespace"] == "witness"
    assert witness["canonical_ref"] == "Psalm 1:1a"
    assert witness["versionTitle"] == "Fixture Witness"


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


def test_lexicon_routes_return_indexed_matches() -> None:
    lemma = client.get("/lexicon/lemma/אשר")
    assert lemma.status_code == 200
    assert lemma.json()["lemma"] == "אשר"
    assert lemma.json()["match_count"] == 1
    assert lemma.json()["matches"][0]["token_id"] == "ps001.v001.t001"

    strong = client.get("/lexicon/strong/H7462")
    assert strong.status_code == 200
    assert strong.json()["strong"] == "H7462"
    assert strong.json()["match_count"] == 1
    assert strong.json()["matches"][0]["token_id"] == "ps023.v001.t002"


def test_pinned_lexical_card_state_round_trip() -> None:
    initial = client.get("/state/lexical-card")
    assert initial.status_code == 200
    assert initial.json()["token_id"] is None

    pinned = client.put("/state/lexical-card", json={"token_id": "ps023.v001.t002"})
    assert pinned.status_code == 200
    assert pinned.json()["token_id"] == "ps023.v001.t002"
    assert pinned.json()["token"]["strong"] == "H7462"

    cleared = client.put("/state/lexical-card", json={"token_id": None})
    assert cleared.status_code == 200
    assert cleared.json()["token_id"] is None
    assert cleared.json()["token"] is None
