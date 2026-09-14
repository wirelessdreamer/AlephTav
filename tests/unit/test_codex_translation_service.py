from __future__ import annotations

import json
from collections import deque
from typing import Any

import pytest

from app.core.errors import ValidationError
from app.llm.strict_schema import strict_output_schema
from app.services import codex_app_server_service as codex
from app.services import codex_translation_service as translation
from app.services import generation_service, registry_service

UNIT_ID = "ps001.v001.a"


@pytest.fixture(autouse=True)
def _clean_session_store():
    """Sessions persist by design, so isolate each test from the last one."""
    translation._store_path().unlink(missing_ok=True)
    yield
    translation._store_path().unlink(missing_ok=True)


class ScriptedTransport:
    """Replays a queue of app-server replies keyed by request method."""

    def __init__(self, agent_text: str) -> None:
        self.agent_text = agent_text
        self.sent: list[dict[str, Any]] = []
        self._inbox: deque[str] = deque()

    def send(self, message: dict[str, Any]) -> None:
        self.sent.append(message)
        method = message.get("method")
        if method == "thread/start":
            self._push(
                {"jsonrpc": "2.0", "id": message["id"], "result": {"thread": {"id": "th-1"}}}
            )
        elif method == "turn/start":
            self._push(
                {"jsonrpc": "2.0", "id": message["id"], "result": {"turn": {"id": "turn-1"}}}
            )
            self._push(
                {
                    "jsonrpc": "2.0",
                    "method": "item/completed",
                    "params": {"item": {"type": "agentMessage", "text": self.agent_text}},
                }
            )
            self._push(
                {"jsonrpc": "2.0", "method": "turn/completed", "params": {"turn": {"id": "turn-1"}}}
            )
        elif "id" in message:
            self._push({"jsonrpc": "2.0", "id": message["id"], "result": {}})

    def _push(self, obj: dict[str, Any]) -> None:
        self._inbox.append(json.dumps(obj))

    def readline(self) -> str:
        return self._inbox.popleft() + "\n" if self._inbox else ""

    def close(self) -> None:
        pass

    def params_for(self, method: str) -> dict[str, Any]:
        return next(m["params"] for m in self.sent if m.get("method") == method)


def _valid_payload() -> dict[str, Any]:
    return {
        "unit_id": UNIT_ID,
        "layer": "lyric",
        "candidates": [
            {
                "text": "Blessed is the one",
                "rationale": "tracks the Hebrew",
                "alignment_hints": [],
                "drift_flags": [],
                "metrics": {},
                "variation_basis": ["hebrew_source"],
                "preserved_source_images": [],
                "differentiator": "literal-leaning",
                "grounding_confidence": 0.9,
                "translation_basis": {
                    "basis_type": "hebrew_to_english",
                    "source_ids": ["oshb"],
                    "source_language": "he",
                    "source_version": "1.0",
                    "basis_note": "Hebrew source",
                },
                "delivery_profile": "spoken",
                "source_anchor": {
                    "anchor_text": "אשרי",
                    "source_language": "he",
                    "source_text": "אשרי האיש",
                    "basis_note": "Opening colon",
                },
                "accuracy_note": "Close to the Hebrew clause order.",
                "creative_liberties_note": "Contracted for singability.",
                "literalness": "very_close",
            }
        ],
    }


def _client(agent_text: str) -> codex.CodexAppServerClient:
    return codex.CodexAppServerClient(transport=ScriptedTransport(agent_text))


def test_create_session_maps_to_a_thread_and_stores_no_credentials() -> None:
    client = _client("{}")
    session = translation.create_session(client, psalm_id="ps001", unit_id=UNIT_ID, model="gpt-5")

    assert session["thread_id"] == "th-1"
    assert session["provider"] == codex.PROVIDER_NAME
    assert session["prompt_template_version"] == translation.PROMPT_TEMPLATE_VERSION

    stored = json.dumps(translation.get_session(session["session_id"]))
    for forbidden in ("accessToken", "refreshToken", "authUrl", "loginUrl"):
        assert forbidden not in stored

    assert [s["session_id"] for s in translation.list_sessions("ps001")] == [session["session_id"]]


def test_prompt_carries_the_required_evidence_and_separates_mt_numbering() -> None:
    prompt = translation.build_translation_prompt(
        UNIT_ID, "lyric", candidate_count=3, style_profile="antiphonal", meter_target="6/8"
    )
    unit = registry_service.load_unit(UNIT_ID)

    assert unit["source_hebrew"] in prompt
    assert "MT reference:" in prompt and "Display reference:" in prompt
    assert "Required output layer: lyric" in prompt
    assert "Candidate count: 3" in prompt
    assert "antiphonal" in prompt and "6/8" in prompt
    assert "Do not alter the Hebrew source." in prompt
    # Token evidence is included so alignment can be anchored.
    assert unit["tokens"][0]["token_id"] in prompt
    # Codex runs outside the repository, so the layer's own rules travel in the prompt.
    assert "## Layer instructions (lyric)" in prompt
    assert "# Pass 05 Lyric" in prompt


def test_valid_run_completes_and_records_provenance() -> None:
    client = _client(json.dumps(_valid_payload()))
    session = translation.create_session(client, psalm_id="ps001", unit_id=UNIT_ID, model="gpt-5")
    run = translation.run_translation_turn(client, session["session_id"], UNIT_ID, "lyric")

    assert run["status"] == translation.RUN_COMPLETED
    assert run["turn_id"] == "turn-1"
    assert run["payload"]["candidates"][0]["accuracy_note"]
    # The contract is handed to Codex in its strict structured-output form.
    assert client.transport.params_for("turn/start")["outputSchema"] == strict_output_schema(
        generation_service.OUTPUT_VALIDATOR.schema
    )


def test_output_failing_the_contract_is_preserved_as_an_auditable_error() -> None:
    broken = {"unit_id": UNIT_ID, "layer": "lyric", "candidates": [{"text": "missing fields"}]}
    client = _client(json.dumps(broken))
    session = translation.create_session(client, psalm_id="ps001", unit_id=UNIT_ID)
    run = translation.run_translation_turn(client, session["session_id"], UNIT_ID, "lyric")

    assert run["status"] == translation.RUN_INVALID_OUTPUT
    assert run["validation"], "validation errors must be preserved for the retry action"
    assert run["payload"] is None

    # No rendering may be created from an invalid run.
    with pytest.raises(ValidationError):
        translation.save_run_candidates(run["run_id"])


def test_non_json_output_is_rejected_without_creating_a_rendering() -> None:
    client = _client("I cannot do that")
    session = translation.create_session(client, psalm_id="ps001", unit_id=UNIT_ID)
    run = translation.run_translation_turn(client, session["session_id"], UNIT_ID, "lyric")

    assert run["status"] == translation.RUN_INVALID_OUTPUT
    with pytest.raises(ValidationError):
        translation.save_run_candidates(run["run_id"])


def test_saved_candidates_are_always_proposed_and_carry_codex_provenance() -> None:
    client = _client(json.dumps(_valid_payload()))
    session = translation.create_session(client, psalm_id="ps001", unit_id=UNIT_ID, model="gpt-5")
    run = translation.run_translation_turn(client, session["session_id"], UNIT_ID, "lyric")

    created = translation.save_run_candidates(run["run_id"])

    assert len(created) == 1
    rendering = created[0]
    # FR-6: never canonical, whatever the model returned.
    assert rendering["status"] == "proposed"
    assert rendering["provenance"]["provider"] == codex.PROVIDER_NAME
    assert rendering["provenance"]["thread_id"] == "th-1"
    assert rendering["provenance"]["run_id"] == run["run_id"]

    unit = registry_service.load_unit(UNIT_ID)
    stored = next(r for r in unit["renderings"] if r["rendering_id"] == rendering["rendering_id"])
    assert stored["status"] == "proposed"
    assert stored["rendering_id"] not in unit["canonical_rendering_ids"]
    # The mutation went through the rendering service, so it is audited.
    assert any(record["entity_id"] == rendering["rendering_id"] for record in unit["audit_records"])


def test_codex_cannot_promote_its_own_candidate_to_canonical() -> None:
    payload = _valid_payload()
    payload["candidates"][0]["text"] = "Sneaky canonical attempt"
    client = _client(json.dumps(payload))
    session = translation.create_session(client, psalm_id="ps001", unit_id=UNIT_ID)
    run = translation.run_translation_turn(client, session["session_id"], UNIT_ID, "lyric")

    created = translation.save_run_candidates(run["run_id"])
    assert created[0]["status"] == "proposed"


def test_cancelling_a_running_turn_interrupts_it() -> None:
    client = _client(json.dumps(_valid_payload()))
    session = translation.create_session(client, psalm_id="ps001", unit_id=UNIT_ID)
    run = translation.run_translation_turn(client, session["session_id"], UNIT_ID, "lyric")
    run["status"] = translation.RUN_RUNNING
    translation._save_run(run)

    cancelled = translation.cancel_run(client, run["run_id"])

    assert cancelled["status"] == translation.RUN_CANCELLED
    assert client.transport.params_for("turn/interrupt") == {
        "threadId": "th-1",
        "turnId": "turn-1",
    }


def test_resume_session_reopens_the_thread() -> None:
    client = _client("{}")
    session = translation.create_session(client, psalm_id="ps001", unit_id=UNIT_ID)
    resumed = translation.resume_session(client, session["session_id"])

    assert resumed["thread_id"] == "th-1"
    assert client.transport.params_for("thread/resume") == {"threadId": "th-1"}
