"""The alignment Codex gives with a rendering: kept, recovered, and read as links.

Codex returns hints such as "ps001.v001.t002–t003 → the man" with each candidate. They
are kept in the rendering's provenance, and the comparison table reads them as links
from Hebrew tokens to the words of the literal.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.services import codex_app_server_service as codex
from app.services import codex_translation_service as translation
from app.services import comparison_assessment_service as comparisons
from app.services import registry_service
from tests.unit.test_verse_notes import ScriptedTransport, _candidate

PSALM_ID = "ps001"
UNIT_ID = "ps001.v001.a"
HINTS = ["ps001.v001.t001 → Happy", "ps001.v001.t001–t002 → Happy is the man"]


@pytest.fixture(autouse=True)
def _restore_unit():
    translation._store_path().unlink(missing_ok=True)
    unit = registry_service.load_unit(UNIT_ID)
    yield
    registry_service.save_unit(unit)
    translation._store_path().unlink(missing_ok=True)


def _write_literal(hints: list[str]) -> dict[str, Any]:
    """A literal Codex writes for the verse, saved from its run."""
    reply = {
        "unit_id": UNIT_ID,
        "layer": "literal",
        "candidates": [{**_candidate("Happy is the man who walks not"), "alignment_hints": hints}],
    }
    client = codex.CodexAppServerClient(transport=ScriptedTransport([reply]))
    session_id = translation.create_session(client, psalm_id=PSALM_ID)["session_id"]
    run = translation.run_translation_turn(client, session_id, UNIT_ID, "literal")
    [rendering] = translation.save_run_candidates(run["run_id"])
    return rendering


def test_the_alignment_codex_gives_is_kept_with_the_rendering() -> None:
    rendering = _write_literal(HINTS)

    assert rendering["provenance"]["alignment_hints"] == HINTS


def test_hints_are_read_as_links_from_tokens_to_words() -> None:
    ids = [f"ps025.v002.t00{n}" for n in range(1, 6)]
    unit = {"unit_id": "ps025.v002.a", "tokens": [{"token_id": token_id} for token_id in ids]}
    rendering = {
        "provenance": {
            "alignment_hints": [
                "ps025.v002.t001 → My God",
                "ps025.v002.t002–t004 → in you I have trusted",
                "t005 -> let me not",
                "ps025.v002.t001, ps025.v002.t005 → both",
                "ps019.v001.t001 → another psalm",
                "no arrow at all",
            ]
        }
    }

    links = comparisons.alignment_links(unit, rendering)

    assert links == [
        {"token_ids": ids[:1], "text": "My God"},
        {"token_ids": ids[1:4], "text": "in you I have trusted"},
        {"token_ids": ids[4:], "text": "let me not"},
        {"token_ids": [ids[0], ids[4]], "text": "both"},
    ]


def test_the_table_row_carries_the_literal_links() -> None:
    unit = registry_service.load_unit(UNIT_ID)
    literal = comparisons.select_rendering(unit, "literal")
    literal["provenance"]["alignment_hints"] = HINTS
    registry_service.save_unit(unit)

    table = comparisons.build_comparison_table(PSALM_ID)

    row = next(row for row in table["rows"] if UNIT_ID in row["unit_ids"])
    assert row["literal_links"] == [
        {"token_ids": ["ps001.v001.t001"], "text": "Happy"},
        {"token_ids": ["ps001.v001.t001", "ps001.v001.t002"], "text": "Happy is the man"},
    ]


def test_hints_lost_before_they_were_kept_are_recovered_from_the_run_log() -> None:
    from scripts.validate_content import validate_all_content

    rendering = _write_literal(HINTS)
    # A literal saved before hints were kept: its run still has them.
    unit = registry_service.load_unit(UNIT_ID)
    stored = next(r for r in unit["renderings"] if r["rendering_id"] == rendering["rendering_id"])
    del stored["provenance"]["alignment_hints"]
    registry_service.save_unit(unit)

    counts = translation.recover_alignment_hints()

    unit = registry_service.load_unit(UNIT_ID)
    stored = next(r for r in unit["renderings"] if r["rendering_id"] == rendering["rendering_id"])
    assert stored["provenance"]["alignment_hints"] == HINTS
    assert counts["recovered"] == 1
    record = unit["audit_records"][-1]
    assert (record["summary"], record["entity_id"]) == (
        "Record alignment hints",
        rendering["rendering_id"],
    )
    assert validate_all_content()["errors"] == []
    # A second pass finds them kept and changes nothing.
    again = translation.recover_alignment_hints()
    assert again["recovered"] == 0
    assert again["already_kept"] >= 1
