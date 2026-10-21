"""The translator's briefing: background and the questions the psalm leaves open."""

from __future__ import annotations

from typing import Any

import pytest

from app.services import codex_app_server_service as codex
from app.services import codex_briefing_service as briefing
from app.services import codex_translation_service as translation
from app.services import registry_service
from tests.unit.test_verse_notes import ScriptedTransport

PSALM_ID = "ps001"


@pytest.fixture(autouse=True)
def _restore():
    translation._store_path().unlink(missing_ok=True)
    briefing._briefings_path().unlink(missing_ok=True)
    meta = registry_service.load_psalm_meta(PSALM_ID)
    units = [registry_service.load_unit(unit_id) for unit_id in meta["unit_ids"]]
    yield
    registry_service.save_psalm_meta(PSALM_ID, meta)
    for unit in units:
        registry_service.save_unit(unit)
    translation._store_path().unlink(missing_ok=True)
    briefing._briefings_path().unlink(missing_ok=True)


def _reply(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "background": {
            "authorship": "No heading; tradition places it first as a preface.",
            "setting": "Often dated after the exile; the text names no occasion.",
            "form": "A wisdom psalm built on the contrast of two ways.",
            "themes": "The two ways, from blessing to the way that perishes.",
            "reception": "Read with Psalm 2 as one opening in some Jewish tradition.",
        },
        "questions": [
            {
                "topic": "The divine name",
                "verses": [2, 6],
                "question": "How should YHWH be rendered?",
                "background": "The tetragrammaton, read aloud as Adonai.",
                "options": [
                    {
                        "choice": 'Render YHWH as "the LORD".',
                        "held_by": "KJV, ESV, NRSV, JPS",
                        "effect": "Familiar in worship; hides the name.",
                    },
                    {
                        "choice": 'Render YHWH as "Yahweh".',
                        "held_by": "World English Bible, many scholars",
                        "effect": "Keeps the name; strange to some readers.",
                    },
                ],
            }
        ],
    }
    payload.update(overrides)
    return payload


def _session(payloads: list[Any]) -> tuple[codex.CodexAppServerClient, str]:
    client = codex.CodexAppServerClient(transport=ScriptedTransport(payloads))
    return client, translation.create_session(client, psalm_id=PSALM_ID)["session_id"]


def test_the_prompt_carries_the_psalm_and_asks_for_open_questions_not_answers() -> None:
    prompt = briefing.build_briefing_prompt(PSALM_ID)

    for unit in registry_service.load_psalm(PSALM_ID)["units"]:
        assert unit["source_hebrew"] in prompt
    assert "authorship:" in prompt and "reception:" in prompt
    assert "Do not treat a traditional ascription as a fact" in prompt
    assert "do not rank them or say which is right" in prompt
    assert "## The translator's guidance so far\n" in prompt
    assert "(none yet)" in prompt


def test_questions_the_guidance_settles_are_not_asked() -> None:
    translation.set_guidance(PSALM_ID, 'Render YHWH as "Yahweh".')

    prompt = briefing.build_briefing_prompt(PSALM_ID)

    assert "Do not ask what it already decides." in prompt
    assert 'Render YHWH as "Yahweh".' in prompt


def test_a_briefing_is_cached_with_the_guidance_it_was_made_under() -> None:
    translation.set_guidance(PSALM_ID, "Target 6/8 meter.")
    client, session_id = _session([_reply()])

    result = briefing.prepare_briefing(client, session_id, PSALM_ID)

    assert result["status"] == translation.RUN_COMPLETED
    cached = briefing.cached_briefing(PSALM_ID)
    assert cached == result["briefing"]
    assert cached["guidance"] == "Target 6/8 meter."
    assert cached["questions"][0]["options"][1]["choice"] == 'Render YHWH as "Yahweh".'
    assert cached["background"]["form"].startswith("A wisdom psalm")
    # Another translation of the psalm has its own briefing, and has none yet.
    assert briefing.cached_briefing(PSALM_ID, "tr.ps001.0001") is None


def test_a_question_with_one_option_fails_and_the_earlier_briefing_stays() -> None:
    one_sided = _reply()
    one_sided["questions"][0]["options"] = one_sided["questions"][0]["options"][:1]
    client, session_id = _session([_reply(), one_sided])
    first = briefing.prepare_briefing(client, session_id, PSALM_ID)

    second = briefing.prepare_briefing(client, session_id, PSALM_ID)

    assert second["status"] == translation.RUN_INVALID_OUTPUT
    assert second["briefing"] == first["briefing"]
    assert briefing.cached_briefing(PSALM_ID) == first["briefing"]


def test_briefings_and_annotated_guidance_survive_cache_deletion() -> None:
    from app.services import translation_context_service as context

    client, session_id = _session([_reply(), _reply()])
    first = briefing.prepare_briefing(client, session_id, PSALM_ID)["briefing"]
    translation.set_guidance(
        PSALM_ID,
        "Use Yahweh.",
        briefing_annotations=[
            {
                "briefing_run_id": first["run_id"],
                "question_index": 0,
                "answer": "Use Yahweh.",
                "notes": "Keep the personal name audible.",
            }
        ],
    )
    second = briefing.prepare_briefing(client, session_id, PSALM_ID)["briefing"]
    briefing._briefings_path().unlink()
    translation._store_path().unlink()

    events = context.history(PSALM_ID)
    assert [event["kind"] for event in events] == ["briefing", "guidance", "briefing"]
    assert events[0]["briefing"] == first
    assert events[1]["previous_guidance"] == ""
    assert events[1]["annotations"][0]["question"] == first["questions"][0]
    assert events[1]["annotations"][0]["notes"] == "Keep the personal name audible."
    assert briefing.cached_briefing(PSALM_ID) == second
    assert context.history(PSALM_ID, "tr.ps001.9999") == []


def test_annotation_cannot_reference_another_translations_briefing() -> None:
    from app.core.errors import ValidationError

    client, session_id = _session([_reply()])
    prepared = briefing.prepare_briefing(client, session_id, PSALM_ID)["briefing"]
    with pytest.raises(ValidationError, match="does not belong"):
        translation.set_guidance(
            PSALM_ID,
            "Changed",
            briefing_annotations=[
                {
                    "briefing_run_id": prepared["run_id"] + "other",
                    "question_index": 0,
                    "answer": "Test",
                    "notes": "",
                }
            ],
        )
    assert translation.get_guidance(PSALM_ID) == ""


def test_notes_can_be_saved_without_changing_guidance() -> None:
    from app.services import translation_context_service as context

    client, session_id = _session([_reply()])
    prepared = briefing.prepare_briefing(client, session_id, PSALM_ID)["briefing"]
    translation.set_guidance(
        PSALM_ID,
        "",
        briefing_annotations=[
            {
                "briefing_run_id": prepared["run_id"],
                "question_index": 0,
                "answer": "",
                "notes": "Still deciding between the two readings.",
            }
        ],
    )
    assert context.history(PSALM_ID)[-1]["annotations"][0]["notes"].startswith("Still deciding")
    assert translation.get_guidance(PSALM_ID) == ""


def test_existing_cached_briefing_migration_is_idempotent() -> None:
    import json

    from app.services import translation_context_service as context

    legacy = {
        "psalm_id": PSALM_ID,
        "translation_id": None,
        "run_id": "legacy-run",
        "guidance": "Old guidance",
        "created_at": "2026-01-01T00:00:00Z",
        **_reply(),
    }
    briefing._briefings_path().write_text(json.dumps({PSALM_ID: legacy}), encoding="utf-8")
    assert len(context.preserve_cached_briefings()) == 1
    assert context.preserve_cached_briefings() == []
    briefing._briefings_path().unlink()
    assert briefing.cached_briefing(PSALM_ID) == legacy


def test_decisions_save_independently_restore_and_keep_only_current_answers_in_generation() -> None:
    from app.services import translation_context_service as context

    client, session_id = _session([_reply()])
    prepared = briefing.prepare_briefing(client, session_id, PSALM_ID)["briefing"]
    note = {
        "briefing_run_id": prepared["run_id"],
        "question_index": 0,
        "answer": "Use Yahweh.",
        "notes": "Personal name audible.",
    }
    first = context.save_decision(PSALM_ID, None, note)
    assert translation.get_guidance(PSALM_ID) == ""
    assert first["question"] == prepared["questions"][0]
    count = len(context.history(PSALM_ID))
    context.save_decision(PSALM_ID, None, note)
    assert len(context.history(PSALM_ID)) == count  # Retries are idempotent.
    changed = context.save_decision(PSALM_ID, None, {**note, "answer": "Use LORD."})
    # Applying an older snapshot to guidance must not undo the newer form answer.
    translation.set_guidance(PSALM_ID, "Use Yahweh.", briefing_annotations=[note])
    briefing._briefings_path().unlink()
    translation._store_path().unlink()
    assert context.capture(PSALM_ID, None)["annotations"] == [changed]
    assert context.history(PSALM_ID)[1]["annotations"] == [first]
    context.save_decision(PSALM_ID, None, {**note, "answer": "", "notes": ""})
    assert context.capture(PSALM_ID, None)["annotations"] == []
    assert context.history(PSALM_ID)[-1]["kind"] == "briefing_decision"


def test_decision_api_preserves_translation_scope_and_rejects_invalid_questions() -> None:
    from fastapi.testclient import TestClient

    from app.api.main import app
    from app.services import translation_context_service as context

    transport, session_id = _session([_reply()])
    prepared = briefing.prepare_briefing(transport, session_id, PSALM_ID)["briefing"]
    client = TestClient(app)
    note = {
        "briefing_run_id": prepared["run_id"],
        "question_index": 0,
        "answer": "Use Yahweh.",
        "notes": "Keep the name.",
    }
    endpoint = f"/psalms/{PSALM_ID}/briefing-decisions"
    result = client.put(endpoint, json={"annotation": note})
    assert result.status_code == 200
    assert result.json()["notes"] == "Keep the name."
    assert context.capture(PSALM_ID, None)["annotations"] == [result.json()]
    before = len(context.history(PSALM_ID))
    for invalid in [None, {**note, "question_index": 99}, {**note, "answer": []}]:
        assert client.put(endpoint, json={"annotation": invalid}).status_code == 400
    assert (
        client.put(
            endpoint, json={"translation_id": "tr.ps001.9999", "annotation": note}
        ).status_code
        == 400
    )
    assert len(context.history(PSALM_ID)) == before


def test_saved_decisions_follow_the_translation_into_rendering_provenance() -> None:
    from app.services import translation_context_service as context
    from tests.unit.test_translation_guidance_and_rows import _client

    client, session_id = _session([_reply()])
    prepared = briefing.prepare_briefing(client, session_id, PSALM_ID)["briefing"]
    note = context.save_decision(
        PSALM_ID,
        None,
        {
            "briefing_run_id": prepared["run_id"],
            "question_index": 0,
            "answer": "Use Yahweh.",
            "notes": "Keep this decision with the generated text.",
        },
    )
    generator = _client()
    session = translation.create_session(generator, psalm_id=PSALM_ID)
    run = translation.run_translation_turn(
        generator, session["session_id"], "ps001.v001.a", "lyric", candidate_count=1
    )
    prompt = generator.transport.prompts()[0]
    assert "Saved briefing decisions (apply automatically)" in prompt
    assert "Decision: Use Yahweh." in prompt
    assert "Translator note: Keep this decision with the generated text." in prompt
    assert prompt.index("Decision: Use Yahweh.") < prompt.index("## Hebrew source meaning")
    assert translation.get_guidance(PSALM_ID) == ""  # No separate guidance save.
    rendering = translation.save_run_candidates(run["run_id"])[0]
    saved = rendering["provenance"]["translation_context"]
    assert saved["annotations"] == [note]
    assert saved["briefing"] == prepared
    assert context.history(PSALM_ID)[-1]["audit_id"] in saved["history_ids"]


def test_saved_answers_reach_passages_rebuilds_choices_arrangements_and_local_inputs(
    monkeypatch,
) -> None:
    from app.services import codex_arrangement_service, generation_service
    from app.services import translation_context_service as context

    client, session_id = _session([_reply()])
    prepared = briefing.prepare_briefing(client, session_id, PSALM_ID)["briefing"]
    note = {
        "briefing_run_id": prepared["run_id"],
        "question_index": 0,
        "answer": "Use Yahweh.",
        "notes": "Do not replace the personal name.",
    }
    context.save_decision(PSALM_ID, None, note)
    monkeypatch.setattr(translation, "_readings_elsewhere", lambda *args: [])
    unit = registry_service.load_unit("ps001.v001.a")
    for prompt in [
        translation.build_passage_prompt(PSALM_ID, [unit["unit_id"]], "lyric"),
        translation.build_rebuild_prompt(unit["unit_id"], "lyric", []),
        translation.build_suggestion_prompt(
            unit["unit_id"], [unit["tokens"][0]["token_id"]], "lyric"
        ),
        codex_arrangement_service.build_arrangement_prompt(PSALM_ID, "lyric"),
        briefing.build_briefing_prompt(PSALM_ID),
        generation_service._locked_inputs(unit, "gloss")["briefing_decisions"],
    ]:
        assert "Decision: Use Yahweh." in prompt
        assert "Do not replace the personal name." in prompt
    assert context.briefing_instructions(PSALM_ID, "tr.ps001.other") == ""
    context.save_decision(PSALM_ID, None, {**note, "answer": "", "notes": ""})
    assert "Use Yahweh." not in translation.build_passage_prompt(
        PSALM_ID, [unit["unit_id"]], "lyric"
    )


def test_inferred_suggestions_do_not_direct_translation_until_adopted() -> None:
    from app.services import translation_context_service as context

    client, session_id = _session([_reply()])
    prepared = briefing.prepare_briefing(client, session_id, PSALM_ID)["briefing"]
    context.append(
        PSALM_ID,
        None,
        kind="briefing_inference",
        summary="Inference, not original answer",
        snapshot={
            "guidance": "",
            "inferences": {
                "briefing_run_id": prepared["run_id"],
                "items": [{"answer": "Inferred Yahweh preference"}],
            },
        },
    )
    assert "Inferred Yahweh preference" not in translation.generation_guidance(PSALM_ID)
    assert context.capture(PSALM_ID, None)["annotations"] == []


def test_saved_briefing_loads_without_waiting_for_source_dictionary(monkeypatch) -> None:
    from app.api.routes import codex as routes
    from app.services import briefing_source_service
    from app.services import translation_context_service as context

    client, session_id = _session([_reply()])
    prepared = briefing.prepare_briefing(client, session_id, PSALM_ID)["briefing"]
    context.save_decision(
        PSALM_ID,
        None,
        {
            "briefing_run_id": prepared["run_id"],
            "question_index": 0,
            "answer": "Use Yahweh.",
            "notes": "Keep the name.",
        },
    )

    def slow_sources(*args):
        raise AssertionError("Restoring saved answers must not load the Greek dictionary")

    monkeypatch.setattr(briefing_source_service, "greek_evidence", slow_sources)
    view = routes.get_briefing(PSALM_ID, translation_id=None, include_sources=False)
    assert view["briefing"] == prepared
    assert context.current_annotations(view["history"])[0]["answer"] == "Use Yahweh."
