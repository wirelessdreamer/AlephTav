import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from app.core.ids import (
    alignment_id,
    audit_id,
    comparison_id,
    decision_id,
    ensure_id,
    issue_link_id,
    pr_link_id,
    rendering_id,
    span_id,
    unit_id_from_entity_id,
)

pytestmark = pytest.mark.no_seeded_repo


def test_id_patterns_accept_expected_values() -> None:
    assert ensure_id("project_id", "proj.main") == "proj.main"
    assert ensure_id("psalm_id", "ps023") == "ps023"
    assert ensure_id("unit_id", "ps023.v001.a") == "ps023.v001.a"


def test_generated_ids_follow_required_formats() -> None:
    assert alignment_id("ps023.v001.a", "literal", []) == "aln.ps023.v001.a.literal.0001"
    assert rendering_id("ps023.v001.a", "lyric", "alt", []) == "rnd.ps023.v001.a.lyric.alt.0001"
    assert issue_link_id(123) == "iss.000123"
    assert pr_link_id(456) == "pr.000456"


@pytest.mark.parametrize("prefix", ["", "lxx."])
def test_unit_scoped_id_generation_and_parsing_preserve_corpus(prefix: str) -> None:
    unit_id = f"{prefix}ps023.v001.a"
    assert ensure_id("unit_id", unit_id) == unit_id
    token_id = f"{prefix}ps023.v001.t001"
    assert ensure_id("token_id", token_id) == token_id
    generated = {
        "alignment_id": alignment_id(unit_id, "literal", []),
        "audit_id": audit_id(unit_id, []),
        "comparison_id": comparison_id(unit_id, []),
        "decision_id": decision_id(unit_id, []),
        "rendering_id": rendering_id(unit_id, "literal", "can", []),
        "alternate_id": rendering_id(unit_id, "lyric", "alt", []),
        "span_id": span_id(unit_id, "literal", []),
        "concept_id": f"cpt.{unit_id}.0001",
    }
    for kind, value in generated.items():
        assert ensure_id(kind, value) == value
        assert unit_id_from_entity_id(kind, value) == unit_id

    # Hebrew and Greek sequences must not borrow each other's suffixes.
    other_unit_id = f"{'lxx.' if not prefix else ''}ps023.v001.a"
    previous = [audit_id(other_unit_id, []), audit_id(unit_id, [])]
    assert audit_id(unit_id, previous) == f"aud.{unit_id}.0002"


@pytest.mark.parametrize(
    ("kind", "value"),
    [
        ("unit_id", "lxxps023.v001.a"),
        ("unit_id", "lxx.lxx.ps023.v001.a"),
        ("unit_id", "grc.ps023.v001.a"),
        ("unit_id", "lxx.ps23.v001.a"),
        ("unit_id", "lxx.ps023.v001.a.extra"),
        ("token_id", "lxx.ps023.v001.a.t001"),
        ("alignment_id", "lxx.aln.ps023.v001.a.literal.0001"),
        ("alignment_id", "aln.lxx.lxx.ps023.v001.a.literal.0001"),
        ("audit_id", "aud.lxx.ps023.v001.0001"),
        ("rendering_id", "rnd.lxx.ps023.v001.a.literal.draft.0001"),
        ("alternate_id", "rnd.lxx.ps023.v001.a.literal.can.0001"),
        ("span_id", "spn.lxx.ps023.v001.a.literal.1"),
    ],
)
def test_malformed_corpus_ids_are_rejected(kind: str, value: str) -> None:
    with pytest.raises(ValueError, match="Invalid"):
        ensure_id(kind, value)
    with pytest.raises(ValueError, match="Invalid"):
        unit_id_from_entity_id(kind, value)


def test_entity_parser_rejects_ids_without_a_unit() -> None:
    with pytest.raises(ValueError, match="unit-scoped"):
        unit_id_from_entity_id("psalm_id", "ps023")


@pytest.mark.parametrize(
    ("schema_name", "path", "value"),
    [
        ("alignment", "properties.unit_id", "lxx.ps023.v001.a"),
        ("alignment", "properties.alignment_id", "aln.lxx.ps023.v001.a.literal.0001"),
        ("audit_record", "properties.audit_id", "aud.lxx.ps023.v001.a.0001"),
        ("unit", "properties.unit_id", "lxx.ps023.v001.a"),
        (
            "unit",
            "properties.review_decisions.items.properties.decision_id",
            "rev.lxx.ps023.v001.a.0001",
        ),
        ("token", "properties.token_id", "lxx.ps023.v001.t001"),
        ("rendering", "properties.unit_id", "lxx.ps023.v001.a"),
        ("rendering", "properties.rendering_id", "rnd.lxx.ps023.v001.a.literal.can.0001"),
        (
            "rendering",
            "properties.target_spans.items.properties.span_id",
            "spn.lxx.ps023.v001.a.literal.0001",
        ),
        ("comparison_assessment", "properties.unit_id", "lxx.ps023.v001.a"),
        ("comparison_assessment", "properties.comparison_id", "cmp.lxx.ps023.v001.a.0001"),
        (
            "comparison_assessment",
            "properties.word_notes.items.properties.token_ids.items",
            "lxx.ps023.v001.t001",
        ),
        ("psalm_meta", "properties.unit_ids.items", "lxx.ps023.v001.a"),
        ("psalm_meta", "$defs.anchor.properties.unit_id", "lxx.ps023.v001.a"),
        ("psalm_meta", "$defs.omission.properties.unit_id", "lxx.ps023.v001.a"),
    ],
)
def test_schema_id_fields_accept_only_the_supported_corpus_prefix(
    schema_name: str, path: str, value: str
) -> None:
    schema_path = Path(__file__).resolve().parents[2] / "schemas" / f"{schema_name}.schema.json"
    field = json.loads(schema_path.read_text(encoding="utf-8"))
    for key in path.split("."):
        field = field[key]
    validator = Draft202012Validator(field)
    validator.validate(value)
    validator.validate(value.replace("lxx.", ""))
    for malformed in (
        value.replace("lxx.", "lxx.lxx."),
        value.replace("lxx.", "grc."),
        value.replace("lxx.", "lxx"),
        f"{value}.extra",
    ):
        assert list(validator.iter_errors(malformed)), malformed
