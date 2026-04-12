import unicodedata

from fastapi.testclient import TestClient

from app.api.main import app
from app.llm.base import GenerationResponse
from app.services import registry_service, settings_service


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


class FakeAssistantAdapter:
    name = "fake-assistant"

    def __init__(self, profile: dict) -> None:
        self.profile = profile

    def generate_json(self, generation_request) -> GenerationResponse:
        prompt = generation_request.prompt
        if "User message:\nShow me the project configuration" in prompt:
            payload = {
                "reply": "Loading the project.",
                "speakable_text": "Loading the project.",
                "tool_calls": [{"action_id": "project.get", "input": {}}],
            }
        elif "User message:\nOpen the workbench" in prompt:
            payload = {
                "reply": "Opening the workbench.",
                "speakable_text": "Opening the workbench.",
                "tool_calls": [{"action_id": "navigate.route", "input": {"route": "workbench"}}],
            }
        elif "User message:\nOpen the compare tab" in prompt:
            payload = {
                "reply": "Opening compare mode.",
                "speakable_text": "Opening compare mode.",
                "tool_calls": [{"action_id": "workbench.set_drawer_tab", "input": {"tab": "compare"}}],
            }
        else:
            payload = {
                "reply": "I can prepare a rendering.",
                "speakable_text": "I can prepare a rendering.",
                "tool_calls": [
                    {
                        "action_id": "renderings.create",
                        "input": {
                            "unit_id": "ps019.v001.a",
                            "layer": "lyric",
                            "text": "Assistant drafted line",
                            "status": "proposed",
                            "rationale": "assistant test",
                        },
                    }
                ],
            }
        return GenerationResponse(payload=payload, raw_text="{}", runtime_metadata={})


def test_health_and_project_endpoints() -> None:
    assert client.get("/health").json() == {"status": "ok"}
    project = client.get("/project")
    assert project.status_code == 200
    assert project.json()["project_id"] == "proj.main"


def test_assistant_endpoints_support_navigation_read_tools_and_confirmed_writes(monkeypatch) -> None:
    monkeypatch.setattr("app.services.assistant_service.build_adapter", lambda profile: FakeAssistantAdapter(profile))
    settings_service.update_settings({"assistant": {"model_profile_id": "demo-local"}})

    tools = client.get("/assistant/tools")
    assert tools.status_code == 200
    assert any(item["action_id"] == "renderings.create" for item in tools.json())
    assert any(item["action_id"] == "workbench.set_drawer_tab" for item in tools.json())
    assert any(item["result_schema"]["type"] == "object" for item in tools.json())

    session = client.post("/assistant/sessions")
    assert session.status_code == 200
    session_id = session.json()["session_id"]

    navigation = client.post(
        f"/assistant/sessions/{session_id}/messages",
        json={"message": "Open the workbench", "context": {"route": "welcome"}},
    )
    assert navigation.status_code == 200
    assert navigation.json()["message"]["client_actions"][0]["action_id"] == "navigate.route"
    assert navigation.json()["message"]["speakable_text"] == "Opening the workbench."

    compare_tab = client.post(
        f"/assistant/sessions/{session_id}/messages",
        json={"message": "Open the compare tab", "context": {"route": "workbench", "ui": {"drawerTab": "workflow"}}},
    )
    assert compare_tab.status_code == 200
    assert compare_tab.json()["message"]["client_actions"][0]["action_id"] == "workbench.set_drawer_tab"

    read_result = client.post(
        f"/assistant/sessions/{session_id}/messages",
        json={"message": "Show me the project configuration", "context": {"route": "welcome"}},
    )
    assert read_result.status_code == 200
    assert read_result.json()["message"]["tool_results"][0]["action_id"] == "project.get"

    write_result = client.post(
        f"/assistant/sessions/{session_id}/messages",
        json={"message": "Draft a lyric rendering", "context": {"route": "workbench"}},
    )
    assert write_result.status_code == 200
    preview = write_result.json()["message"]["pending_actions"][0]
    assert preview["action_id"] == "renderings.create"

    denied = client.post(
        "/assistant/actions/execute",
        json={"action_id": "renderings.create", "input": preview["input"]},
    )
    assert denied.status_code == 400
    assert "requires confirmation" in denied.json()["detail"]

    executed = client.post(
        "/assistant/actions/execute",
        json={
            "action_id": "renderings.create",
            "input": preview["input"],
            "confirmation_token": preview["confirmation_token"],
        },
    )
    assert executed.status_code == 200
    assert executed.json()["result"]["text"] == "Assistant drafted line"


def test_speech_transcription_uses_saved_openai_settings(monkeypatch) -> None:
    settings_service.update_settings(
        {
            "openai": {
                "api_key": "sk-test",
                "base_url": "https://api.openai.example/v1",
                "whisper_model": "whisper-fixture",
            }
        }
    )

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b'{"text":"Fixture transcript"}'

    def fake_urlopen(request, timeout):
        assert request.full_url == "https://api.openai.example/v1/audio/transcriptions"
        assert request.headers["Authorization"] == "Bearer sk-test"
        assert timeout == 60
        return FakeResponse()

    monkeypatch.setattr("app.services.speech_service.request.urlopen", fake_urlopen)

    response = client.post(
        "/speech/transcriptions",
        files={"file": ("fixture.wav", b"audio-bytes", "audio/wav")},
    )

    assert response.status_code == 200
    assert response.json()["text"] == "Fixture transcript"
    assert response.json()["model"] == "whisper-fixture"


def test_public_assistant_settings_expose_provider_capabilities() -> None:
    settings_service.update_settings({"openai": {"api_key": ""}})
    response = client.get("/assistant/settings")
    assert response.status_code == 200
    payload = response.json()
    assert payload["providers"]["speech_to_text"]["provider"] == "openai"
    assert payload["providers"]["speech_to_text"]["auth_status"] == "not_configured"
    assert payload["providers"]["speech_to_text"]["account_link_available"] is False


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


def test_alternates_endpoints_support_filters_and_lifecycle_actions() -> None:
    list_response = client.get(
        "/units/ps023.v001.a/alternates",
        params={"layer": "lyric", "style_filter": "best_meter_fit", "release_approved_only": "false"},
    )
    assert list_response.status_code == 200
    assert [item["rendering_id"] for item in list_response.json()] == ["rnd.ps023.v001.a.lyric.alt.0001"]

    approved_only = client.get(
        "/units/ps023.v001.a/alternates",
        params={"layer": "lyric", "style_filter": "best_meter_fit", "release_approved_only": "true"},
    )
    assert approved_only.status_code == 200
    assert approved_only.json() == []

    created = client.post(
        "/units/ps019.v001.a/alternates",
        json={
            "layer": "lyric",
            "text": "A proposed lyric alternate",
            "rationale": "Keep a singable option in review",
            "style_goal": "best_lyric_flow",
            "metric_profile": "common_meter",
            "style_tags": ["lyric-flow", "contemporary"],
            "issue_links": ["issue.alt.ps019.v001.a.0001"],
            "pr_links": ["pr.alt.ps019.v001.a.0001"],
        },
    )
    assert created.status_code == 200
    rendering_id = created.json()["rendering_id"]
    assert created.json()["style_goal"] == "best_lyric_flow"
    assert created.json()["metric_profile"] == "common_meter"

    accepted = client.post(f"/alternates/{rendering_id}/accept", json={"created_by": "test"})
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "accepted_as_alternate"

    deprecated = client.post(f"/alternates/{rendering_id}/deprecate", json={"created_by": "test"})
    assert deprecated.status_code == 200
    assert deprecated.json()["status"] == "deprecated"

    rejected = client.post(f"/alternates/{rendering_id}/reject", json={"created_by": "test"})
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"


def test_compare_endpoint_supports_cross_layer_selection() -> None:
    response = client.get(
        "/units/ps001.v001.a/renderings/compare",
        params={
            "left_id": "rnd.ps001.v001.a.gloss.can.0001",
            "right_id": "rnd.ps001.v001.a.literal.can.0001",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["comparison"]["same_layer"] is False
    assert body["comparison"]["left_is_canonical"] is True
    assert body["comparison"]["right_is_canonical"] is True


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


def test_visual_flow_endpoints_return_full_psalm_canvas_and_cloud() -> None:
    visual_flow = client.get('/psalms/ps001/visual-flow')
    assert visual_flow.status_code == 200
    payload = visual_flow.json()
    assert payload['psalm_id'] == 'ps001'
    assert len(payload['units']) >= 1
    assert payload['units'][0]['default_rendering']['layer'] == 'literal'
    assert payload['cloud_nodes']

    cloud = client.get('/psalms/ps001/cloud')
    assert cloud.status_code == 200
    assert any(item['kind'] == 'concept' for item in cloud.json()['nodes'])
    assert any(item['kind'] == 'phrase' for item in cloud.json()['nodes'])



def test_retrieval_prefers_same_psalm_hits_before_cross_psalm_support() -> None:
    cloud = client.get('/psalms/ps001/cloud')
    assert cloud.status_code == 200
    node_id = cloud.json()['nodes'][0]['node_id']

    retrieval = client.get('/psalms/ps001/retrieval', params={'node_id': node_id, 'include_cross_psalm': 'true'})
    assert retrieval.status_code == 200
    hits = retrieval.json()['hits']
    assert hits
    assert hits[0]['scope'] == 'same_psalm'
    assert any(hit['scope'] == 'cross_psalm' for hit in hits)
