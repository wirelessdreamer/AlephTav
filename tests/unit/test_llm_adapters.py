from __future__ import annotations

from pathlib import Path

from app.core.errors import GenerationError
from app.llm.adapters.llamacpp import LlamaCppAdapter
from app.llm.base import GenerationRequest, GenerationResponse
from app.services import composer_suggestion_service, llama_runtime_service, registry_service


def _generation_request() -> GenerationRequest:
    return GenerationRequest(
        prompt="Return a constrained JSON object.",
        contract={
            "type": "object",
            "required": ["ok"],
            "additionalProperties": False,
            "properties": {"ok": {"type": "boolean"}},
        },
        model="local-composer",
        seed=42,
        temperature=0.2,
        max_tokens=256,
        system_prompt="Return JSON only.",
        candidate_count=1,
        timeout_seconds=15,
    )


def test_llamacpp_adapter_uses_schema_constrained_json_and_sampling_controls(monkeypatch) -> None:
    captured: dict[str, object] = {}
    adapter = LlamaCppAdapter(
        {
            "adapter": "llama.cpp",
            "base_url": "http://127.0.0.1:8080/v1",
            "model": "local-composer",
            "response_format_mode": "json_schema",
            "response_format_fallback": "json_object",
            "top_p": 0.9,
            "top_k": 40,
            "min_p": 0.05,
            "repeat_penalty": 1.05,
        }
    )

    def fake_post_json(url, payload, headers=None, timeout_seconds=30):
        captured["url"] = url
        captured["payload"] = payload
        captured["headers"] = headers
        captured["timeout_seconds"] = timeout_seconds
        return {
            "choices": [{"message": {"content": '{"ok": true}'}, "finish_reason": "stop"}],
            "usage": {"total_tokens": 7},
        }

    monkeypatch.setattr(adapter, "_post_json", fake_post_json)

    response = adapter.generate_json(_generation_request())

    payload = captured["payload"]
    assert captured["url"] == "http://127.0.0.1:8080/v1/chat/completions"
    assert payload["response_format"] == {
        "type": "json_schema",
        "schema": _generation_request().contract,
    }
    assert payload["top_p"] == 0.9
    assert payload["top_k"] == 40
    assert payload["min_p"] == 0.05
    assert payload["repeat_penalty"] == 1.05
    assert response.payload == {"ok": True}
    assert response.runtime_metadata["response_format"] == "json_schema"


def test_llamacpp_adapter_retries_with_plain_json_object_when_schema_mode_fails(monkeypatch) -> None:
    attempts: list[dict[str, object]] = []
    adapter = LlamaCppAdapter(
        {
            "adapter": "llama.cpp",
            "base_url": "http://127.0.0.1:8080/v1",
            "model": "local-composer",
            "response_format_mode": "json_schema",
            "response_format_fallback": "json_object",
        }
    )

    def fake_post_json(url, payload, headers=None, timeout_seconds=30):
        attempts.append(payload["response_format"])
        if len(attempts) == 1:
            raise GenerationError("schema mode rejected")
        return {
            "choices": [{"message": {"content": '{"ok": true}'}, "finish_reason": "stop"}],
            "usage": {"total_tokens": 5},
        }

    monkeypatch.setattr(adapter, "_post_json", fake_post_json)

    response = adapter.generate_json(_generation_request())

    assert attempts == [
        {"type": "json_schema", "schema": _generation_request().contract},
        {"type": "json_object", "schema": _generation_request().contract},
    ]
    assert response.payload == {"ok": True}
    assert response.runtime_metadata["response_format"] == "json_object"


def test_llamacpp_adapter_ensures_managed_runtime_before_request(monkeypatch) -> None:
    seen: dict[str, object] = {}
    adapter = LlamaCppAdapter(
        {
            "adapter": "llama.cpp",
            "base_url": "http://127.0.0.1:8080/v1",
            "model": "local-composer",
            "managed_process": True,
            "server_binary_path": "llama-server",
            "model_path": "models/local-composer.gguf",
            "response_format_mode": "json_schema",
            "response_format_fallback": "json_object",
        }
    )

    monkeypatch.setattr(
        "app.llm.adapters.llamacpp.llama_runtime_service.ensure_runtime",
        lambda profile: seen.setdefault("profile", profile),
    )
    monkeypatch.setattr(
        adapter,
        "_post_json",
        lambda url, payload, headers=None, timeout_seconds=30: {
            "choices": [{"message": {"content": '{"ok": true}'}, "finish_reason": "stop"}],
            "usage": {"total_tokens": 5},
        },
    )

    response = adapter.generate_json(_generation_request())

    assert seen["profile"]["managed_process"] is True
    assert response.payload == {"ok": True}


def test_managed_runtime_builds_child_process_command_and_waits_for_health(monkeypatch, tmp_path: Path) -> None:
    binary = tmp_path / "llama-server"
    binary.write_text("", encoding="utf-8")
    model = tmp_path / "composer.gguf"
    model.write_text("", encoding="utf-8")

    launched: dict[str, object] = {}

    class FakeProcess:
        def __init__(self, command):
            self.command = command
            self.returncode = None

        def poll(self):
            return self.returncode

        def terminate(self):
            self.returncode = 0

        def wait(self, timeout=None):
            self.returncode = 0
            return 0

        def kill(self):
            self.returncode = -9

    health_checks = iter([False, True])

    def fake_popen(command, stdout=None, stderr=None, text=None):
        launched["command"] = command
        launched["stdout"] = stdout
        return FakeProcess(command)

    monkeypatch.setattr("app.services.llama_runtime_service.subprocess.Popen", fake_popen)
    monkeypatch.setattr(
        "app.services.llama_runtime_service._health_ok",
        lambda profile, timeout_seconds=1.0: next(health_checks),
    )

    profile = {
        "model_profile_id": "composer-local",
        "adapter": "llama.cpp",
        "managed_process": True,
        "server_binary_path": str(binary),
        "model_path": str(model),
        "base_url": "http://127.0.0.1:8099/v1",
        "context_size": 8192,
        "batch_size": 1024,
        "parallel_slots": 2,
        "runtime_start_timeout_seconds": 1,
    }

    llama_runtime_service.ensure_runtime(profile)

    assert launched["command"] == [
        str(binary),
        "-m",
        str(model),
        "--host",
        "127.0.0.1",
        "--port",
        "8099",
        "-c",
        "8192",
        "-ub",
        "1024",
        "-np",
        "2",
    ]

    llama_runtime_service.shutdown_all()


def test_composer_suggestions_prefer_default_composer_profile(monkeypatch) -> None:
    seen: dict[str, object] = {}

    class FakeComposerAdapter:
        name = "fake-composer"

        def __init__(self, profile: dict[str, object]) -> None:
            seen["profile"] = profile

        def generate_json(self, generation_request) -> GenerationResponse:
            return GenerationResponse(
                payload={
                    "unit_id": generation_request.metadata["unit_id"],
                    "stage": generation_request.metadata["stage"],
                    "chunks": [
                        {
                            "chunk_id": "chunk-1",
                            "candidates": [
                                {
                                    "text": "phrase option 1",
                                    "rationale": "fixture rationale",
                                    "alignment_hints": ["seed-1"],
                                    "drift_flags": [],
                                    "metrics": {"confidence": 0.81},
                                }
                            ],
                        }
                    ],
                },
                raw_text="{}",
                runtime_metadata={},
            )

    monkeypatch.setattr(
        "app.services.composer_suggestion_service.build_adapter",
        lambda profile: FakeComposerAdapter(profile),
    )

    response = composer_suggestion_service.suggest_for_unit(
        unit_id="ps001.v001.a",
        stage="phrase",
        chunks=[
            {
                "chunk_id": "chunk-1",
                "start": 0,
                "end": 1,
                "text": "Blessed the man",
                "source_text": "אַשְׁרֵי הָאִישׁ",
                "confidence": 0.82,
                "confidence_reasons": ["fixture seed"],
            }
        ],
        candidate_count=1,
    )

    project = registry_service.load_project()
    assert seen["profile"]["model_profile_id"] == project["default_composer_model_profile"]
    assert response["available"] is True
    assert response["chunks"][0]["candidates"][0]["text"] == "phrase option 1"


def test_composer_suggestions_prompt_is_hebrew_grounded_and_style_driven(monkeypatch) -> None:
    seen: dict[str, object] = {}

    class FakeComposerAdapter:
        name = "fake-composer"

        def __init__(self, profile: dict[str, object]) -> None:
            seen["profile"] = profile

        def generate_json(self, generation_request) -> GenerationResponse:
            seen["prompt"] = generation_request.prompt
            seen["temperature"] = generation_request.temperature
            seen["metadata"] = generation_request.metadata
            return GenerationResponse(
                payload={
                    "unit_id": generation_request.metadata["unit_id"],
                    "stage": generation_request.metadata["stage"],
                    "chunks": [
                        {
                            "chunk_id": "chunk-1",
                            "candidates": [
                                {
                                    "text": "Speak it plainly\nthrough the dawn",
                                    "rationale": "cadence-first but still faithful",
                                    "alignment_hints": ["negation preserved"],
                                    "drift_flags": [],
                                    "metrics": {"confidence": 0.76},
                                }
                            ],
                        }
                    ],
                },
                raw_text="{}",
                runtime_metadata={},
            )

    monkeypatch.setattr(
        "app.services.composer_suggestion_service.build_adapter",
        lambda profile: FakeComposerAdapter(profile),
    )

    response = composer_suggestion_service.suggest_for_unit(
        unit_id="ps001.v001.a",
        stage="lyric",
        chunks=[
            {
                "chunk_id": "chunk-1",
                "start": 0,
                "end": 2,
                "text": "How blessed is the man",
                "source_text": "אַשְׁרֵי הָאִישׁ אֲשֶׁר",
                "confidence": 0.82,
                "confidence_reasons": ["fixture seed"],
            }
        ],
        candidate_count=1,
        style_profile="performative_free",
    )

    prompt = str(seen["prompt"])
    assert "Translate each chunk directly from the Hebrew token data provided below." in prompt
    assert '"style_profile_id": "performative_free"' in prompt
    assert '"hebrew_text":' in prompt
    assert '"lexical_tokens": [' in prompt
    assert '"source_anchor_candidates": [' in prompt
    assert '"deterministic_seed_english": "How blessed is the man"' in prompt
    assert "You may use newline characters inside candidate text to create sparse, breath-based lineation." in prompt
    assert "Every candidate must set delivery_profile and source_anchor." in prompt
    assert "4_4_direct" in prompt
    assert "6_8_lament" in prompt
    assert "performance_direction_leak" in prompt
    assert "King James Version" not in prompt
    assert response["available"] is True
    assert response["chunks"][0]["candidates"][0]["text"] == "Speak it plainly\nthrough the dawn"
    assert response["chunks"][0]["candidates"][0]["delivery_profile"] == "4_4_direct"
    assert response["chunks"][0]["candidates"][0]["source_anchor"]["anchor_text"] == "How blessed is the man"
    assert float(seen["temperature"]) > 0.2
    assert seen["metadata"]["style_profile"] == "performative_free"


def test_composer_suggestions_prompt_can_relax_divine_name_for_reader_facing_lament(monkeypatch) -> None:
    seen: dict[str, object] = {}

    class FakeComposerAdapter:
        name = "fake-composer"

        def __init__(self, profile: dict[str, object]) -> None:
            seen["profile"] = profile

        def generate_json(self, generation_request) -> GenerationResponse:
            seen["prompt"] = generation_request.prompt
            seen["metadata"] = generation_request.metadata
            return GenerationResponse(
                payload={
                    "unit_id": generation_request.metadata["unit_id"],
                    "stage": generation_request.metadata["stage"],
                    "chunks": [
                        {
                            "chunk_id": "chunk-1",
                            "candidates": [
                                {
                                    "text": "God, do not break me in your anger",
                                    "rationale": "reader-facing direct address",
                                    "alignment_hints": ["divine name handled as direct address"],
                                    "drift_flags": [],
                                    "metrics": {"confidence": 0.73},
                                }
                            ],
                        }
                    ],
                },
                raw_text="{}",
                runtime_metadata={},
            )

    monkeypatch.setattr(
        "app.services.composer_suggestion_service.build_adapter",
        lambda profile: FakeComposerAdapter(profile),
    )

    response = composer_suggestion_service.suggest_for_unit(
        unit_id="ps001.v001.a",
        stage="concept",
        chunks=[
            {
                "chunk_id": "chunk-1",
                "start": 0,
                "end": 3,
                "text": "O Yahweh do not rebuke me in your anger",
                "source_text": "יְהוָה אַל-בְּאַפְּךָ תוֹכִיחֵנִי",
                "confidence": 0.8,
                "confidence_reasons": ["fixture seed"],
            }
        ],
        candidate_count=2,
        style_profile="doubter_lament",
    )

    prompt = str(seen["prompt"])
    assert '"style_profile_id": "doubter_lament"' in prompt
    assert "configured divine-name handling" in prompt
    assert "let one candidate use 'God' or 'my God' for emotional immediacy" in prompt
    assert "let at least one candidate keep the marked divine-name distinction" in prompt
    assert response["available"] is True
    assert response["chunks"][0]["candidates"][0]["text"] == "God, do not break me in your anger"
    assert seen["metadata"]["style_profile"] == "doubter_lament"


def test_composer_suggestions_drop_seed_english_duplicates_when_other_options_exist(monkeypatch) -> None:
    class FakeComposerAdapter:
        name = "fake-composer"

        def __init__(self, profile: dict[str, object]) -> None:
            self.profile = profile

        def generate_json(self, generation_request) -> GenerationResponse:
            return GenerationResponse(
                payload={
                    "unit_id": generation_request.metadata["unit_id"],
                    "stage": generation_request.metadata["stage"],
                    "chunks": [
                        {
                            "chunk_id": "chunk-1",
                            "candidates": [
                                {
                                    "text": "How blessed is the man",
                                    "rationale": "seed duplicate",
                                    "alignment_hints": [],
                                    "drift_flags": [],
                                    "metrics": {},
                                },
                                {
                                    "text": "How deeply blessed is the one",
                                    "rationale": "fresh delivery",
                                    "alignment_hints": [],
                                    "drift_flags": [],
                                    "metrics": {},
                                },
                            ],
                        }
                    ],
                },
                raw_text="{}",
                runtime_metadata={},
            )

    monkeypatch.setattr(
        "app.services.composer_suggestion_service.build_adapter",
        lambda profile: FakeComposerAdapter(profile),
    )

    response = composer_suggestion_service.suggest_for_unit(
        unit_id="ps001.v001.a",
        stage="concept",
        chunks=[
            {
                "chunk_id": "chunk-1",
                "start": 0,
                "end": 2,
                "text": "How blessed is the man",
                "source_text": "אַשְׁרֵי הָאִישׁ אֲשֶׁר",
                "confidence": 0.82,
                "confidence_reasons": ["fixture seed"],
            }
        ],
        candidate_count=2,
        style_profile="dynamic_equivalent",
    )

    assert response["available"] is True
    assert [candidate["text"] for candidate in response["chunks"][0]["candidates"]] == ["How deeply blessed is the one"]
