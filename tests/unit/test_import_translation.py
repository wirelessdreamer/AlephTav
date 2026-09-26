"""Importing an existing translation: placed verse by verse, never rewritten."""

from __future__ import annotations

from typing import Any

import pytest

from app.services import codex_app_server_service as codex
from app.services import codex_arrangement_service as drafting
from app.services import codex_import_service as importing
from app.services import codex_translation_service as translation
from app.services import registry_service
from tests.unit.test_verse_notes import ScriptedTransport

PSALM_ID = "ps001"
UNIT_ID = "ps001.v001.a"

PASTE = """Psalm 1, sung
Meter: 6/8
[Verse 1]
1 How happy the one who won’t walk
where the wicked give counsel,
[Chorus]
Planted, planted by the water."""


@pytest.fixture(autouse=True)
def _restore_psalm():
    meta = registry_service.load_psalm_meta(PSALM_ID)
    unit = registry_service.load_unit(UNIT_ID)
    yield
    registry_service.save_psalm_meta(PSALM_ID, meta)
    registry_service.save_unit(unit)


def _reading(**overrides: Any) -> dict[str, Any]:
    reading = {
        "title": "Psalm 1, sung",
        "guidance": ["Meter: 6/8"],
        "verses": [
            {
                "unit_id": UNIT_ID,
                "text": "How happy the one who won't walk\nwhere the wicked give counsel,",
            }
        ],
        "unplaced": [
            {"text": "Planted, planted by the water.", "reason": "An added closing line."}
        ],
    }
    reading.update(overrides)
    return reading


def _session(payloads: list[Any]) -> tuple[codex.CodexAppServerClient, str]:
    client = codex.CodexAppServerClient(transport=ScriptedTransport(payloads))
    return client, translation.create_session(client, psalm_id=PSALM_ID)["session_id"]


def _renderings(layer: str) -> list[dict[str, Any]]:
    unit = registry_service.load_unit(UNIT_ID)
    return [r for r in unit.get("renderings", []) if r["layer"] == layer]


def test_a_pasted_translation_is_placed_verse_by_verse_with_its_guidance() -> None:
    from scripts.validate_content import validate_all_content

    translation.set_guidance(PSALM_ID, "Keep it singable.")
    client, session_id = _session([_reading()])

    result = importing.import_translation(
        client, session_id, PSALM_ID, PASTE, layer="metered_lyric"
    )

    prompt = client.transport.prompts()[0]
    assert PASTE.strip() in prompt
    assert UNIT_ID in prompt
    assert result["status"] == translation.RUN_COMPLETED
    assert result["title"] == "Psalm 1, sung"
    # The paste's guidance goes below the psalm's own, which is kept.
    assert translation.get_guidance(PSALM_ID) == (
        "Keep it singable.\n\nFrom the imported translation:\nMeter: 6/8"
    )
    [placed] = result["renderings"]
    assert placed["unit_id"] == UNIT_ID
    assert placed["shown"] is True
    [rendering] = _renderings("metered_lyric")
    assert rendering["status"] == "proposed"
    assert rendering["text"] == "How happy the one who won't walk\nwhere the wicked give counsel,"
    assert rendering["provenance"]["imported"] is True
    assert result["unplaced"][0]["reason"] == "An added closing line."
    assert validate_all_content()["errors"] == []


def test_an_import_that_rewrites_the_paste_stores_nothing() -> None:
    reading = _reading(verses=[{"unit_id": UNIT_ID, "text": "How happy is the one"}])
    client, session_id = _session([reading])
    before = translation.get_guidance(PSALM_ID)

    result = importing.import_translation(
        client, session_id, PSALM_ID, PASTE, layer="metered_lyric"
    )

    assert result["status"] == translation.RUN_INVALID_OUTPUT
    assert "How happy is the one" in result["error"]
    assert _renderings("metered_lyric") == []
    assert translation.get_guidance(PSALM_ID) == before


def test_a_verse_that_is_not_in_the_psalm_is_refused() -> None:
    reading = _reading(
        verses=[{"unit_id": "ps001.v009.a", "text": "where the wicked give counsel,"}]
    )
    client, session_id = _session([reading])

    result = importing.import_translation(
        client, session_id, PSALM_ID, PASTE, layer="metered_lyric"
    )

    assert result["status"] == translation.RUN_INVALID_OUTPUT
    assert "ps001.v009.a is not a verse" in result["error"]


def test_a_verse_with_reviewed_text_keeps_showing_it() -> None:
    shown_before = [r for r in _renderings("lyric") if r["status"] == "accepted_as_alternate"]
    assert shown_before, "the fixture verse has a reviewed lyric"
    client, session_id = _session([_reading()])

    result = importing.import_translation(client, session_id, PSALM_ID, PASTE, layer="lyric")

    assert result["renderings"][0]["shown"] is False


def test_importing_the_same_translation_again_adds_nothing() -> None:
    client, session_id = _session([_reading(), _reading()])
    importing.import_translation(client, session_id, PSALM_ID, PASTE, layer="metered_lyric")

    again = importing.import_translation(client, session_id, PSALM_ID, PASTE, layer="metered_lyric")

    assert again["renderings"][0]["unchanged"] is True
    assert len(_renderings("metered_lyric")) == 1
    assert translation.get_guidance(PSALM_ID).count("Meter: 6/8") == 1


def _setting(line_text: str) -> dict[str, Any]:
    token = registry_service.load_unit(UNIT_ID)["tokens"][0]["token_id"]
    return {
        "title": "Psalm 1, sung",
        "sections": [
            {
                "key": "V1",
                "kind": "verse",
                "label": "Verse 1",
                "repeat_of": None,
                "lines": [
                    {"text": line_text, "token_ids": [token], "liberty": "tracks", "rationale": ""}
                ],
            }
        ],
        "omissions": [],
    }


def test_the_translation_is_analysed_as_a_setting_with_its_lines_as_pasted() -> None:
    client, session_id = _session([_setting("How happy the one who won't walk")])

    result = drafting.arrange_import(client, session_id, PSALM_ID, PASTE, layer="lyric")

    assert "[Chorus]" in client.transport.prompts()[0]
    arrangement = result["view"]["arrangement"]
    assert arrangement["created_via"] == "import"
    assert arrangement["status"] == "proposed"
    assert arrangement["sections"][0]["lines"][0]["text"] == "How happy the one who won't walk"


def test_a_setting_analysis_that_rewrites_a_line_stores_nothing() -> None:
    client, session_id = _session([_setting("How blessed the one who won't walk")])

    result = drafting.arrange_import(client, session_id, PSALM_ID, PASTE, layer="lyric")

    assert result["status"] == translation.RUN_INVALID_OUTPUT
    assert "How blessed the one" in result["error"]
    assert "arrangements" not in registry_service.load_psalm_meta(PSALM_ID)
