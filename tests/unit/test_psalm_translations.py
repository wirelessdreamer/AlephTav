"""Several translations of one psalm, each with its own English, guidance and analyses.

The Hebrew and the literal are shared; everything written in English belongs to the
translation it was written for. Records of the psalm's main translation carry no id.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.core.errors import NotFoundError, ValidationError
from app.services import (
    arrangement_service,
    registry_service,
    rendering_service,
    verse_notes_service,
)
from app.services import codex_analysis_service as analysis
from app.services import codex_app_server_service as codex
from app.services import codex_import_service as importing
from app.services import codex_translation_service as translation
from app.services import comparison_assessment_service as comparisons
from app.services import psalm_translations_service as translations
from tests.unit.test_codex_analysis_service import _psalm_payload
from tests.unit.test_import_translation import PASTE, _reading
from tests.unit.test_verse_notes import (
    ScriptedTransport,
    _candidate,
    _rebuild_reply,
    _suggestions,
    _verse_audit,
)

PSALM_ID = "ps001"
UNIT_ID = "ps001.v001.a"


@pytest.fixture(autouse=True)
def _restore_psalm():
    translation._store_path().unlink(missing_ok=True)
    translation._suggestions_path().unlink(missing_ok=True)
    meta = registry_service.load_psalm_meta(PSALM_ID)
    unit = registry_service.load_unit(UNIT_ID)
    yield
    registry_service.save_psalm_meta(PSALM_ID, meta)
    registry_service.save_unit(unit)
    translation._store_path().unlink(missing_ok=True)
    translation._suggestions_path().unlink(missing_ok=True)


def _added(title: str = "Sung in 6/8") -> str:
    return translations.create_translation(PSALM_ID, title)["translation_id"]


def _session(
    payloads: list[Any], translation_id: str | None
) -> tuple[codex.CodexAppServerClient, str]:
    client = codex.CodexAppServerClient(transport=ScriptedTransport(payloads))
    session = translation.create_session(client, psalm_id=PSALM_ID, translation_id=translation_id)
    return client, session["session_id"]


def _row(translation_id: str | None = None) -> dict[str, Any]:
    table = comparisons.build_comparison_table(PSALM_ID, translation_id=translation_id)
    return next(row for row in table["rows"] if UNIT_ID in row["unit_ids"])


def _lyric(text: str, translation_id: str | None) -> dict[str, Any]:
    return rendering_service.create_rendering(
        UNIT_ID, "lyric", text, "proposed", "test", "tester", translation_id=translation_id
    )


def _passage(layer: str, text: str) -> dict[str, Any]:
    return {
        "psalm_id": PSALM_ID,
        "layer": layer,
        "units": [{"unit_id": UNIT_ID, "layer": layer, "candidates": [_candidate(text)]}],
    }


# -- The translations themselves ---------------------------------------------------


def test_a_new_translation_is_listed_after_the_main_one_with_an_audit_record() -> None:
    created = translations.create_translation(PSALM_ID, "Sung in 6/8")

    assert created["translation_id"] == "tr.ps001.0001"
    listed = translations.list_translations(PSALM_ID)
    assert [t["translation_id"] for t in listed] == [None, "tr.ps001.0001"]
    assert listed[0]["title"] == translations.MAIN_TITLE
    record = registry_service.load_unit(UNIT_ID)["audit_records"][-1]
    assert (record["entity_type"], record["entity_id"]) == ("translation", "tr.ps001.0001")
    assert created["audit_ids"] == [record["audit_id"]]
    assert _added("Another") == "tr.ps001.0002"


def test_a_translation_needs_a_name() -> None:
    with pytest.raises(ValidationError):
        translations.create_translation(PSALM_ID, "   ")


def test_an_unknown_translation_is_refused() -> None:
    with pytest.raises(NotFoundError):
        comparisons.build_comparison_table(PSALM_ID, translation_id="tr.ps001.0009")
    with pytest.raises(NotFoundError):
        _lyric("Happy the one", "tr.ps001.0009")


def test_each_translation_keeps_its_own_guidance() -> None:
    translation.set_guidance(PSALM_ID, "Keep it plain.")
    added = _added()

    translation.set_guidance(PSALM_ID, "Meter: 6/8", added)

    assert translation.get_guidance(PSALM_ID) == "Keep it plain."
    assert translation.get_guidance(PSALM_ID, added) == "Meter: 6/8"


# -- English is the translation's; the literal is shared ------------------------------


def test_a_new_translation_shares_the_literal_but_starts_without_english() -> None:
    main = _row()
    fresh = _row(_added())

    assert main["english_text"]
    assert fresh["literal_text"] == main["literal_text"]
    assert fresh["english_text"] is None
    assert fresh["incomplete"] is True


def test_only_english_renderings_are_marked_with_a_translation() -> None:
    added = _added()

    lyric = _lyric("Happy the one", added)
    literal = rendering_service.create_rendering(
        UNIT_ID, "literal", "Blessed the man", "proposed", "test", "tester", translation_id=added
    )

    assert lyric["translation_id"] == added
    assert "translation_id" not in literal
    assert _row(added)["english_text"] == "Happy the one"
    assert _row()["english_text"] != "Happy the one"


def test_translating_in_a_session_writes_that_translations_english_under_its_guidance() -> None:
    translation.set_guidance(PSALM_ID, "Keep it plain.")
    added = _added()
    translation.set_guidance(PSALM_ID, "Meter: 6/8", added)
    before = _row()["english_text"]
    client, session_id = _session([_passage("lyric", "Happy, happy the one")], added)

    result = translation.fill_psalm_passage(client, session_id, PSALM_ID, [UNIT_ID])

    assert result["status"] == translation.RUN_COMPLETED
    prompt = client.transport.prompts()[-1]
    assert "Meter: 6/8" in prompt
    assert "Keep it plain." not in prompt
    assert _row(added)["english_text"] == "Happy, happy the one"
    assert _row()["english_text"] == before


def test_a_verse_audit_belongs_to_the_translation_it_audits() -> None:
    added = _added()
    _lyric("Happy the one", added)
    main_client, main_session = _session([_verse_audit(accuracy_rating="close")], None)
    analysis.analyze_verse(main_client, main_session, UNIT_ID)
    client, session_id = _session([_verse_audit(accuracy_rating="adapted")], added)

    result = analysis.analyze_verse(client, session_id, UNIT_ID)

    assert result["assessment"]["translation_id"] == added
    assert "Happy the one" in client.transport.prompts()[0]
    assert _row()["accuracy_rating"] == "close"
    assert _row(added)["accuracy_rating"] == "adapted"


def test_each_translation_has_its_own_psalm_analysis() -> None:
    added = _added()
    main_client, main_session = _session([_psalm_payload(summary="The main reading.")], None)
    analysis.analyze_psalm_scope(main_client, main_session, PSALM_ID)
    client, session_id = _session([_psalm_payload(summary="The 6/8 setting.")], added)

    analysis.analyze_psalm_scope(client, session_id, PSALM_ID)

    assert analysis.active_analysis(PSALM_ID)["summary"] == "The main reading."
    assert analysis.active_analysis(PSALM_ID, added)["summary"] == "The 6/8 setting."
    table = comparisons.build_comparison_table(PSALM_ID, translation_id=added)
    assert table["analysis"]["summary"] == "The 6/8 setting."


def test_notes_and_rebuilds_stay_with_their_translation() -> None:
    added = _added()
    _lyric("Happy the one", added)
    verse_notes_service.add_note(UNIT_ID, "Name Yahweh.")
    note = verse_notes_service.add_note(UNIT_ID, "Keep it in 6/8.", translation_id=added)
    # The main translation has a rebuild waiting; that does not hold up the other one.
    main_client, main_session = _session([_rebuild_reply("lyric", "main rebuilt", [])], None)
    translation.rebuild_verse(main_client, main_session, UNIT_ID, layers=["english"])
    reply = _rebuild_reply(
        "lyric", "Happy, in six-eight", [{"note_id": note["note_id"], "response": "Kept."}]
    )
    client, session_id = _session([reply], added)

    result = translation.rebuild_verse(client, session_id, UNIT_ID, layers=["english"])

    assert result["status"] == translation.RUN_COMPLETED
    prompt = client.transport.prompts()[0]
    assert "Keep it in 6/8." in prompt
    assert "Name Yahweh." not in prompt
    assert "Happy the one" in prompt
    rebuild = result["rebuild"]
    assert rebuild["translation_id"] == added
    assert [n["note_id"] for n in _row(added)["verse_notes"]] == [note["note_id"]]
    assert _row(added)["pending_rebuild"]["rebuild_id"] == rebuild["rebuild_id"]
    assert _row()["pending_rebuild"]["rebuild_id"] != rebuild["rebuild_id"]

    verse_notes_service.accept_rebuild(UNIT_ID, rebuild["rebuild_id"])

    assert _row(added)["english_text"] == "Happy, in six-eight"


def test_word_choices_are_kept_per_translation() -> None:
    added = _added()
    token_id = registry_service.load_unit(UNIT_ID)["tokens"][0]["token_id"]
    client, session_id = _session([_suggestions(3)], added)

    translation.suggest_word_renderings(client, session_id, UNIT_ID, [token_id])

    assert translation.cached_suggestions(UNIT_ID, [token_id], "lyric") is None
    assert translation.cached_suggestions(UNIT_ID, [token_id], "lyric", added)["outdated"] is False
    assert _row(added)["word_choices"]
    assert _row()["word_choices"] == []


def test_song_settings_are_listed_per_translation() -> None:
    added = _added()

    view = arrangement_service.create_arrangement(PSALM_ID, title="In 6/8", translation_id=added)

    arrangement_id = view["arrangement"]["arrangement_id"]
    assert [
        a["arrangement_id"] for a in arrangement_service.list_arrangements(PSALM_ID, added)
    ] == [arrangement_id]
    assert arrangement_id not in {
        a["arrangement_id"] for a in arrangement_service.list_arrangements(PSALM_ID)
    }


def test_an_import_lands_in_the_sessions_translation() -> None:
    translation.set_guidance(PSALM_ID, "Keep it plain.")
    added = translations.create_translation(PSALM_ID, "Psalm 1, sung", created_via="import")[
        "translation_id"
    ]
    client, session_id = _session([_reading()], added)

    result = importing.import_translation(client, session_id, PSALM_ID, PASTE, layer="lyric")

    assert result["status"] == translation.RUN_COMPLETED
    assert result["translation_id"] == added
    # Nothing else is on show in the new translation, so the import is.
    assert result["renderings"][0]["shown"] is True
    assert _row(added)["english_text"] == (
        "How happy the one who won't walk\nwhere the wicked give counsel,"
    )
    assert translation.get_guidance(PSALM_ID) == "Keep it plain."
    assert "Meter: 6/8" in translation.get_guidance(PSALM_ID, added)


def test_content_written_in_an_added_translation_still_validates() -> None:
    from scripts.validate_content import validate_all_content

    added = _added()
    translation.set_guidance(PSALM_ID, "Meter: 6/8", added)
    _lyric("Happy the one", added)
    verse_notes_service.add_note(UNIT_ID, "Keep it in 6/8.", translation_id=added)
    arrangement_service.create_arrangement(PSALM_ID, title="In 6/8", translation_id=added)
    client, session_id = _session(
        [_verse_audit(), _psalm_payload(), _rebuild_reply("lyric", "rebuilt", [])], added
    )
    analysis.analyze_verse(client, session_id, UNIT_ID)
    analysis.analyze_psalm_scope(client, session_id, PSALM_ID)
    translation.rebuild_verse(client, session_id, UNIT_ID, layers=["english"])

    assert validate_all_content()["errors"] == []


# -- Which psalm a paste translates ------------------------------------------------


def _identify(payload: dict[str, Any]) -> tuple[codex.CodexAppServerClient, dict[str, Any]]:
    client = codex.CodexAppServerClient(transport=ScriptedTransport([payload]))
    return client, importing.identify_psalm(client, PASTE)


def _identification(**overrides: Any) -> dict[str, Any]:
    payload = {
        "psalm_number": 23,
        "confidence": "high",
        "reason": "The shepherd, the still waters.",
        "alternatives": [],
        "title": "The Lord's my shepherd",
    }
    payload.update(overrides)
    return payload


def test_codex_names_the_psalm_a_paste_translates_in_a_thread_of_its_own() -> None:
    client, result = _identify(_identification(alternatives=[1, 23, 150]))

    assert result["status"] == translation.RUN_COMPLETED
    assert result["psalm_id"] == "ps023"
    assert result["confidence"] == "high"
    assert result["title"] == "The Lord's my shepherd"
    # The pick is not its own alternative, and a psalm this workspace lacks is not offered.
    assert result["alternatives"] == ["ps001"]
    prompt = client.transport.prompts()[0]
    assert PASTE.strip() in prompt
    assert "Masoretic" in prompt
    session = translation.list_sessions()[-1]
    assert (session["psalm_id"], session["purpose"]) == (None, "identify")


def test_a_psalm_this_workspace_lacks_is_refused() -> None:
    _, result = _identify(_identification(psalm_number=150))

    assert result["status"] == translation.RUN_INVALID_OUTPUT
    assert result["psalm_id"] is None


def test_a_paste_that_translates_no_psalm_names_none() -> None:
    _, result = _identify(_identification(psalm_number=None, confidence="low", title=""))

    assert result["status"] == translation.RUN_COMPLETED
    assert result["psalm_id"] is None
