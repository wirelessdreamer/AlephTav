from __future__ import annotations

import pytest

from app.core.errors import ValidationError
from app.services import comparison_assessment_service, registry_service

UNIT_ID = "ps001.v001.a"
LITERAL_ONLY_UNIT_ID = "ps019.v001.a"  # fixture unit with no lyric rendering


def _rendering_ids(unit_id: str = UNIT_ID) -> tuple[str, str]:
    unit = registry_service.load_unit(unit_id)
    literal = comparison_assessment_service.select_rendering(unit, "literal")
    english = comparison_assessment_service.select_rendering(unit, "lyric")
    assert literal is not None
    assert english is not None
    return literal["rendering_id"], english["rendering_id"]


def test_create_assessment_is_stored_on_the_unit_with_an_audit_record() -> None:
    literal_id, english_id = _rendering_ids()

    item = comparison_assessment_service.create_assessment(
        unit_id=UNIT_ID,
        literal_rendering_id=literal_id,
        english_rendering_id=english_id,
        accuracy_rating="close",
        accuracy_note="Keeps the heavens/firmament pair.",
        creative_liberties_note="Contracted for singability.",
        created_by="tester",
        created_via="codex",
        generator_provider="codex-app-server",
    )

    assert item["comparison_id"].startswith(f"cmp.{UNIT_ID}.")
    assert item["audit_ids"], "assessment must link its audit record"

    unit = registry_service.load_unit(UNIT_ID)
    stored = unit["comparison_assessments"]
    assert [entry["comparison_id"] for entry in stored] == [item["comparison_id"]]
    # MT numbering is preserved separately from the user-facing reference.
    assert stored[0]["mt_reference"] == unit["ref"]
    assert stored[0]["display_reference"] == unit["ref"]

    audit_ids = {record["audit_id"] for record in unit["audit_records"]}
    assert set(item["audit_ids"]) <= audit_ids
    created = next(
        record for record in unit["audit_records"] if record["audit_id"] == item["audit_ids"][0]
    )
    assert created["entity_type"] == "comparison_assessment"
    assert created["change_type"] == "create"


def test_create_assessment_rejects_a_rendering_that_is_not_on_the_unit() -> None:
    _literal_id, english_id = _rendering_ids()

    with pytest.raises(ValidationError):
        comparison_assessment_service.create_assessment(
            unit_id=UNIT_ID,
            literal_rendering_id="rnd.ps019.v001.a.literal.can.0001",
            english_rendering_id=english_id,
        )


def test_create_assessment_rejects_unknown_accuracy_rating() -> None:
    literal_id, english_id = _rendering_ids()

    with pytest.raises(ValidationError):
        comparison_assessment_service.create_assessment(
            unit_id=UNIT_ID,
            literal_rendering_id=literal_id,
            english_rendering_id=english_id,
            accuracy_rating="mostly_right",
        )


def test_revise_assessment_supersedes_the_original_without_overwriting_it() -> None:
    literal_id, english_id = _rendering_ids()
    original = comparison_assessment_service.create_assessment(
        unit_id=UNIT_ID,
        literal_rendering_id=literal_id,
        english_rendering_id=english_id,
        accuracy_rating="adapted",
        accuracy_note="Codex original note.",
        created_via="codex",
        generator_provider="codex-app-server",
    )

    successor = comparison_assessment_service.revise_assessment(
        unit_id=UNIT_ID,
        comparison_id_value=original["comparison_id"],
        created_by="reviewer",
        reviewer_id="rev-1",
        accuracy_rating="close",
        accuracy_note="Reviewer tightened the rating.",
    )

    assert successor["revision_of"] == original["comparison_id"]
    assert successor["status"] == "reviewed"
    assert successor["reviewer_id"] == "rev-1"
    assert successor["reviewed_at"]
    # Provenance of the original generator survives the review.
    assert successor["created_via"] == "codex"
    assert successor["generator_provider"] == "codex-app-server"

    unit = registry_service.load_unit(UNIT_ID)
    stored = {entry["comparison_id"]: entry for entry in unit["comparison_assessments"]}
    assert stored[original["comparison_id"]]["status"] == "superseded"
    # The original text is untouched, not overwritten by the review.
    assert stored[original["comparison_id"]]["accuracy_note"] == "Codex original note."
    assert stored[original["comparison_id"]]["accuracy_rating"] == "adapted"


def test_revise_assessment_refuses_to_revise_a_superseded_assessment() -> None:
    literal_id, english_id = _rendering_ids()
    original = comparison_assessment_service.create_assessment(
        unit_id=UNIT_ID,
        literal_rendering_id=literal_id,
        english_rendering_id=english_id,
    )
    comparison_assessment_service.revise_assessment(
        unit_id=UNIT_ID,
        comparison_id_value=original["comparison_id"],
        accuracy_note="first revision",
    )

    with pytest.raises(ValidationError):
        comparison_assessment_service.revise_assessment(
            unit_id=UNIT_ID,
            comparison_id_value=original["comparison_id"],
            accuracy_note="second revision",
        )


def test_list_assessments_hides_superseded_and_filters_by_rating() -> None:
    literal_id, english_id = _rendering_ids()
    original = comparison_assessment_service.create_assessment(
        unit_id=UNIT_ID,
        literal_rendering_id=literal_id,
        english_rendering_id=english_id,
        accuracy_rating="adapted",
    )
    successor = comparison_assessment_service.revise_assessment(
        unit_id=UNIT_ID,
        comparison_id_value=original["comparison_id"],
        accuracy_rating="close",
    )

    active = comparison_assessment_service.list_assessments("ps001")
    assert [entry["comparison_id"] for entry in active] == [successor["comparison_id"]]

    everything = comparison_assessment_service.list_assessments("ps001", include_superseded=True)
    assert len(everything) == 2

    filtered = comparison_assessment_service.list_assessments("ps001", accuracy_rating="close")
    assert [entry["comparison_id"] for entry in filtered] == [successor["comparison_id"]]
    assert comparison_assessment_service.list_assessments("ps001", accuracy_rating="omission") == []


def test_build_comparison_table_returns_five_column_rows() -> None:
    literal_id, english_id = _rendering_ids()
    comparison_assessment_service.create_assessment(
        unit_id=UNIT_ID,
        literal_rendering_id=literal_id,
        english_rendering_id=english_id,
        accuracy_rating="very_close",
        accuracy_note="Tracks the Hebrew clause order.",
        creative_liberties_note="None beyond contraction.",
    )

    table = comparison_assessment_service.build_comparison_table("ps001")
    assert table["literal_layer"] == "literal"
    assert table["english_layer"] == "lyric"

    row = next(row for row in table["rows"] if UNIT_ID in row["unit_ids"])
    unit = registry_service.load_unit(UNIT_ID)
    assert row["hebrew_text"] == unit["source_hebrew"]
    assert row["literal_text"]
    assert row["english_text"]
    assert row["accuracy_rating"] == "very_close"
    assert row["creative_liberties_note"] == "None beyond contraction."
    assert row["incomplete"] is False


def test_comparison_table_marks_rows_without_an_english_rendering_incomplete() -> None:
    # No assessment and no rendering at this layer: the row must report itself
    # incomplete rather than inventing text.
    table = comparison_assessment_service.build_comparison_table("ps019")

    row = next(row for row in table["rows"] if LITERAL_ONLY_UNIT_ID in row["unit_ids"])
    assert row["literal_text"], "the literal side is present"
    assert row["english_text"] is None
    assert row["incomplete"] is True
    assert row["accuracy_rating"] is None


def test_rebuild_mirrors_assessments_into_the_query_index() -> None:
    from app.db.session import get_connection
    from app.services import concordance_service

    literal_id, english_id = _rendering_ids()
    item = comparison_assessment_service.create_assessment(
        unit_id=UNIT_ID,
        literal_rendering_id=literal_id,
        english_rendering_id=english_id,
        accuracy_rating="close",
        created_via="codex",
        generator_provider="codex-app-server",
    )

    counts = concordance_service.rebuild_indexes()
    assert counts["comparison_assessments"] >= 1

    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM comparison_assessment_index WHERE comparison_id = ?",
            (item["comparison_id"],),
        ).fetchone()

    assert row is not None
    assert row["unit_id"] == UNIT_ID
    assert row["accuracy_rating"] == "close"
    assert row["created_via"] == "codex"


def test_units_carrying_assessments_still_validate_against_the_schema() -> None:
    from scripts.validate_content import validate_all_content

    literal_id, english_id = _rendering_ids()
    comparison_assessment_service.create_assessment(
        unit_id=UNIT_ID,
        literal_rendering_id=literal_id,
        english_rendering_id=english_id,
        accuracy_rating="literal",
    )

    result = validate_all_content()
    assert result["errors"] == []


# -- The seventh rating and its evidence -----------------------------------


def test_no_source_basis_is_refused_without_the_material_it_names() -> None:
    literal_id, english_id = _rendering_ids()

    with pytest.raises(ValidationError, match="non_source_material"):
        comparison_assessment_service.create_assessment(
            unit_id=UNIT_ID,
            literal_rendering_id=literal_id,
            english_rendering_id=english_id,
            accuracy_rating="no_source_basis",
        )


def test_no_source_basis_is_accepted_when_the_material_is_declared() -> None:
    literal_id, english_id = _rendering_ids()

    item = comparison_assessment_service.create_assessment(
        unit_id=UNIT_ID,
        literal_rendering_id=literal_id,
        english_rendering_id=english_id,
        accuracy_rating="no_source_basis",
        non_source_material=[
            {
                "text": "[6/8]",
                "kind": "meter",
                "note": "Arrangement decision; Psalm 1 gives no meter.",
            }
        ],
    )

    assert item["accuracy_rating"] == "no_source_basis"
    assert item["non_source_material"][0]["kind"] == "meter"


def test_human_assessments_default_to_empty_evidence_and_a_null_fingerprint() -> None:
    literal_id, english_id = _rendering_ids()

    item = comparison_assessment_service.create_assessment(
        unit_id=UNIT_ID,
        literal_rendering_id=literal_id,
        english_rendering_id=english_id,
        accuracy_rating="close",
    )

    assert item["literal_backbone"] == []
    assert item["word_notes"] == []
    assert item["non_source_material"] == []
    # Null is also what marks a row as not written by the analysis pass.
    assert item["analyzed_text_hash"] is None


def test_review_revises_the_verdict_without_discarding_the_evidence() -> None:
    literal_id, english_id = _rendering_ids()
    original = comparison_assessment_service.create_assessment(
        unit_id=UNIT_ID,
        literal_rendering_id=literal_id,
        english_rendering_id=english_id,
        accuracy_rating="interpretive",
        created_via="codex",
        literal_backbone=["Blessed is the one who does not walk"],
        word_notes=[
            {
                "token_ids": ["ps001.v001.t001"],
                "transliteration": "ashre",
                "lexical_gloss": "blessedness of",
                "rendered_as": "How blessed",
                "verdict": "expansion",
                "note": "Plural construct heightened to an exclamation.",
            }
        ],
        analyzed_text_hash="abc123",
    )

    successor = comparison_assessment_service.revise_assessment(
        unit_id=UNIT_ID,
        comparison_id_value=original["comparison_id"],
        accuracy_rating="close",
    )

    assert successor["accuracy_rating"] == "close"
    # A reviewer revises the verdict, not the findings behind it.
    assert successor["literal_backbone"] == original["literal_backbone"]
    assert successor["word_notes"] == original["word_notes"]
    assert successor["analyzed_text_hash"] == "abc123"


def test_units_carrying_the_new_evidence_fields_still_validate() -> None:
    from scripts.validate_content import validate_all_content

    literal_id, english_id = _rendering_ids()
    comparison_assessment_service.create_assessment(
        unit_id=UNIT_ID,
        literal_rendering_id=literal_id,
        english_rendering_id=english_id,
        accuracy_rating="no_source_basis",
        literal_backbone=["Blessed is the one"],
        word_notes=[
            {
                "token_ids": ["ps001.v001.t001", "ps001.v001.t002"],
                "transliteration": "ashre ha-ish",
                "lexical_gloss": "blessedness of the man",
                "rendered_as": "How blessed is the one",
                "verdict": "defensible",
                "note": "Bound phrase rendered as a unit.",
            }
        ],
        non_source_material=[
            {"text": "[Verse 1]", "kind": "section_label", "note": "Arrangement."}
        ],
        analyzed_text_hash="deadbeef",
    )

    assert validate_all_content()["errors"] == []
