from __future__ import annotations

import pytest

from app.services import greek_lexical_preview_service as lexical
from app.services.greek_lexical_lookup_service import LexicalIndex
from app.services.greek_nt_input_service import parse_nestle1904

pytestmark = pytest.mark.no_seeded_repo


def test_nt_row_retains_text_reference_tags_and_lexical_identifier():
    row = parse_nestle1904(
        "Matt 1:1\tΒίβλος\tN-NSF\tN-NSF\t976\tβίβλος\tΒίβλος\t", package_id="nt.fixture"
    )[0]
    assert row["reference"] == "nt:nestle1904:Matt.1.1"
    assert row["lexical_identifiers"] == ["G976"]
    assert row["scheme"] == "Robinson"
    assert row["features"] == {}
    assert row["source_locator"]["line"] == 1


def test_nt_does_not_confuse_tvm_with_a_lexical_identifier_and_retains_homonym_label():
    row = parse_nestle1904(
        "Matt 1:1\tδοῦλος\tN-NSM\tN-NSM\t1401&5656\tδοῦλος (II)\tδοῦλος\t",
        package_id="nt.fixture",
    )[0]
    assert row["lemma"] == "δοῦλος"
    assert row["raw_lemma"] == "δοῦλος (II)"
    assert row["raw_strongs"] == "1401&5656"
    assert row["lexical_identifiers"] == ["G1401"]


def test_nt_morphology_alternatives_are_preserved_with_a_finding():
    row = parse_nestle1904(
        "Matt 10:28\tφοβεῖσθε\tV-PEM-2P@@V-PNM-2P\tV-PEM-2P@@V-PNM-2P"
        "\t5399\tφοβέω\tφοβεῖσθε\tV-PEM-2P\tV-PNM-2P",
        package_id="nt.fixture",
    )[0]
    assert row["morphology_alternatives"] == ["V-PEM-2P", "V-PNM-2P"]
    assert row["findings"] == ["additional_morphology_columns"]


def test_source_lexical_identifiers_can_supply_context_without_borrowed_nt_grammar():
    entries = [
        {
            "entry_id": "source",
            "headword": "authored lemma",
            "gloss": "authored meaning",
            "identifiers": [{"scheme": "eStrong", "relation": "entry", "value": "G976"}],
        }
    ]
    rows = parse_nestle1904(
        "Matt 1:1\tΒίβλος\tN-NSF\tN-NSF\t976\tβίβλος\tΒίβλος\t", package_id="nt.fixture"
    )
    result = LexicalIndex(entries, rows).fallback({"token_id": "lxx.fixture", "surface": "βίβλος"})
    assert result[0]["dictionary_entries"][0]["gloss"] == "authored meaning"
    assert result[0]["features"] == {}
    assert result[0]["evidence"]["source_row_ids"] == ["nt.fixture:row:1"]


def test_nt_catalog_covers_all_27_books_and_exact_source_token_count():
    nt = lexical.CORPUS_CATALOG["new_testament"]
    assert len(nt["books"]) == 27
    assert sum(b["tokens"] for b in nt["books"]) == 137779


@pytest.mark.parametrize(
    "text",
    [
        "Fake 1:1\tλόγος\tN-NSM\tN-NSM\t3056\tλόγος\tλόγος",
        "John 1:1\tλόγος\tN-NSM\tN-NSM\t3056garbage\tλόγος\tλόγος",
        "John 1:1\tλόγος\tN-NSM\tN-NSM\t3056\tλόγος\tλόγος\tgarbage",
    ],
)
def test_nt_parser_refuses_invalid_books_identifiers_and_unexplained_extra_columns(text):
    with pytest.raises(ValueError):
        parse_nestle1904(text, package_id="nt.fixture")
