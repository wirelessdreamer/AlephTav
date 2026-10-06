"""Song settings: sections free of verse boundaries, every departure declared."""

from __future__ import annotations

from typing import Any

import pytest

from app.core.errors import NotFoundError, ReviewRequiredError, ValidationError
from app.services import arrangement_service as arrangements
from app.services import codex_app_server_service as codex
from app.services import codex_arrangement_service as drafting
from app.services import codex_translation_service as translation
from app.services import registry_service
from tests.unit.test_verse_notes import ScriptedTransport

PSALM_ID = "ps001"
UNIT_ID = "ps001.v001.a"


@pytest.fixture(autouse=True)
def _restore_psalm():
    meta = registry_service.load_psalm_meta(PSALM_ID)
    unit = registry_service.load_unit(UNIT_ID)
    yield
    registry_service.save_psalm_meta(PSALM_ID, meta)
    registry_service.save_unit(unit)


def _tokens() -> list[str]:
    return [t["token_id"] for t in registry_service.load_unit(UNIT_ID)["tokens"]]


def _setting(**overrides: Any) -> dict[str, Any]:
    """The fixture verse has two words. The verse and the chorus both sing the first;
    the chorus is sung again; an added line closes; the second word is left out."""
    tokens = _tokens()
    sections = [
        {
            "key": "V1",
            "kind": "verse",
            "label": "Verse 1",
            "repeat_of": None,
            "lines": [
                {"text": "How happy the one", "token_ids": tokens[:1], "liberty": "tracks"},
            ],
        },
        {
            "key": "C",
            "kind": "chorus",
            "label": "Chorus",
            "repeat_of": None,
            "lines": [
                {
                    "text": "who won't walk that way",
                    "token_ids": tokens[:1],
                    "liberty": "compressed",
                    "rationale": "Two words folded into one image.",
                },
            ],
        },
        {"key": "C2", "kind": "chorus", "label": "Chorus", "repeat_of": "C", "lines": []},
        {
            "key": "O",
            "kind": "outro",
            "label": "Outro",
            "repeat_of": None,
            "lines": [{"text": "Happy, happy", "token_ids": [], "liberty": "tracks"}],
        },
    ]
    return arrangements.create_arrangement(
        PSALM_ID, created_by="tester", sections=overrides.pop("sections", sections), **overrides
    )


def test_a_setting_is_stored_on_the_psalm_validated_and_audited() -> None:
    from scripts.validate_content import validate_all_content

    audits = len(registry_service.load_unit(UNIT_ID).get("audit_records", []))

    view = _setting()

    arrangement = view["arrangement"]
    assert arrangement["arrangement_id"] == "arr.ps001.0001"
    assert [s["label"] for s in arrangement["sections"]] == ["Verse 1", "Chorus", "Chorus", "Outro"]
    assert arrangement["sections"][2]["repeat_of"] == arrangement["sections"][1]["section_id"]
    # A line that renders no Hebrew is added, whatever it was called.
    assert arrangement["sections"][3]["lines"][0]["liberty"] == "added"
    stored = registry_service.load_psalm_meta(PSALM_ID)["arrangements"]
    assert [a["arrangement_id"] for a in stored] == ["arr.ps001.0001"]
    records = registry_service.load_unit(UNIT_ID)["audit_records"]
    assert len(records) == audits + 1
    assert records[-1]["entity_type"] == "arrangement"
    assert records[-1]["entity_id"] == "arr.ps001.0001"
    assert arrangement["audit_ids"] == [records[-1]["audit_id"]]
    assert validate_all_content()["errors"] == []


def test_a_setting_can_be_deleted_with_an_audit_record() -> None:
    arrangement_id = _setting()["arrangement"]["arrangement_id"]
    audits = len(registry_service.load_unit(UNIT_ID).get("audit_records", []))

    result = arrangements.delete_arrangement(
        PSALM_ID,
        arrangement_id,
        created_by="tester",
        rationale="remove accidental duplicate",
    )

    assert result["deleted"] == arrangement_id
    assert registry_service.load_psalm_meta(PSALM_ID)["arrangements"] == []
    records = registry_service.load_unit(UNIT_ID)["audit_records"]
    assert len(records) == audits + 1
    assert records[-1]["entity_id"] == arrangement_id
    assert records[-1]["change_type"] == "delete"
    with pytest.raises(NotFoundError):
        arrangements.get_arrangement(PSALM_ID, arrangement_id)


def test_a_repeat_is_sung_again_and_counted_in_the_coverage() -> None:
    view = _setting()
    tokens = _tokens()

    sung = view["sung"]
    assert [item["line"]["text"] for item in sung] == [
        "How happy the one",
        "who won't walk that way",
        "who won't walk that way",
        "Happy, happy",
    ]
    assert [(item["time"], item["repeat"]) for item in sung[1:3]] == [(1, False), (2, True)]
    counts = {t["token_id"]: t["count"] for t in view["coverage"]["units"][0]["tokens"]}
    assert [counts[t] for t in tokens] == [3, 0]
    assert view["coverage"]["totals"] == {
        "words": 2,
        "once": 0,
        "repeated": 1,
        "dropped": 1,
    }


def test_departures_are_listed_with_the_approvals_they_need() -> None:
    view = _setting()

    by_kind = {item["kind"]: item for item in view["liberties"]}
    assert by_kind["compressed"]["required"] == 1
    assert by_kind["compressed"]["rationale"] == "Two words folded into one image."
    assert by_kind["repeated"]["settled"] is True
    assert by_kind["added"]["required"] == 1
    assert by_kind["dropped"]["token_ids"] == _tokens()[1:]
    assert by_kind["dropped"]["required"] == 2
    assert view["summary"]["open"] == 3


def test_a_setting_is_accepted_only_once_every_departure_is_approved() -> None:
    view = _setting()
    arrangement_id = view["arrangement"]["arrangement_id"]
    compressed = next(i for i in view["liberties"] if i["kind"] == "compressed")
    added = next(i for i in view["liberties"] if i["kind"] == "added")
    dropped = next(i for i in view["liberties"] if i["kind"] == "dropped")

    with pytest.raises(ReviewRequiredError):
        arrangements.update_arrangement(
            PSALM_ID, arrangement_id, created_by="tester", status="accepted"
        )

    for item in (compressed, added):
        arrangements.approve_line(
            PSALM_ID,
            arrangement_id,
            item["line_id"],
            reviewer="Ana",
            reviewer_role="lyric reviewer",
        )
    with pytest.raises(ValidationError):  # the first approval must say why
        arrangements.approve_omission(
            PSALM_ID,
            arrangement_id,
            unit_id=UNIT_ID,
            token_ids=dropped["token_ids"],
            reviewer="Ana",
            reviewer_role="Hebrew reviewer",
        )
    arrangements.approve_omission(
        PSALM_ID,
        arrangement_id,
        unit_id=UNIT_ID,
        token_ids=dropped["token_ids"],
        reviewer="Ana",
        reviewer_role="Hebrew reviewer",
        rationale="The song sets only the opening.",
    )
    once = arrangements.arrangement_view(PSALM_ID, arrangement_id)
    assert next(i for i in once["liberties"] if i["kind"] == "dropped")["settled"] is False

    arrangements.approve_omission(
        PSALM_ID,
        arrangement_id,
        unit_id=UNIT_ID,
        token_ids=dropped["token_ids"],
        reviewer="Ben",
        reviewer_role="theology reviewer",
    )
    accepted = arrangements.update_arrangement(
        PSALM_ID, arrangement_id, created_by="tester", status="accepted"
    )

    assert accepted["summary"]["open"] == 0
    assert accepted["arrangement"]["status"] == "accepted"


def test_an_approval_needs_a_known_reviewer_role() -> None:
    view = _setting()
    compressed = next(i for i in view["liberties"] if i["kind"] == "compressed")

    with pytest.raises(ValidationError):
        arrangements.approve_line(
            PSALM_ID,
            view["arrangement"]["arrangement_id"],
            compressed["line_id"],
            reviewer="Ana",
            reviewer_role="friend",
        )


def test_changing_an_approved_line_drops_its_approvals() -> None:
    view = _setting()
    arrangement_id = view["arrangement"]["arrangement_id"]
    compressed = next(i for i in view["liberties"] if i["kind"] == "compressed")
    arrangements.approve_line(
        PSALM_ID,
        arrangement_id,
        compressed["line_id"],
        reviewer="Ana",
        reviewer_role="lyric reviewer",
    )

    edited = arrangements.update_line(
        PSALM_ID, arrangement_id, compressed["line_id"], created_by="tester", text="who won't go"
    )

    item = next(i for i in edited["liberties"] if i["key"] == compressed["line_id"])
    assert item["approvals"] == []
    assert item["settled"] is False


def test_sections_and_lines_are_edited_moved_and_removed_with_an_audit_each() -> None:
    view = _setting()
    arrangement_id = view["arrangement"]["arrangement_id"]
    verse = view["arrangement"]["sections"][0]["section_id"]
    audits = len(view["arrangement"]["audit_ids"])

    view = arrangements.add_line(
        PSALM_ID,
        arrangement_id,
        verse,
        text="day and night",
        created_by="tester",
        anchors=[{"unit_id": UNIT_ID, "token_ids": _tokens()[1:2]}],
        index=0,
    )
    first = view["arrangement"]["sections"][0]["lines"][0]
    assert first["text"] == "day and night"
    view = arrangements.update_line(
        PSALM_ID, arrangement_id, first["line_id"], created_by="tester", index=1
    )
    assert view["arrangement"]["sections"][0]["lines"][1]["line_id"] == first["line_id"]
    view = arrangements.update_section(
        PSALM_ID, arrangement_id, verse, created_by="tester", label="Opening", index=3
    )
    assert view["arrangement"]["sections"][3]["label"] == "Opening"
    view = arrangements.remove_line(PSALM_ID, arrangement_id, first["line_id"], created_by="tester")
    view = arrangements.remove_section(PSALM_ID, arrangement_id, verse, created_by="tester")

    assert [s["label"] for s in view["arrangement"]["sections"]] == ["Chorus", "Chorus", "Outro"]
    assert len(view["arrangement"]["audit_ids"]) == audits + 5


def test_a_section_that_is_sung_again_cannot_be_removed_before_its_repeats() -> None:
    view = _setting()
    chorus = view["arrangement"]["sections"][1]["section_id"]

    with pytest.raises(ValidationError, match="Sung again"):
        arrangements.remove_section(
            PSALM_ID, view["arrangement"]["arrangement_id"], chorus, created_by="tester"
        )


def test_a_line_cannot_claim_tokens_outside_the_psalm() -> None:
    view = _setting()
    verse = view["arrangement"]["sections"][0]["section_id"]

    with pytest.raises(ValidationError, match="Tokens not in ps001"):
        arrangements.add_line(
            PSALM_ID,
            view["arrangement"]["arrangement_id"],
            verse,
            text="borrowed",
            created_by="tester",
            anchors=[{"unit_id": UNIT_ID, "token_ids": ["ps023.v001.t001"]}],
        )


def _unit(unit_id: str, words: list[str]) -> dict[str, Any]:
    return {
        "unit_id": unit_id,
        "ref": unit_id,
        "tokens": [
            {"token_id": f"{unit_id}.t{i:03d}", "surface": word} for i, word in enumerate(words)
        ],
    }


def test_refrains_are_found_across_spelling_variants() -> None:
    units = [
        _unit("ps136.v001.a", ["הוֹדוּ", "לַיהוָה", "כִּי", "לְעוֹלָם", "חַסְדּוֹ"]),
        _unit("ps136.v003.a", ["הוֹדוּ", "לַאֲדֹנֵי", "כִּי", "לְעֹלָם", "חַסְדּוֹ"]),
        _unit("ps136.v005.a", ["לְעֹשֵׂה", "הַשָּׁמַיִם", "כִּי", "לְעוֹלָם", "חַסְדּוֹ"]),
    ]

    refrains = arrangements.find_refrains(units)

    assert len(refrains) == 1
    assert refrains[0]["length"] == 3
    assert [i["unit_id"] for i in refrains[0]["instances"]] == [u["unit_id"] for u in units]
    assert refrains[0]["variants"] == 2


def test_a_verse_with_nothing_repeated_has_no_refrain() -> None:
    assert arrangements.find_refrains([_unit("ps001.v001.a", ["אַשְׁרֵי", "הָאִישׁ", "אֲשֶׁר"])]) == []


def _draft_reply(token_ids: list[str]) -> dict[str, Any]:
    return {
        "title": "Happy the one",
        "sections": [
            {
                "key": "V",
                "kind": "verse",
                "label": "Verse",
                "repeat_of": None,
                "lines": [
                    {
                        "text": "How happy the one",
                        "token_ids": token_ids,
                        "liberty": "tracks",
                        "rationale": "",
                    }
                ],
            },
            {"key": "V2", "kind": "verse", "label": "Verse again", "repeat_of": "V", "lines": []},
        ],
        "omissions": [],
    }


def _session(payloads: list[Any]) -> tuple[codex.CodexAppServerClient, str]:
    client = codex.CodexAppServerClient(transport=ScriptedTransport(payloads))
    return client, translation.create_session(client, psalm_id=PSALM_ID)["session_id"]


def test_codex_drafts_a_setting_that_is_stored_as_a_proposal() -> None:
    translation.set_guidance(PSALM_ID, "Target 6/8 meter.")
    tokens = _tokens()
    client, session_id = _session([_draft_reply(tokens[:2])])

    result = drafting.draft_arrangement(client, session_id, PSALM_ID)

    prompt = client.transport.prompts()[0]
    assert "Target 6/8 meter." in prompt
    assert f"{tokens[0]} " in prompt
    assert "repeat_of" in prompt
    assert result["status"] == translation.RUN_COMPLETED
    arrangement = result["view"]["arrangement"]
    assert arrangement["status"] == "proposed"
    assert arrangement["created_via"] == "codex"
    assert arrangement["guidance"] == "Target 6/8 meter."
    assert arrangement["generation_run_id"] == result["run_id"]
    assert len(result["view"]["sung"]) == 2


def test_a_codex_draft_naming_unknown_tokens_stores_nothing() -> None:
    client, session_id = _session([_draft_reply(["ps001.v009.t001"])])

    result = drafting.draft_arrangement(client, session_id, PSALM_ID)

    assert result["status"] == translation.RUN_INVALID_OUTPUT
    assert "Tokens not in ps001" in result["error"]
    assert "arrangements" not in registry_service.load_psalm_meta(PSALM_ID)
