from __future__ import annotations

from copy import deepcopy

import pytest

from app.services.source_origin_service import arrangement_choices

pytestmark = pytest.mark.no_seeded_repo


@pytest.fixture
def recorded_choice():
    unit_id = "ps025.v001.a"
    token_id = "lxx.authored.r0001.ps024.v001.t001"
    note = {
        "briefing_run_id": "brief.authored",
        "question_index": 0,
        "question": {"topic": "A word", "verses": [1]},
        "answer": "Follow the Greek reading.",
        "notes": "Keep this decision.",
    }
    rendering = {
        "rendering_id": "rnd.authored",
        "layer": "lyric",
        "status": "proposed",
        "text": "a word",
        "translation_id": "tr.authored",
        "translation_basis": {
            "basis_type": "septuagint_greek_to_english",
            "source_language": "grc",
            "source_ids": ["lxx", "authored"],
            "source_version": "authored:r0001:" + "0" * 64,
        },
        "source_anchor": {
            "source_language": "grc",
            "source_text": "λόγος",
            "token_ids": [token_id],
        },
        "provenance": {"translation_context": {"annotations": [note]}},
    }
    arrangement = {
        "layer": "lyric",
        "translation_id": "tr.authored",
        "sections": [
            {
                "lines": [
                    {
                        "line_id": "ln.0001",
                        "text": "a word",
                        "rationale": "Follows Greek Psalm 24:1.",
                        "anchors": [{"unit_id": unit_id, "token_ids": ["ps025.v001.t001"]}],
                    }
                ]
            }
        ],
    }
    psalm = {"units": [{"unit_id": unit_id, "ref": "Psalm 25:1", "renderings": [rendering]}]}
    greek = {
        "available": True,
        "edition_id": "authored",
        "text_revision_id": "r0001",
        "by_mt_unit": {
            unit_id: {
                "units": [
                    {
                        "ref": "Greek Psalm 24:1",
                        "source_greek": "λόγος",
                        "tokens": [{"token_id": token_id}],
                    }
                ]
            }
        },
    }
    return psalm, arrangement, greek


def test_phrase_scope_comes_from_recorded_line_and_retains_exact_decision(recorded_choice):
    before = deepcopy(recorded_choice)
    result = arrangement_choices(*recorded_choice)
    assert len(result) == 1
    assert result[0]["text"] == "a word"
    assert result[0]["greek_reference"] == "Greek Psalm 24:1"
    assert result[0]["decisions"][0]["notes"] == "Keep this decision."
    assert result[0]["decision_scope"] == "verse_translation"
    assert result[0]["status"] == "proposed"
    assert recorded_choice == before


@pytest.mark.parametrize(
    "mismatch",
    [
        "blocked",
        "text",
        "tokens",
        "revision",
        "reference",
        "translation",
        "no_claim",
        "negative",
        "identity",
        "language",
        "rejected",
    ],
)
def test_unresolved_or_unrecorded_source_claims_never_gain_phrase_highlights(
    recorded_choice, mismatch
):
    psalm, arrangement, greek = recorded_choice
    rendering = psalm["units"][0]["renderings"][0]
    line = arrangement["sections"][0]["lines"][0]
    if mismatch == "blocked":
        greek["available"] = False
    elif mismatch == "text":
        rendering["source_anchor"]["source_text"] = "invented"
    elif mismatch == "tokens":
        rendering["source_anchor"]["token_ids"] = ["lxx.other.r0001.ps024.v001.t001"]
    elif mismatch == "revision":
        rendering["translation_basis"]["source_version"] = "authored:r0002:" + "0" * 64
    elif mismatch == "reference":
        line["rationale"] = "Follows Greek Psalm 24:2."
    elif mismatch == "translation":
        rendering["translation_id"] = "another-translation"
    elif mismatch == "identity":
        rendering["translation_basis"]["source_ids"] = ["lxx", "another-edition"]
    elif mismatch == "language":
        rendering["translation_basis"]["source_language"] = "he"
    elif mismatch == "rejected":
        rendering["status"] = "rejected"
    elif mismatch == "no_claim":
        line["rationale"] = "Shares vocabulary with the Greek, but no source choice is recorded."
    else:
        line["rationale"] = "Does not follow Greek Psalm 24:1."
    assert arrangement_choices(psalm, arrangement, greek) == []


@pytest.mark.parametrize(
    ("hint", "text", "phrase", "numbers"),
    [
        (
            "Hebrew ps025.v001.t001–t002 → in your truth.",
            "I please you in your truth.",
            "in your truth",
            [1, 2],
        ),
        (
            "Hebrew ps025.v001.t001 and t003 → I wash my hands.",
            "I wash my hands among the innocent.",
            "I wash my hands",
            [1, 3],
        ),
        (
            "Hebrew ps025.v001.t001 → your temple, identifying the sacred house.",
            "your temple's beauty",
            "your temple's",
            [1],
        ),
    ],
)
def test_mixed_phrases_use_explicit_hebrew_hints(recorded_choice, hint, text, phrase, numbers):
    psalm, arrangement, _ = recorded_choice
    unit = psalm["units"][0]
    unit["tokens"] = [{"token_id": f"ps025.v001.t{n:03d}"} for n in range(1, 4)]
    line = arrangement["sections"][0]["lines"][0]
    line["text"] = text
    line["anchors"][0]["token_ids"] = [token["token_id"] for token in unit["tokens"]]
    rendering = unit["renderings"][0]
    rendering["text"] = text
    rendering["provenance"]["alignment_hints"] = [hint]
    before = deepcopy(recorded_choice)
    result = arrangement_choices(*recorded_choice)[0]["hebrew_phrases"]
    assert len(result) == 1
    assert result[0]["text"] == phrase
    assert text[result[0]["start"] : result[0]["end"]] == phrase
    assert result[0]["token_ids"] == [f"ps025.v001.t{n:03d}" for n in numbers]
    assert recorded_choice == before


@pytest.mark.parametrize(
    "hint",
    [
        "Hebrew ps025.v001.t001 marks where Greek pleasing replaces Hebrew walking.",
        "Greek ps025.v001.t001 → a word.",
        "Hebrew ps025.v002.t001 → a word.",
        "Hebrew ps025.v001.t999 → a word.",
        "Hebrew ps025.v001.t001 → an earlier wording.",
    ],
)
def test_correspondence_notes_and_stale_hints_do_not_claim_hebrew_phrases(recorded_choice, hint):
    psalm, _, _ = recorded_choice
    psalm["units"][0]["tokens"] = [{"token_id": "ps025.v001.t001"}]
    psalm["units"][0]["renderings"][0]["provenance"]["alignment_hints"] = [hint]
    assert arrangement_choices(*recorded_choice)[0]["hebrew_phrases"] == []
