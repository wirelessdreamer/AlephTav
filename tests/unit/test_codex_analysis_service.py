"""The analysis pass: verse and psalm scope, staleness, idempotency, guards."""

from __future__ import annotations

import json
from collections import deque
from typing import Any

import pytest

from app.core.errors import ValidationError
from app.services import codex_analysis_service as analysis
from app.services import codex_app_server_service as codex
from app.services import codex_translation_service as translation
from app.services import comparison_assessment_service as comparisons
from app.services import registry_service, rendering_service

UNIT_ID = "ps001.v001.a"
PSALM_ID = "ps001"


@pytest.fixture(autouse=True)
def _clean_session_store():
    translation._store_path().unlink(missing_ok=True)
    yield
    translation._store_path().unlink(missing_ok=True)


def _verse_payload(**overrides: Any) -> dict[str, Any]:
    payload = {
        "unit_id": UNIT_ID,
        "accuracy_rating": "close",
        "accuracy_note": "Keeps the walking/standing/sitting progression.",
        "creative_liberties_note": "Contracted for singability.",
        "literal_backbone": ["Blessed is the one who does not walk in the counsel of the wicked"],
        "word_notes": [
            {
                "token_ids": ["ps001.v001.t001"],
                "transliteration": "ashre",
                "lexical_gloss": "blessedness of, happy is",
                "rendered_as": "How blessed",
                "verdict": "expansion",
                "note": "Plural construct heightened into an exclamation.",
            }
        ],
        "non_source_material": [],
    }
    payload.update(overrides)
    return payload


def _psalm_payload(**overrides: Any) -> dict[str, Any]:
    payload = {
        "psalm_id": PSALM_ID,
        "summary": "Two ways, contrasted and then judged.",
        "sections": [
            {
                "title": "Verse 1",
                "first_verse": 1,
                "last_verse": 1,
                "theme": "the way of the righteous",
                "arc_note": "Negative definition of the blessed life.",
            }
        ],
        "structural_seams": [],
        "guardrails": {
            "heading_attribution": "Psalm 1 carries no heading; it names no author.",
            "cultic_setting": "Wisdom framing rather than temple liturgy.",
        },
        "epistemics": {
            "known_from_text": [
                {"claim": "The psalm contrasts two ways.", "basis": "vv. 1-2 against vv. 4-5."}
            ],
            "not_known_from_text": [
                {"claim": "No author is named.", "why_not": "The psalm has no superscription."}
            ],
        },
        "non_source_material": [],
        "method": "Compact literal renderings checked against the Masoretic text.",
        "citations": [],
    }
    payload.update(overrides)
    return payload


class ScriptedTransport:
    """Replies to every turn with the queued payload."""

    def __init__(self, payloads: list[dict[str, Any]]) -> None:
        self.payloads = list(payloads)
        self.sent: list[dict[str, Any]] = []
        self._inbox: deque[str] = deque()
        self.turn = 0

    def send(self, message: dict[str, Any]) -> None:
        self.sent.append(message)
        method = message.get("method")
        if method == "thread/start":
            self._push({"jsonrpc": "2.0", "id": message["id"], "result": {"threadId": "th-1"}})
        elif method == "turn/start":
            self.turn += 1
            turn_id = f"turn-{self.turn}"
            body = self.payloads.pop(0) if self.payloads else {}
            self._push({"jsonrpc": "2.0", "id": message["id"], "result": {"turnId": turn_id}})
            self._push(
                {
                    "jsonrpc": "2.0",
                    "method": "item/completed",
                    "params": {"item": {"type": "agentMessage", "text": json.dumps(body)}},
                }
            )
            self._push(
                {"jsonrpc": "2.0", "method": "turn/completed", "params": {"turnId": turn_id}}
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
            m["params"]["input"][0]["data"]["text"]
            for m in self.sent
            if m.get("method") == "turn/start"
        ]


def _session(payloads: list[dict[str, Any]]):
    client = codex.CodexAppServerClient(transport=ScriptedTransport(payloads))
    session = translation.create_session(client, psalm_id=PSALM_ID, purpose="analysis")
    return client, session["session_id"]


# -- Independence ----------------------------------------------------------


def test_the_auditor_never_sees_the_translators_guidance() -> None:
    translation.set_guidance(PSALM_ID, "Render YHWH as 'the LORD' and keep it raw.")

    verse_prompt = analysis.build_verse_analysis_prompt(UNIT_ID)
    psalm_prompt = analysis.build_psalm_analysis_prompt(PSALM_ID)

    # Feeding the translator's standing direction to the auditor would prime it
    # with the intent it is supposed to judge independently.
    for prompt in (verse_prompt, psalm_prompt):
        assert "Render YHWH" not in prompt
        assert "Translator guidance" not in prompt


def test_the_verse_prompt_carries_token_ids_and_the_text_under_audit() -> None:
    prompt = analysis.build_verse_analysis_prompt(UNIT_ID)
    unit = registry_service.load_unit(UNIT_ID)

    assert unit["source_hebrew"] in prompt
    assert unit["tokens"][0]["token_id"] in prompt
    assert "not translating" in prompt
    assert "Literal rendering under audit" in prompt


# -- Verse scope -----------------------------------------------------------


def test_analysis_records_the_verdict_as_a_proposed_assessment() -> None:
    client, session_id = _session([_verse_payload()])
    before = len(registry_service.load_unit(UNIT_ID)["renderings"])

    result = analysis.analyze_verse(client, session_id, UNIT_ID)

    assert result["status"] == translation.RUN_COMPLETED
    item = result["assessment"]
    assert item["accuracy_rating"] == "close"
    assert item["created_via"] == "codex"
    # The pass cannot mark its own verdict reviewed.
    assert item["status"] == "proposed"
    assert item["reviewer_id"] is None
    assert item["literal_backbone"] == _verse_payload()["literal_backbone"]
    assert item["word_notes"][0]["verdict"] == "expansion"
    assert item["analyzed_text_hash"]

    # It audits renderings; it must not create any.
    assert len(registry_service.load_unit(UNIT_ID)["renderings"]) == before


def test_rerunning_an_unchanged_verse_writes_nothing() -> None:
    client, session_id = _session([_verse_payload(), _verse_payload()])
    first = analysis.analyze_verse(client, session_id, UNIT_ID)

    second = analysis.analyze_verse(client, session_id, UNIT_ID)

    assert second["skipped"] is True
    assert second["assessment"]["comparison_id"] == first["assessment"]["comparison_id"]
    unit = registry_service.load_unit(UNIT_ID)
    assert len(unit["comparison_assessments"]) == 1, "a no-op re-run must not append a record"


def test_editing_a_rendering_in_place_makes_the_analysis_stale() -> None:
    client, session_id = _session([_verse_payload()])
    analysis.analyze_verse(client, session_id, UNIT_ID)

    unit = registry_service.load_unit(UNIT_ID)
    stored = unit["comparison_assessments"][-1]
    before = stored["analyzed_text_hash"]

    # update_rendering mutates text under the SAME rendering_id, which is why
    # staleness cannot be keyed on the id.
    english = comparisons.select_rendering(unit, "lyric")
    rendering_service.update_rendering(
        english["rendering_id"],
        {"text": "A completely different line"},
        created_by="editor",
    )

    refreshed = registry_service.load_unit(UNIT_ID)
    literal = comparisons.select_rendering(refreshed, "literal")
    english = comparisons.select_rendering(refreshed, "lyric")
    after = analysis.verse_fingerprint(refreshed, [literal, english])

    assert after != before, "an edited rendering must change the fingerprint"


def test_a_second_analysis_supersedes_rather_than_overwrites() -> None:
    client, session_id = _session(
        [_verse_payload(), _verse_payload(accuracy_rating="adapted", accuracy_note="Looser.")]
    )
    first = analysis.analyze_verse(client, session_id, UNIT_ID)
    second = analysis.analyze_verse(client, session_id, UNIT_ID, force=True)

    assert second["assessment"]["accuracy_rating"] == "adapted"
    assert second["assessment"]["revision_of"] == first["assessment"]["comparison_id"]

    unit = registry_service.load_unit(UNIT_ID)
    stored = {i["comparison_id"]: i for i in unit["comparison_assessments"]}
    assert stored[first["assessment"]["comparison_id"]]["status"] == "superseded"
    # The original verdict survives intact.
    assert stored[first["assessment"]["comparison_id"]]["accuracy_rating"] == "close"


def test_word_notes_pointing_at_unknown_tokens_are_rejected() -> None:
    payload = _verse_payload()
    payload["word_notes"][0]["token_ids"] = ["ps099.v001.t001"]
    client, session_id = _session([payload])

    with pytest.raises(ValidationError, match="tokens not in"):
        analysis.analyze_verse(client, session_id, UNIT_ID)


def test_invalid_output_creates_no_assessment_and_is_preserved() -> None:
    client, session_id = _session([{"unit_id": UNIT_ID, "accuracy_rating": "close"}])

    result = analysis.analyze_verse(client, session_id, UNIT_ID)

    assert result["status"] == translation.RUN_INVALID_OUTPUT
    assert result["assessment"] is None
    run = translation.get_run(result["run_id"])
    assert run["validation"], "the failed run is preserved for the retry action"
    assert registry_service.load_unit(UNIT_ID).get("comparison_assessments", []) == []


# -- Psalm scope -----------------------------------------------------------


def test_psalm_analysis_lands_on_the_meta_file_with_an_audit_record() -> None:
    client, session_id = _session([_psalm_payload()])

    result = analysis.analyze_psalm_scope(client, session_id, PSALM_ID)

    record = result["analysis"]
    assert record["psalm_analysis_id"].startswith("anl.ps001.")
    assert record["status"] == "proposed"
    assert record["sections"][0]["title"] == "Verse 1"
    assert record["epistemics"]["not_known_from_text"][0]["why_not"]
    assert record["source_fingerprint"]

    meta = registry_service.load_psalm_meta(PSALM_ID)
    assert [a["psalm_analysis_id"] for a in meta["analyses"]] == [record["psalm_analysis_id"]]

    # The audit record is anchored on the psalm's first unit, because audit ids
    # are patterned to a unit, but every field describes the meta payload.
    anchor = registry_service.load_unit(meta["unit_ids"][0])
    audit = next(r for r in anchor["audit_records"] if r["audit_id"] in record["audit_ids"])
    assert audit["entity_type"] == "psalm_analysis"
    assert audit["entity_id"] == record["psalm_analysis_id"]


def _six_verse_psalm() -> dict[str, Any]:
    return {
        "psalm_id": "ps066",
        "unit_ids": [f"ps066.v{n:03d}.a" for n in range(1, 7)],
    }


def _section(title: str, first: int, last: int) -> dict[str, Any]:
    return {
        "title": title,
        "first_verse": first,
        "last_verse": last,
        "theme": "t",
        "arc_note": "",
    }


def test_sections_covering_every_verse_in_order_are_accepted() -> None:
    analysis._assert_sections_tile(
        _six_verse_psalm(), [_section("A", 1, 3), _section("B", 4, 6)]
    )


def test_sections_that_leave_a_gap_are_rejected() -> None:
    with pytest.raises(ValidationError, match="do not tile"):
        # Verse 4 falls through the gap.
        analysis._assert_sections_tile(
            _six_verse_psalm(), [_section("A", 1, 3), _section("B", 5, 6)]
        )


def test_sections_that_overlap_are_rejected() -> None:
    with pytest.raises(ValidationError, match="do not tile"):
        analysis._assert_sections_tile(
            _six_verse_psalm(), [_section("A", 1, 4), _section("B", 4, 6)]
        )


def test_sections_that_stop_short_of_the_psalm_are_rejected() -> None:
    with pytest.raises(ValidationError, match="coverage stops"):
        analysis._assert_sections_tile(
            _six_verse_psalm(), [_section("A", 1, 3), _section("B", 4, 5)]
        )


def test_sections_that_do_not_start_at_the_first_verse_are_rejected() -> None:
    with pytest.raises(ValidationError, match="do not tile"):
        analysis._assert_sections_tile(_six_verse_psalm(), [_section("A", 2, 6)])


def test_rerunning_an_unchanged_psalm_writes_nothing() -> None:
    client, session_id = _session([_psalm_payload(), _psalm_payload()])
    analysis.analyze_psalm_scope(client, session_id, PSALM_ID)

    second = analysis.analyze_psalm_scope(client, session_id, PSALM_ID)

    assert second["skipped"] is True
    meta = registry_service.load_psalm_meta(PSALM_ID)
    assert len(meta["analyses"]) == 1


def test_a_second_psalm_analysis_supersedes_the_first() -> None:
    client, session_id = _session(
        [_psalm_payload(), _psalm_payload(summary="Revised reading of the two ways.")]
    )
    first = analysis.analyze_psalm_scope(client, session_id, PSALM_ID)
    second = analysis.analyze_psalm_scope(client, session_id, PSALM_ID, force=True)

    assert second["analysis"]["revision_of"] == first["analysis"]["psalm_analysis_id"]
    meta = registry_service.load_psalm_meta(PSALM_ID)
    statuses = {a["psalm_analysis_id"]: a["status"] for a in meta["analyses"]}
    assert statuses[first["analysis"]["psalm_analysis_id"]] == "superseded"
    assert analysis.active_analysis(PSALM_ID)["summary"] == "Revised reading of the two ways."


def test_meta_carrying_an_analysis_still_validates() -> None:
    from scripts.validate_content import validate_all_content

    client, session_id = _session([_psalm_payload()])
    analysis.analyze_psalm_scope(client, session_id, PSALM_ID)

    assert validate_all_content()["errors"] == []


# -- Run kinds -------------------------------------------------------------


def test_an_analysis_run_cannot_be_fed_to_the_rendering_saver() -> None:
    client, session_id = _session([_verse_payload()])
    result = analysis.analyze_verse(client, session_id, UNIT_ID)

    # Its payload is truthy but carries no candidates, so without the kind guard
    # this would silently return [] and read as a successful no-op.
    with pytest.raises(ValidationError, match="produces no renderings"):
        translation.save_run_candidates(result["run_id"])


# -- Surfacing in the table ------------------------------------------------


def test_the_table_row_carries_the_evidence_and_reports_freshness() -> None:
    client, session_id = _session([_verse_payload()])
    analysis.analyze_verse(client, session_id, UNIT_ID)

    table = comparisons.build_comparison_table(PSALM_ID)
    row = next(r for r in table["rows"] if UNIT_ID in r["unit_ids"])

    assert row["accuracy_rating"] == "close"
    assert row["literal_backbone"]
    assert row["stale"] is False

    # The word note rides the study card for the token it is about.
    card = next(c for c in row["tokens"] if c["token_id"] == "ps001.v001.t001")
    assert card["note"]["verdict"] == "expansion"
    assert all("note" not in c for c in row["tokens"] if c["token_id"] != "ps001.v001.t001")


def test_editing_the_audited_rendering_marks_the_row_stale() -> None:
    client, session_id = _session([_verse_payload()])
    analysis.analyze_verse(client, session_id, UNIT_ID)

    unit = registry_service.load_unit(UNIT_ID)
    english = comparisons.select_rendering(unit, "lyric")
    rendering_service.update_rendering(
        english["rendering_id"], {"text": "Rewritten after the audit"}, created_by="editor"
    )

    table = comparisons.build_comparison_table(PSALM_ID)
    row = next(r for r in table["rows"] if UNIT_ID in r["unit_ids"])

    # The rendering id is unchanged; only the content moved.
    assert row["english_text"] == "Rewritten after the audit"
    assert row["stale"] is True


def test_a_human_written_assessment_is_never_reported_stale() -> None:
    literal = comparisons.select_rendering(registry_service.load_unit(UNIT_ID), "literal")
    english = comparisons.select_rendering(registry_service.load_unit(UNIT_ID), "lyric")
    comparisons.create_assessment(
        unit_id=UNIT_ID,
        literal_rendering_id=literal["rendering_id"],
        english_rendering_id=english["rendering_id"],
        accuracy_rating="close",
    )

    table = comparisons.build_comparison_table(PSALM_ID)
    row = next(r for r in table["rows"] if UNIT_ID in r["unit_ids"])

    assert row["stale"] is False


def test_the_table_envelope_carries_the_psalm_analysis_and_numbering() -> None:
    client, session_id = _session([_psalm_payload()])
    analysis.analyze_psalm_scope(client, session_id, PSALM_ID)

    table = comparisons.build_comparison_table(PSALM_ID)

    assert table["analysis"]["summary"] == "Two ways, contrasted and then judged."
    assert table["analysis"]["sections"][0]["title"] == "Verse 1"
    # Numbering comes from the committed table, not the model.
    assert table["canonical_numbering"]["mt"] == 1
    assert table["canonical_numbering"]["septuagint"] == [1]
