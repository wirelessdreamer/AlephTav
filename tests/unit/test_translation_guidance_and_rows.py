"""Per-psalm guidance, per-word study tokens, and end-to-end row fill."""

from __future__ import annotations

import json
from collections import deque
from typing import Any

import pytest

from app.services import codex_app_server_service as codex
from app.services import codex_translation_service as translation
from app.services import comparison_assessment_service, registry_service

UNIT_ID = "ps001.v001.a"


@pytest.fixture(autouse=True)
def _clean_session_store():
    translation._store_path().unlink(missing_ok=True)
    yield
    translation._store_path().unlink(missing_ok=True)


class ScriptedTransport:
    """Returns a fresh valid candidate for every turn."""

    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []
        self._inbox: deque[str] = deque()
        self.turn = 0

    def send(self, message: dict[str, Any]) -> None:
        self.sent.append(message)
        method = message.get("method")
        if method == "thread/start":
            self._push(
                {"jsonrpc": "2.0", "id": message["id"], "result": {"thread": {"id": "th-1"}}}
            )
        elif method == "turn/start":
            self.turn += 1
            turn_id = f"turn-{self.turn}"
            self._push({"jsonrpc": "2.0", "id": message["id"], "result": {"turn": {"id": turn_id}}})
            self._push(
                {
                    "jsonrpc": "2.0",
                    "method": "item/completed",
                    "params": {
                        "item": {"type": "agentMessage", "text": json.dumps(_payload(self.turn))}
                    },
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


def _payload(turn: int) -> dict[str, Any]:
    return {
        "unit_id": UNIT_ID,
        "layer": "lyric",
        "candidates": [
            {
                "text": f"Generated line {turn}",
                "rationale": "tracks the Hebrew",
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
                "delivery_profile": "spoken",
                "source_anchor": {
                    "anchor_text": "a",
                    "source_language": "he",
                    "source_text": "b",
                    "basis_note": "c",
                },
                "accuracy_note": "Tracks the Hebrew clause order.",
                "creative_liberties_note": "Contracted for singability.",
                "literalness": "very_close",
            }
        ],
    }


def _client() -> codex.CodexAppServerClient:
    return codex.CodexAppServerClient(transport=ScriptedTransport())


# -- Guidance --------------------------------------------------------------


def test_guidance_round_trips_on_the_psalm_meta_file() -> None:
    assert translation.get_guidance("ps001") == ""

    translation.set_guidance("ps001", "  Keep it raw. No devotional smoothing.  ")

    assert translation.get_guidance("ps001") == "Keep it raw. No devotional smoothing."
    meta = registry_service.load_psalm_meta("ps001")
    assert meta["translation_guidance"] == "Keep it raw. No devotional smoothing."
    # Guidance must not disturb the rest of the meta record.
    assert meta["psalm_id"] == "ps001" and meta["unit_ids"]


def test_clearing_guidance_removes_the_field() -> None:
    translation.set_guidance("ps001", "temporary")
    translation.set_guidance("ps001", "   ")

    assert translation.get_guidance("ps001") == ""
    assert "translation_guidance" not in registry_service.load_psalm_meta("ps001")


def test_guidance_is_injected_into_the_prompt_above_style_rules() -> None:
    translation.set_guidance("ps001", "Never use the word 'blessed'.")

    prompt = translation.build_translation_prompt(UNIT_ID, "lyric")

    assert "Never use the word 'blessed'." in prompt
    assert "Translator guidance for this psalm" in prompt
    # It must precede the source so the model reads intent before evidence.
    assert prompt.index("Never use the word") < prompt.index("## Hebrew source meaning")


def test_prompt_omits_the_guidance_section_when_none_is_set() -> None:
    prompt = translation.build_translation_prompt(UNIT_ID, "lyric")
    assert "Translator guidance" not in prompt


# -- Study tokens ----------------------------------------------------------


def test_comparison_rows_carry_per_word_study_tokens() -> None:
    table = comparison_assessment_service.build_comparison_table("ps001")
    row = next(row for row in table["rows"] if UNIT_ID in row["unit_ids"])

    assert row["tokens"], "each row needs its Hebrew words for the study card"
    unit = registry_service.load_unit(UNIT_ID)
    assert len(row["tokens"]) == len(unit["tokens"])

    card = row["tokens"][1]
    assert card["surface"] and card["token_id"]
    # The fields that make it a study guide rather than just a word.
    for field in ("lemma", "strong", "display_gloss", "morph_readable"):
        assert card.get(field), f"{field} missing from study card"
    assert card["occurrence_count"] >= 0


def test_study_token_drops_empty_fields_instead_of_emitting_nulls() -> None:
    card = comparison_assessment_service.study_token(
        {
            "token_id": "ps001.v001.t001",
            "surface": "אַשְׁרֵי",
            "lemma": "אֶשֶׁר",
            "strong": "H835",
            "semantic_role": None,
            "referent": None,
            "corpus_occurrence_refs": ["Psalm 2:12", "Psalm 32:1"],
        }
    )

    assert card["lemma"] == "אֶשֶׁר"
    assert "semantic_role" not in card
    assert "referent" not in card
    assert card["occurrence_count"] == 2


# -- Row fill --------------------------------------------------------------


def test_fill_row_creates_renderings_but_never_the_verdict() -> None:
    client = _client()
    session = translation.create_session(client, psalm_id="ps001", unit_id=UNIT_ID)

    result = translation.fill_comparison_row(client, session["session_id"], UNIT_ID)

    assert result["status"] == translation.RUN_COMPLETED
    # The fixture unit already has a literal rendering, so only the English
    # layer is generated and the existing baseline is reused.
    assert len(result["run_ids"]) == 1
    assert len(result["rendering_ids"]) == 1

    # The two passes are separate: translating must not stamp the Accuracy
    # column, even though the candidate carried a literalness rating.
    assert result["assessment"] is None
    unit = registry_service.load_unit(UNIT_ID)
    assert unit.get("comparison_assessments", []) == []

    unit = registry_service.load_unit(UNIT_ID)
    generated = [r for r in unit["renderings"] if r["rendering_id"] in result["rendering_ids"]]
    assert generated and all(r["status"] == "proposed" for r in generated)


def test_fill_row_generates_a_literal_baseline_when_the_unit_lacks_one() -> None:
    # Strip the literal rendering so the row has no baseline to reuse.
    unit = registry_service.load_unit(UNIT_ID)
    unit["renderings"] = [r for r in unit["renderings"] if r["layer"] != "literal"]
    unit["canonical_rendering_ids"] = [
        r for r in unit["canonical_rendering_ids"] if ".literal." not in r
    ]
    registry_service.save_unit(unit)

    client = _client()
    session = translation.create_session(client, psalm_id="ps001", unit_id=UNIT_ID)
    result = translation.fill_comparison_row(client, session["session_id"], UNIT_ID)

    assert result["status"] == translation.RUN_COMPLETED
    # Literal first, then the English layer.
    assert len(result["run_ids"]) == 2
    assert len(result["rendering_ids"]) == 2
    assert result["assessment"] is None


def test_translated_row_has_text_but_no_accuracy_until_analysis_runs() -> None:
    client = _client()
    session = translation.create_session(client, psalm_id="ps001", unit_id=UNIT_ID)
    translation.fill_comparison_row(client, session["session_id"], UNIT_ID)

    table = comparison_assessment_service.build_comparison_table("ps001")
    row = next(row for row in table["rows"] if UNIT_ID in row["unit_ids"])

    assert row["literal_text"]
    assert row["english_text"]
    # Both columns of text are filled, but the verdict columns stay empty: the
    # analysis pass owns them.
    assert row["accuracy_rating"] is None
    assert row["accuracy_note"] == ""
    assert row["creative_liberties_note"] == ""
    assert row["incomplete"] is False


def test_row_fill_uses_the_psalm_guidance() -> None:
    translation.set_guidance("ps001", "Render YHWH as 'the LORD'.")
    client = _client()
    session = translation.create_session(client, psalm_id="ps001", unit_id=UNIT_ID)

    translation.fill_comparison_row(client, session["session_id"], UNIT_ID)

    assert all("Render YHWH as 'the LORD'." in prompt for prompt in client.transport.prompts())
