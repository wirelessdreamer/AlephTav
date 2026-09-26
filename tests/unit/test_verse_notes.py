"""Notes on a verse, rebuilding it with them, and auditing the rebuild blind.

A rebuild is held: its renderings are saved as proposed but kept out of the
table and the auditor's view until the reviewer accepts it.
"""

from __future__ import annotations

import json
from collections import deque
from typing import Any

import pytest

from app.core.errors import NotFoundError, ValidationError
from app.services import codex_analysis_service as analysis
from app.services import codex_app_server_service as codex
from app.services import codex_translation_service as translation
from app.services import comparison_assessment_service as comparisons
from app.services import registry_service, verse_notes_service

UNIT_ID = "ps001.v001.a"
PSALM_ID = "ps001"
NOTE_TEXT = "Make it clear the teaching is Yahweh's, not the man's."


@pytest.fixture(autouse=True)
def _restore_unit():
    translation._store_path().unlink(missing_ok=True)
    translation._suggestions_path().unlink(missing_ok=True)
    unit = registry_service.load_unit(UNIT_ID)
    meta = registry_service.load_psalm_meta(PSALM_ID)
    yield
    registry_service.save_unit(unit)
    registry_service.save_psalm_meta(PSALM_ID, meta)
    translation._store_path().unlink(missing_ok=True)
    translation._suggestions_path().unlink(missing_ok=True)


def _candidate(text: str) -> dict[str, Any]:
    return {
        "text": text,
        "rationale": "follows the reviewer's note",
        "alignment_hints": [],
        "drift_flags": [],
        "metrics": {},
        "variation_basis": ["hebrew_source"],
        "preserved_source_images": [],
        "differentiator": "d",
        "grounding_confidence": 0.9,
        "translation_basis": {
            "basis_type": "hebrew_to_english",
            "source_ids": ["oshb"],
            "source_language": "he",
            "source_version": "1.0",
            "basis_note": "Hebrew source",
        },
        "delivery_profile": "sung",
        "source_anchor": {
            "anchor_text": "a",
            "source_language": "he",
            "source_text": "b",
            "basis_note": "c",
        },
        "accuracy_note": "Tracks the Hebrew.",
        "creative_liberties_note": "None.",
        "literalness": "close",
    }


def _rebuild_reply(layer: str, text: str, responses: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "psalm_id": PSALM_ID,
        "layer": layer,
        "units": [{"unit_id": UNIT_ID, "layer": layer, "candidates": [_candidate(text)]}],
        "note_responses": responses,
    }


def _verse_audit(**overrides: Any) -> dict[str, Any]:
    payload = {
        "unit_id": UNIT_ID,
        "accuracy_rating": "very_close",
        "accuracy_note": "The rebuilt lyric keeps every clause.",
        "creative_liberties_note": "Names Yahweh where the Hebrew has a suffix.",
        "literal_backbone": ["Blessed is the one"],
        "word_notes": [],
        "non_source_material": [],
    }
    payload.update(overrides)
    return payload


class ScriptedTransport:
    """Answers each turn with the next queued payload."""

    def __init__(self, payloads: list[dict[str, Any]]) -> None:
        self.payloads = list(payloads)
        self.sent: list[dict[str, Any]] = []
        self._inbox: deque[str] = deque()
        self.turn = 0

    def send(self, message: dict[str, Any]) -> None:
        self.sent.append(message)
        method = message.get("method")
        if method == "thread/start":
            self._push({"jsonrpc": "2.0", "id": message["id"], "result": {"thread": {"id": "th"}}})
        elif method == "turn/start":
            self.turn += 1
            turn_id = f"turn-{self.turn}"
            body = self.payloads.pop(0) if self.payloads else {}
            text = body if isinstance(body, str) else json.dumps(body)
            self._push({"jsonrpc": "2.0", "id": message["id"], "result": {"turn": {"id": turn_id}}})
            self._push(
                {
                    "jsonrpc": "2.0",
                    "method": "item/completed",
                    "params": {"item": {"type": "agentMessage", "text": text}},
                }
            )
            self._push(
                {"jsonrpc": "2.0", "method": "turn/completed", "params": {"turn": {"id": turn_id}}}
            )
        elif "id" in message:
            self._push({"jsonrpc": "2.0", "id": message["id"], "result": {}})

    def _push(self, obj: dict[str, Any]) -> None:
        self._inbox.append(json.dumps(obj))

    def readline(self) -> str:
        return self._inbox.popleft() + "\n" if self._inbox else ""

    def close(self) -> None:
        pass

    def prompts(self) -> list[str]:
        return [
            m["params"]["input"][0]["text"] for m in self.sent if m.get("method") == "turn/start"
        ]


def _session(payloads: list[Any]) -> tuple[codex.CodexAppServerClient, str]:
    client = codex.CodexAppServerClient(transport=ScriptedTransport(payloads))
    return client, translation.create_session(client, psalm_id=PSALM_ID)["session_id"]


def _lyric_text() -> str:
    unit = registry_service.load_unit(UNIT_ID)
    return comparisons.select_rendering(unit, "lyric")["text"]


def _rebuild(text: str = "rebuilt lyric naming Yahweh") -> tuple[Any, str, dict[str, Any]]:
    note = verse_notes_service.add_note(UNIT_ID, NOTE_TEXT, applies_to="english")
    client, session_id = _session(
        [_rebuild_reply("lyric", text, [{"note_id": note["note_id"], "response": "Named Yahweh."}])]
    )
    result = translation.rebuild_verse(client, session_id, UNIT_ID, layers=["english"])
    return client, session_id, result


# -- Notes -------------------------------------------------------------------


def test_notes_are_added_edited_and_removed_with_an_audit_record_each() -> None:
    audits = len(registry_service.load_unit(UNIT_ID)["audit_records"])

    note = verse_notes_service.add_note(UNIT_ID, "  Keep the “and”.  ", applies_to="both")
    assert note["text"] == "Keep the “and”."
    assert note["status"] == "open"
    verse_notes_service.update_note(UNIT_ID, note["note_id"], text="Keep the Hebrew's “and”.")
    verse_notes_service.remove_note(UNIT_ID, note["note_id"])

    unit = registry_service.load_unit(UNIT_ID)
    assert unit.get("verse_notes") == []
    summaries = [r["summary"] for r in unit["audit_records"][audits:]]
    assert summaries == ["Add verse note", "Update verse note", "Remove verse note"]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"text": "   "},
        {"text": "x", "applies_to": "gloss"},
        {"text": "x", "kind": "question"},
        {"text": "x", "token_ids": ["ps001.v099.t001"]},
    ],
)
def test_malformed_notes_are_rejected(kwargs: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        verse_notes_service.add_note(UNIT_ID, **kwargs)


def test_a_comment_or_an_addressed_note_is_not_sent_to_the_translator() -> None:
    comment = verse_notes_service.add_note(UNIT_ID, "Lovely line.", kind="comment")
    done = verse_notes_service.add_note(UNIT_ID, "Old ask.")
    verse_notes_service.update_note(UNIT_ID, done["note_id"], status="addressed")
    live = verse_notes_service.add_note(UNIT_ID, NOTE_TEXT)

    sent = verse_notes_service.open_instructions(registry_service.load_unit(UNIT_ID), "english")

    assert [n["note_id"] for n in sent] == [live["note_id"]]
    assert comment["note_id"] not in {n["note_id"] for n in sent}


# -- Rebuild -----------------------------------------------------------------


def test_a_rebuild_is_held_until_the_reviewer_decides() -> None:
    before = _lyric_text()
    client, _, result = _rebuild()

    assert result["status"] == translation.RUN_COMPLETED
    rebuild = result["rebuild"]
    assert rebuild["status"] == "pending"
    assert rebuild["note_responses"][0]["response"] == "Named Yahweh."

    prompt = client.transport.prompts()[0]
    assert NOTE_TEXT in prompt
    assert f"## The current lyric for {UNIT_ID}" in prompt and before in prompt

    unit = registry_service.load_unit(UNIT_ID)
    held = unit["renderings"][-1]
    assert held["rendering_id"] == rebuild["rendering_ids"]["lyric"]
    assert held["status"] == "proposed"
    # The table, and anything else choosing the displayed text, still sees the old lyric.
    assert _lyric_text() == before
    view = verse_notes_service.rebuild_view(unit, verse_notes_service.pending_rebuild(unit))
    assert view["texts"]["lyric"]["previous"] == before
    assert view["texts"]["lyric"]["rebuilt"] == "rebuilt lyric naming Yahweh"


def test_a_second_rebuild_waits_for_the_first_to_be_decided() -> None:
    _rebuild()
    client, session_id = _session([])
    with pytest.raises(ValidationError):
        translation.rebuild_verse(client, session_id, UNIT_ID, layers=["english"])


def test_a_failed_rebuild_saves_nothing() -> None:
    verse_notes_service.add_note(UNIT_ID, NOTE_TEXT)
    renderings = len(registry_service.load_unit(UNIT_ID)["renderings"])
    client, session_id = _session(["not json"])

    result = translation.rebuild_verse(client, session_id, UNIT_ID, layers=["english"])

    assert result["status"] == translation.RUN_INVALID_OUTPUT
    unit = registry_service.load_unit(UNIT_ID)
    assert len(unit["renderings"]) == renderings
    assert verse_notes_service.pending_rebuild(unit) is None


# -- Blind audit, accept, discard --------------------------------------------


def test_the_rebuild_is_audited_blind_to_the_notes() -> None:
    client, session_id, _ = _rebuild()
    assessments = registry_service.load_unit(UNIT_ID).get("comparison_assessments", [])
    client.transport.payloads.append(_verse_audit())

    result = analysis.analyze_rebuild(client, session_id, UNIT_ID)

    prompt = client.transport.prompts()[-1]
    assert "rebuilt lyric naming Yahweh" in prompt
    assert NOTE_TEXT not in prompt
    assert result["analysis"]["accuracy_note"] == "The rebuilt lyric keeps every clause."
    # Held on the rebuild; the verse's own assessment is untouched until accept.
    unit = registry_service.load_unit(UNIT_ID)
    assert unit.get("comparison_assessments", []) == assessments
    assert verse_notes_service.pending_rebuild(unit)["analysis"]["run_id"] == result["run_id"]


def _make_lyric_unreviewed() -> None:
    """Test setup: most real verses carry only proposed Codex text."""
    unit = registry_service.load_unit(UNIT_ID)
    for rendering in unit["renderings"]:
        if rendering["layer"] == "lyric":
            rendering["status"] = "proposed"
    registry_service.save_unit(unit)


def test_accepting_shows_the_rebuild_adopts_its_audit_and_closes_notes() -> None:
    _make_lyric_unreviewed()
    client, session_id, result = _rebuild()
    assert result["rebuild"]["rendering_ids"]["lyric"]
    unit = registry_service.load_unit(UNIT_ID)
    view = verse_notes_service.rebuild_view(unit, verse_notes_service.pending_rebuild(unit))
    assert view["texts"]["lyric"]["replaces_current"] is True
    client.transport.payloads.append(_verse_audit())
    analysis.analyze_rebuild(client, session_id, UNIT_ID)
    note_id = result["rebuild"]["note_ids"][0]

    verse_notes_service.accept_rebuild(
        UNIT_ID, result["rebuild"]["rebuild_id"], addressed_note_ids=[note_id]
    )

    assert _lyric_text() == "rebuilt lyric naming Yahweh"
    table = comparisons.build_comparison_table(PSALM_ID)
    row = next(row for row in table["rows"] if UNIT_ID in row["unit_ids"])
    assert row["accuracy_note"] == "The rebuilt lyric keeps every clause."
    assert row["stale"] is False
    assert row["pending_rebuild"] is None
    note = next(n for n in row["verse_notes"] if n["note_id"] == note_id)
    assert note["status"] == "addressed"
    assert note["addressed_in"] == result["rebuild"]["rebuild_id"]


def test_a_rebuild_never_displaces_reviewed_text() -> None:
    # The fixture lyric is an accepted alternate: only review can replace it.
    before = _lyric_text()
    client, session_id, result = _rebuild()
    unit = registry_service.load_unit(UNIT_ID)
    view = verse_notes_service.rebuild_view(unit, verse_notes_service.pending_rebuild(unit))
    assert view["texts"]["lyric"]["replaces_current"] is False
    client.transport.payloads.append(_verse_audit())
    analysis.analyze_rebuild(client, session_id, UNIT_ID)
    assessments = registry_service.load_unit(UNIT_ID).get("comparison_assessments", [])

    verse_notes_service.accept_rebuild(UNIT_ID, result["rebuild"]["rebuild_id"])

    unit = registry_service.load_unit(UNIT_ID)
    assert _lyric_text() == before
    kept = next(
        r
        for r in unit["renderings"]
        if r["rendering_id"] == result["rebuild"]["rendering_ids"]["lyric"]
    )
    assert kept["status"] == "proposed"
    # The held audit was of text that is not shown, so it is not adopted.
    assert unit.get("comparison_assessments", []) == assessments


def test_discarding_keeps_the_current_text_and_the_notes_open() -> None:
    before = _lyric_text()
    _, _, result = _rebuild()
    rebuilt_id = result["rebuild"]["rendering_ids"]["lyric"]

    verse_notes_service.discard_rebuild(UNIT_ID, result["rebuild"]["rebuild_id"])

    unit = registry_service.load_unit(UNIT_ID)
    assert _lyric_text() == before
    assert next(r for r in unit["renderings"] if r["rendering_id"] == rebuilt_id)["status"] == (
        "rejected"
    )
    assert all(n["status"] == "open" for n in unit["verse_notes"])


def test_notes_and_rebuilds_still_validate() -> None:
    from scripts.validate_content import validate_all_content

    client, session_id, _ = _rebuild()
    client.transport.payloads.append(_verse_audit())
    analysis.analyze_rebuild(client, session_id, UNIT_ID)

    assert validate_all_content()["errors"] == []


# -- Word suggestions --------------------------------------------------------


def _suggestions(count: int) -> dict[str, Any]:
    return {
        "suggestions": [
            {
                "text": f"choice {i}",
                "sense": "meditate",
                "rationale": "why",
                "fit": "two syllables, stressed on the first, on the 6/8 downbeat",
                "line": f"he choice-{i} that teaching",
            }
            for i in range(count)
        ]
    }


def _first_token() -> str:
    return registry_service.load_unit(UNIT_ID)["tokens"][0]["token_id"]


def test_word_choices_must_work_within_the_psalm_guidance() -> None:
    translation.set_guidance(PSALM_ID, "Target 6/8 meter.")

    prompt = translation.build_suggestion_prompt(UNIT_ID, [_first_token()], "lyric")

    heading = "## Translator guidance for this psalm (every choice must work within it)"
    assert prompt.index(heading) < prompt.index("## The word(s) in focus")
    assert "Target 6/8 meter." in prompt
    assert "count its syllables" in prompt
    assert "fit:" in prompt
    # Each choice comes back inside its line, so it can be judged in context.
    assert "line: the line of the current lyric that holds the word" in prompt


def test_choices_made_under_older_guidance_are_flagged_outdated() -> None:
    translation.set_guidance(PSALM_ID, "Target 6/8 meter.")
    client, session_id = _session([_suggestions(3)])
    translation.suggest_word_renderings(client, session_id, UNIT_ID, [_first_token()])
    assert translation.cached_suggestions(UNIT_ID, [_first_token()], "lyric")["outdated"] is False

    translation.set_guidance(PSALM_ID, "Target common meter (8.6.8.6).")

    cached = translation.cached_suggestions(UNIT_ID, [_first_token()], "lyric")
    assert cached["outdated"] is True
    assert cached["outdated_reason"] == "guidance"


def test_choices_from_an_older_narrower_prompt_are_flagged_outdated() -> None:
    client, session_id = _session([_suggestions(3)])
    translation.suggest_word_renderings(client, session_id, UNIT_ID, [_first_token()])
    cache = json.loads(translation._suggestions_path().read_text(encoding="utf-8"))
    for entry in cache.values():
        entry.pop("template_version")  # as the lists made before full-range choices were
    translation._suggestions_path().write_text(json.dumps(cache), encoding="utf-8")

    cached = translation.cached_suggestions(UNIT_ID, [_first_token()], "lyric")

    assert cached["outdated"] is True
    assert cached["outdated_reason"] == "prompt"


def test_the_prompt_lists_every_corpus_reading_of_the_word(monkeypatch) -> None:
    token = registry_service.load_unit(UNIT_ID)["tokens"][0]
    elsewhere: dict[str, Any] = {
        ref: None for ref in token["same_psalm_occurrence_refs"] + token["corpus_occurrence_refs"]
    }
    elsewhere["Psalm 32:1"] = {
        "matches": [{"display_gloss": "blessed are they", "greek": "μακάριοι"}],
        "english_text": "How blessed is the one\nwhose wrong is forgiven",
    }

    def occurrence_context(token_id: str, ref: str, layer: str) -> dict[str, Any]:
        if elsewhere[ref] is None:
            raise NotFoundError(f"Verse not found: {ref}")
        return elsewhere[ref]

    monkeypatch.setattr(comparisons, "occurrence_context", occurrence_context)

    prompt = translation.build_suggestion_prompt(UNIT_ID, [token["token_id"]], "lyric")

    here = token.get("display_gloss") or "?"
    assert f'"{here}" (LXX {token["greek"]}): here' in prompt
    assert '"blessed are they" (LXX μακάριοι): Psalm 32:1' in prompt
    assert "Psalm 32:1: How blessed is the one / whose wrong is forgiven" in prompt
    assert "every distinct sense in the corpus readings and the lexical range" in prompt


def test_asking_again_keeps_every_earlier_choice() -> None:
    token_id = _first_token()
    client, session_id = _session([_suggestions(4), _suggestions(3)])
    translation.suggest_word_renderings(client, session_id, UNIT_ID, [token_id])

    result = translation.suggest_word_renderings(client, session_id, UNIT_ID, [token_id])

    second_prompt = client.transport.prompts()[1]
    assert "## Choices offered for this word before" in second_prompt
    assert "  - choice 3" in second_prompt
    # The new list left "choice 3" out, so it follows the new list, marked as earlier.
    assert [s["text"] for s in result["suggestions"]] == [f"choice {i}" for i in range(4)]
    assert result["suggestions"][3]["earlier"] is True
    assert "earlier" not in result["suggestions"][0]


@pytest.mark.parametrize("missing", ["fit", "line"])
def test_a_suggestion_without_fit_or_line_fails_the_contract(missing: str) -> None:
    reply = _suggestions(3)
    for item in reply["suggestions"]:
        del item[missing]
    client, session_id = _session([reply])

    result = translation.suggest_word_renderings(client, session_id, UNIT_ID, [_first_token()])

    assert result["status"] == translation.RUN_INVALID_OUTPUT


def test_a_rebuild_keeps_to_the_psalm_guidance() -> None:
    translation.set_guidance(PSALM_ID, "Target 6/8 meter.")
    client, _, _ = _rebuild()

    prompt = client.transport.prompts()[0]

    assert "Target 6/8 meter." in prompt
    assert prompt.index("Target 6/8 meter.") < prompt.index("## Reviewer notes on this verse")
    assert "Keep to the translator guidance for this psalm above" in prompt


def test_the_table_row_carries_the_verse_word_choices() -> None:
    client, session_id = _session([_suggestions(4)])
    translation.suggest_word_renderings(client, session_id, UNIT_ID, [_first_token()])

    table = comparisons.build_comparison_table(PSALM_ID)
    row = next(row for row in table["rows"] if UNIT_ID in row["unit_ids"])

    assert [entry["token_ids"] for entry in row["word_choices"]] == [[_first_token()]]
    assert len(row["word_choices"][0]["suggestions"]) == 4


def test_a_word_gets_at_least_three_ranked_suggestions_which_are_cached() -> None:
    token_id = registry_service.load_unit(UNIT_ID)["tokens"][0]["token_id"]
    client, session_id = _session([_suggestions(5)])

    result = translation.suggest_word_renderings(client, session_id, UNIT_ID, [token_id])

    assert [s["text"] for s in result["suggestions"]] == [f"choice {i}" for i in range(5)]
    assert f"{token_id}:" in client.transport.prompts()[0]
    assert translation.cached_suggestions(UNIT_ID, [token_id], "lyric") == {
        **result,
        "outdated": False,
        "outdated_reason": None,
    }


def test_a_word_may_get_up_to_twenty_choices_but_no_more() -> None:
    token_id = _first_token()
    client, session_id = _session(
        [_suggestions(translation.MAX_SUGGESTIONS), _suggestions(translation.MAX_SUGGESTIONS + 1)]
    )

    full = translation.suggest_word_renderings(client, session_id, UNIT_ID, [token_id])
    over = translation.suggest_word_renderings(client, session_id, UNIT_ID, [token_id])

    assert translation.MAX_SUGGESTIONS == 20
    assert len(full["suggestions"]) == 20
    assert over["status"] == translation.RUN_INVALID_OUTPUT


def test_fewer_than_three_suggestions_fails_the_contract_and_is_not_cached() -> None:
    token_id = registry_service.load_unit(UNIT_ID)["tokens"][0]["token_id"]
    client, session_id = _session([_suggestions(2)])

    result = translation.suggest_word_renderings(client, session_id, UNIT_ID, [token_id])

    assert result["status"] == translation.RUN_INVALID_OUTPUT
    assert translation.cached_suggestions(UNIT_ID, [token_id], "lyric") is None
